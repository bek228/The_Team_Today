"""Step 1: analyst rating changes (upgrades and downgrades) for the 50 firms.

Source: yf.Ticker(t).upgrades_downgrades, one raw file per ticker in data/raw/ratings/.

Timestamps. Yahoo's GradeDate comes without a time zone. Read as UTC and converted to US/Eastern,
the clock times look like real publication times, not placeholders: in the committed snapshot
(rating changes, 2021-01-01 to 2026-10-09) almost none sit at midnight or on a round hour, and
most fall between 04:00 and 10:00 Eastern, when brokers send out their morning notes. (The table
printed below, saved to outputs/tables/rating_time_of_day.csv, shows the shares.) Read as Eastern
instead, the peak would be at 10:00-14:00, which does not fit how brokers publish. So: UTC.

Day-0 rule (applied in 04_build_event_panel.py with _common.find_day0), using the Eastern time:
  before_open (<09:30)    -> that trading day (weekend/holiday -> the next trading day)
  during_market           -> that same trading day: the news was tradable before the close
  after_close (>=16:00)   -> the next trading day
The teammates' prototype pushed during-market calls to the NEXT day. That would put the price
reaction on t=-1. It is kept as a logged sensitivity (robustness.csv, specs_tried.md).

Broker names are unified with data/raw/broker_aliases.csv (built by reading every distinct raw
name; e.g. 'Cowen & Co.' and 'TD Cowen' are one broker). After that, one broker can show the same
call twice on one day (once under each old name). Those exact repeats are dropped and logged.

Outputs: data/raw/ratings/<TICKER>.csv (as downloaded), data/processed/ratings.csv (clean),
         outputs/tables/rating_time_of_day.csv, data/processed/ratings_duplicates_dropped.csv,
         outputs/tables/ratings_coverage_by_year.csv (raw rows and kept rating changes, ticker x year)
"""
import time

import pandas as pd
import yfinance as yf
from _common import (PROC, TABLES, RATINGS_DIR, REFRESH, SAMPLE_START, SAMPLE_END, firms,
                     download_with_retry, log_manifest, timing_label, load_broker_aliases)

FIRMS = firms()

# ---- download (only tickers without a cached file, unless --refresh) ----
errors = {}
for t in FIRMS:
    path = RATINGS_DIR / f'{t}.csv'
    if path.exists() and not REFRESH:
        continue
    d = download_with_retry(lambda: yf.Ticker(t).upgrades_downgrades, t, errors)
    if d is not None:
        d = d.reset_index()
        d['ticker'] = t
        d.to_csv(path, index=False)
        log_manifest(path, f'yfinance Ticker("{t}").upgrades_downgrades', len(d))
        print(t, len(d), 'rows, earliest', d.iloc[:, 0].min())
    time.sleep(0.5)  # be polite to Yahoo
if errors:
    print('DOWNLOAD FAILURES:', errors)
missing = [t for t in FIRMS if not (RATINGS_DIR / f'{t}.csv').exists()]
if missing:  # download failed and there is no cached file: stop, never continue with a gap
    raise SystemExit(f'ERROR: rating download failed and no cached file exists for {missing} '
                     f'({errors}). Nothing was written for them; rerun later (Yahoo rate limit?).')

raw = pd.concat([pd.read_csv(RATINGS_DIR / f'{t}.csv') for t in FIRMS], ignore_index=True)
raw = raw.rename(columns={'GradeDate': 'grade_datetime', 'Firm': 'broker_raw', 'ToGrade': 'to_grade',
                          'FromGrade': 'from_grade', 'Action': 'action'})
print('raw rows:', len(raw), '| actions:', raw['action'].value_counts().to_dict())

# how far back does Yahoo go for each ticker? (it keeps roughly the last ~1,000 rows)
first = raw.groupby('ticker')['grade_datetime'].min().sort_values()
late = first[first > SAMPLE_START]
print(f'\ntickers whose Yahoo history starts after {SAMPLE_START}: {len(late)}')
print(late.to_string())

# ---- keep upgrades and downgrades only (same regex as the prototype) ----
r = raw[raw['action'].astype(str).str.strip().str.lower().str.contains(r'\b(?:up|down)', regex=True)].copy()
r['direction'] = r['action'].str.strip().str.lower().map({'up': 'upgrade', 'down': 'downgrade'})
assert r['direction'].notna().all(), 'an action matched the regex but is not up/down'

# ---- timestamps: UTC -> US/Eastern ----
r['grade_datetime_et'] = pd.to_datetime(r['grade_datetime'], utc=True).dt.tz_convert('America/New_York')
r['announce_date'] = r['grade_datetime_et'].dt.tz_localize(None).dt.normalize()
r = r[(r['announce_date'] >= SAMPLE_START) & (r['announce_date'] <= SAMPLE_END)].copy()
r['timing'] = timing_label(r['grade_datetime_et'])

# the clock-time check that decides the day-0 rule (see docstring)
et = r['grade_datetime_et']
hours = et.dt.hour.value_counts().sort_index().rename_axis('hour_et').reset_index(name='n')
hours['share'] = (hours['n'] / hours['n'].sum()).round(4)
hours.to_csv(TABLES / 'rating_time_of_day.csv', index=False)
print('\nrating changes by hour of day (US/Eastern):')
print(hours.to_string(index=False))
print('share exactly at hh:00:00:', round((et.dt.strftime('%M:%S') == '00:00').mean(), 4),
      '| share at 00:00:00:', round((et.dt.strftime('%H:%M:%S') == '00:00:00').mean(), 4))
print('most common clock times:', et.dt.strftime('%H:%M:%S').value_counts().head(5).to_dict())
print('timing:', r['timing'].value_counts().to_dict())

# ---- broker names ----
aliases = load_broker_aliases()
r['broker_raw'] = r['broker_raw'].astype(str).str.strip()
unmapped = sorted(set(r['broker_raw']) - set(aliases))
if unmapped:
    print('WARNING: broker names not in broker_aliases.csv (kept as they are):', unmapped)
r['broker'] = r['broker_raw'].map(aliases).fillna(r['broker_raw'])
print('distinct raw broker names:', r['broker_raw'].nunique(), '-> brokers:', r['broker'].nunique())

# ---- de-duplication, logged (two simple steps) ----
r = r.sort_values(['ticker', 'grade_datetime_et', 'broker', 'broker_raw']).reset_index(drop=True)
n0 = len(r)
# step (a): the same broker, same ticker, same day, same direction is one call recorded twice
#           (usually under two old names of the same broker). Keep the earliest timestamp.
dup = r.duplicated(['ticker', 'broker', 'announce_date', 'direction'], keep='first')
repeats = r[dup]
r = r[~dup].copy()
# step (b): the same broker upgrading AND downgrading the same ticker on the same day: we can't
#           tell which is right, so drop both. n_directions = how many directions that broker
#           gave that ticker that day (1 = normal, 2 = contradictory).
r['n_directions'] = r.groupby(['ticker', 'broker', 'announce_date'])['direction'].transform('nunique')
contradictory = r[r['n_directions'] > 1].drop(columns='n_directions')
r = r[r['n_directions'] == 1].drop(columns='n_directions')
log = pd.concat([repeats.assign(reason='same broker, ticker, day and direction as an earlier row'),
                 contradictory.assign(reason='same broker upgraded and downgraded on one day')])
log.to_csv(PROC / 'ratings_duplicates_dropped.csv', index=False)
print(f'\nde-duplication: {n0} -> {len(r)} rows ({len(repeats)} repeats, {len(contradictory)} contradictory)')

r['event_id'] = (r['ticker'] + '_' + r['announce_date'].dt.strftime('%Y%m%d') + '_'
                 + r['broker'].str.replace(r'[^A-Za-z0-9]+', '', regex=True))
r = r[['event_id', 'ticker', 'broker', 'broker_raw', 'grade_datetime_et', 'announce_date', 'timing',
       'direction', 'from_grade', 'to_grade', 'action']].sort_values(['announce_date', 'ticker', 'broker'])

# checks
assert r['event_id'].is_unique, 'natural key (ticker, day, broker) is not unique'
assert not r.duplicated(['ticker', 'broker', 'announce_date']).any()
assert r['announce_date'].between(SAMPLE_START, SAMPLE_END).all()

r.to_csv(PROC / 'ratings.csv', index=False)
print(r.shape, '| upgrades/downgrades:', r['direction'].value_counts().to_dict(),
      '| firms:', r['ticker'].nunique())

# ---- coverage by ticker and calendar year (Eastern dates), to see holes in Yahoo's history ----
# raw_rows = every raw row (any action: up, down, main, init, reit, ...);
# rating_changes_kept = rows of data/processed/ratings.csv (sample window, after de-duplication)
raw['year'] = pd.to_datetime(raw['grade_datetime'], utc=True).dt.tz_convert('America/New_York').dt.year
raw['date_et'] = (pd.to_datetime(raw['grade_datetime'], utc=True).dt.tz_convert('America/New_York')
                  .dt.strftime('%Y-%m-%d'))
r['year'] = r['announce_date'].dt.year
cov_rows = []
for t in FIRMS:
    for y in range(raw['year'].min(), raw['year'].max() + 1):   # every year, so zero years show up
        rows_ty = raw[(raw['ticker'] == t) & (raw['year'] == y)]
        cov_rows.append(dict(ticker=t, year=y, raw_rows=len(rows_ty),
                             rating_changes_kept=int(((r['ticker'] == t) & (r['year'] == y)).sum()),
                             first_date=rows_ty['date_et'].min() if len(rows_ty) else '',
                             last_date=rows_ty['date_et'].max() if len(rows_ty) else ''))
cov = pd.DataFrame(cov_rows)
cov.to_csv(TABLES / 'ratings_coverage_by_year.csv', index=False)
in_sample = cov[cov['year'].between(int(SAMPLE_START[:4]), int(SAMPLE_END[:4]))]
print('\nticker-years inside the sample with fewer than 5 raw rows (possible holes in Yahoo coverage):')
print(in_sample[in_sample['raw_rows'] < 5].to_string(index=False))
print('raw rows per ticker, largest (Yahoo keeps roughly the last ~1,000):')
print(cov.groupby('ticker')['raw_rows'].sum().sort_values(ascending=False).head(10).to_dict())
