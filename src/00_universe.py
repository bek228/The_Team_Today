"""Step 0: pick 50 large firms from 2020 membership and 2020 volume, among the firms Yahoo can still
price today (a survivors-only universe; see README "Threats to validity").

Method
  1. S&P 500 membership on 2021-01-01. The current Wikipedia page no longer has the
     "Selected changes" table, so instead of rebuilding old membership from changes we read the
     page itself AS IT WAS on 2020-12-31 (the last revision before 2021-01-01, found with the
     MediaWiki API). That revision's constituents table is the membership list on that date.
  2. Old tickers are mapped to today's Yahoo tickers through the SEC CIK number: if the same CIK
     is in today's constituents table we use today's symbol (e.g. FB -> META). Otherwise we keep
     the 2020 symbol ('.' becomes '-', the Yahoo convention, e.g. BRK.B -> BRK-B).
  3. One batched yf.download of daily close and volume for calendar 2020. Rank members by
     average daily dollar volume (close x volume, not adjusted for dividends). Keep one share
     class per CIK (the more traded one, e.g. GOOGL over GOOG).
  4. Keep the top 50. Members Yahoo cannot price (delisted / acquired / renamed off the CIK map)
     are written to data/raw/universe_dropped.csv: that is the residual survivorship.

Outputs: data/raw/sp500_members_2020-12-31.csv (Wikipedia revision table, as downloaded)
         data/raw/dollar_volume_2020.csv (average daily dollar volume per member)
         data/raw/universe.csv, data/raw/universe_dropped.csv
         (these two are DERIVED from the three files above, not downloaded; they stay in data/raw/
         because other code and the dashboard read them from there)
"""
import io
import time

import pandas as pd
import requests
import yfinance as yf
from _common import RAW, REFRESH, UNIVERSE_ASOF, RANK_YEAR, N_FIRMS, log_manifest, download_with_retry

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'}  # pandas' default UA gets a 403
PAGE = 'List of S&P 500 companies'
API = 'https://en.wikipedia.org/w/api.php'
members_path = RAW / 'sp500_members_2020-12-31.csv'
current_path = RAW / 'sp500_members_current.csv'
dv_path = RAW / 'dollar_volume_2020.csv'

# ---- 1. membership on 2021-01-01, from the archived Wikipedia revision ----
if members_path.exists() and current_path.exists() and not REFRESH:
    print(f'{members_path.name} and {current_path.name} exist, skipping download')
else:
    q = dict(action='query', prop='revisions', titles=PAGE, rvlimit=1, rvdir='older',
             rvstart=UNIVERSE_ASOF + 'T00:00:00Z', rvprop='ids|timestamp', format='json')
    resp = requests.get(API, params=q, headers=UA, timeout=30)
    resp.raise_for_status()  # stop with an error if Wikipedia did not answer
    rev = list(resp.json()['query']['pages'].values())[0]['revisions'][0]
    print('Wikipedia revision used:', rev)
    html = requests.get('https://en.wikipedia.org/w/index.php', params={'oldid': rev['revid']},
                        headers=UA, timeout=30).text
    old = pd.read_html(io.StringIO(html))[0]
    old['wiki_revid'], old['wiki_rev_timestamp'] = rev['revid'], rev['timestamp']
    old.to_csv(members_path, index=False)
    log_manifest(members_path, f'en.wikipedia.org {PAGE}, oldid={rev["revid"]} ({rev["timestamp"]})', len(old))

    html = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=UA, timeout=30).text
    cur = pd.read_html(io.StringIO(html))[0]
    cur.to_csv(current_path, index=False)
    log_manifest(current_path, f'en.wikipedia.org {PAGE}, current revision (for CIK -> ticker map)', len(cur))

old = pd.read_csv(members_path)
cur = pd.read_csv(current_path)
print('members on', UNIVERSE_ASOF, ':', len(old), '| revision', old['wiki_revid'].iloc[0], old['wiki_rev_timestamp'].iloc[0])
assert len(old) >= 500 and old['Symbol'].is_unique

# ---- 2. map 2020 symbols to today's Yahoo symbols via CIK ----
old['ticker_2020'] = old['Symbol']
cur_by_cik = cur.groupby('CIK')['Symbol'].apply(list)


def yahoo_symbol(row):
    now = cur_by_cik.get(row['CIK'], [])
    if row['Symbol'] in now or not now:
        return row['Symbol'].replace('.', '-'), 'same symbol' if now else 'same symbol (left the index)'
    if len(now) == 1:
        return now[0].replace('.', '-'), 'renamed (same CIK)'
    return row['Symbol'].replace('.', '-'), 'same symbol (CIK has several classes)'


old[['ticker', 'map_method']] = old.apply(yahoo_symbol, axis=1, result_type='expand')
renamed = old[old['map_method'] == 'renamed (same CIK)']
print('renamed via CIK:', dict(zip(renamed['ticker_2020'], renamed['ticker'])))
assert old['ticker'].is_unique

# ---- 3. average daily dollar volume in 2020, one batched download ----
if dv_path.exists() and not REFRESH:
    print(f'{dv_path.name} exists, skipping download')
else:
    tickers = old['ticker'].tolist()
    px = yf.download(tickers, start=f'{RANK_YEAR}-01-01', end=f'{RANK_YEAR + 1}-01-01',
                     auto_adjust=False, progress=False, threads=True)
    time.sleep(1)
    dollar_vol = px['Close'] * px['Volume']
    dv = pd.DataFrame({'ticker': tickers,
                       'avg_dollar_volume_2020': dollar_vol.mean().reindex(tickers).values,
                       'n_days_2020': dollar_vol.notna().sum().reindex(tickers).fillna(0).astype(int).values})

    # the batch call sometimes fails for a ticker Yahoo does have; retry those one by one
    errors = {}
    for t in dv.loc[dv['n_days_2020'] < 200, 'ticker']:
        def one():
            p = yf.download(t, start=f'{RANK_YEAR}-01-01', end=f'{RANK_YEAR + 1}-01-01',
                            auto_adjust=False, progress=False, multi_level_index=False)
            return (p['Close'] * p['Volume']).dropna()
        s = download_with_retry(one, t, errors, retries=2)
        if s is not None:
            dv.loc[dv['ticker'] == t, ['avg_dollar_volume_2020', 'n_days_2020']] = [s.mean(), len(s)]
            print('  retry worked:', t, len(s), 'days')
        time.sleep(0.5)
    print('no 2020 prices after retries:', sorted(errors))
    # a few dozen delisted members are expected; hundreds means the download itself failed
    if (dv['n_days_2020'] >= 200).sum() < 400:
        raise SystemExit('ERROR: fewer than 400 members have 2020 prices: the download failed. '
                         f'{dv_path.name} not written. Rerun later.')
    dv['n_days_2020'] = dv['n_days_2020'].astype(int)
    dv.to_csv(dv_path, index=False)
    log_manifest(dv_path, f'yfinance yf.download Close*Volume, {RANK_YEAR}, auto_adjust=False', len(dv))

dv = pd.read_csv(dv_path)
uni = old.merge(dv, on='ticker', how='left', validate='1:1')

# usable = Yahoo still has (nearly) a full year of 2020 prices for it
uni['dropped'] = ''
uni.loc[uni['n_days_2020'] == 0, 'dropped'] = 'Yahoo has no 2020 prices (delisted, acquired, or renamed under a CIK not in today\'s index)'
uni.loc[uni['n_days_2020'].between(1, 199), 'dropped'] = 'fewer than 200 trading days in 2020 (listed or spun off during the year)'
dropped = uni[uni['dropped'] != '']
uni = uni[uni['dropped'] == '']

# one share class per firm: keep the more traded class (GOOGL vs GOOG, FOXA vs FOX, ...)
uni = uni.sort_values('avg_dollar_volume_2020', ascending=False)
dup_class = uni[uni.duplicated('CIK', keep='first')].assign(dropped='second share class of the same firm (CIK)')
uni = uni.drop_duplicates('CIK', keep='first')

uni['rank'] = range(1, len(uni) + 1)
top = uni.head(N_FIRMS).copy()
top['name'] = top['Security']
top['sector'] = top['GICS Sector']
top['selection_metric'] = 'avg daily dollar volume, calendar 2020 (close x volume, USD)'
top['selection_value'] = top['avg_dollar_volume_2020'].round(0)
top['source'] = 'S&P 500 members per Wikipedia revision ' + top['wiki_revid'].astype(str) + '; yfinance 2020 close x volume'
top['as_of'] = UNIVERSE_ASOF
top = top[['rank', 'ticker', 'ticker_2020', 'map_method', 'name', 'sector', 'selection_metric',
           'selection_value', 'source', 'as_of']]

dropped_all = pd.concat([dropped, dup_class])[['ticker_2020', 'ticker', 'Security', 'CIK', 'map_method',
                                               'avg_dollar_volume_2020', 'n_days_2020', 'dropped']]

# checks
assert len(top) == N_FIRMS and top['ticker'].is_unique
assert top['selection_value'].is_monotonic_decreasing

top.to_csv(RAW / 'universe.csv', index=False)
dropped_all.to_csv(RAW / 'universe_dropped.csv', index=False)
print(top[['rank', 'ticker', 'name', 'sector']].to_string(index=False))
n_no_prices = (dropped['n_days_2020'] == 0).sum()
print(f'\n{n_no_prices} members could not be priced (residual survivorship), '
      f'{len(dropped) - n_no_prices} had fewer than 200 trading days in 2020, '
      f'{len(dup_class)} extra share classes:')
print(dropped_all.to_string(index=False))
print('50th firm dollar volume:', f'{top["selection_value"].iloc[-1]:,.0f}')
