"""Step 2: earnings announcement dates and times for the 50 firms (to flag confounded rating changes).

Source: yf.Ticker(t).get_earnings_dates(limit=100), one raw file per ticker in data/raw/earnings/.
100 rows reach back well before 2020 for every firm, so the whole sample window is covered.

Timing follows the HW6 worked example: a time during market hours is usually Yahoo's placeholder,
so it is replaced by the firm's usual timing (raw label kept in timing_raw). Day 0 of each
announcement is set in 04_build_event_panel.py with the same find_day0 rule as the rating changes,
and announcements outside the price calendar are dropped there (no clamping to the first date).
The usual timing uses the whole sample (so it uses later announcements too); timing_past_only is
the same replacement made with the firm's EARLIER announcements only, for a robustness row.

Output: data/raw/earnings/<TICKER>.csv (as downloaded), data/processed/earnings.csv
"""
import time

import pandas as pd
import yfinance as yf
from _common import (PROC, EARNINGS_DIR, REFRESH, PRICE_START, PRICE_END, firms,
                     download_with_retry, log_manifest, timing_label)

FIRMS = firms()

errors = {}
for t in FIRMS:
    path = EARNINGS_DIR / f'{t}.csv'
    if path.exists() and not REFRESH:
        continue
    d = download_with_retry(lambda: yf.Ticker(t).get_earnings_dates(limit=100), t, errors)
    if d is not None:
        d = d.reset_index()
        d['ticker'] = t
        d.to_csv(path, index=False)
        log_manifest(path, f'yfinance Ticker("{t}").get_earnings_dates(limit=100)', len(d))
        print(t, len(d), 'rows')
    time.sleep(0.5)  # be polite to Yahoo
if errors:
    print('DOWNLOAD FAILURES:', errors)
missing = [t for t in FIRMS if not (EARNINGS_DIR / f'{t}.csv').exists()]
if missing:  # download failed and there is no cached file: stop, never continue with a gap
    raise SystemExit(f'ERROR: earnings download failed and no cached file exists for {missing} '
                     f'({errors}). Nothing was written for them; rerun later (Yahoo rate limit?).')

raw = pd.concat([pd.read_csv(EARNINGS_DIR / f'{t}.csv') for t in FIRMS], ignore_index=True)
raw = raw.rename(columns={'Earnings Date': 'announce_time', 'EPS Estimate': 'eps_estimate',
                          'Reported EPS': 'eps_reported', 'Surprise(%)': 'surprise_pct'})

# timestamps carry an Eastern offset; parse them and keep them in Eastern time
raw['announce_time'] = pd.to_datetime(raw['announce_time'], utc=True).dt.tz_convert('America/New_York')
raw['announce_date'] = raw['announce_time'].dt.tz_localize(None).dt.normalize()

# keep announcements inside the price download (the rest can never be matched to a trading day)
ea = raw[(raw['announce_date'] >= PRICE_START) & (raw['announce_date'] < PRICE_END)].copy()

ea['timing'] = timing_label(ea['announce_time'])
ea['timing_raw'] = ea['timing']
usual = ea[ea['timing'] != 'during_market'].groupby('ticker')['timing'].agg(lambda s: s.mode()[0])
fix = ea['timing'] == 'during_market'
ea.loc[fix, 'timing'] = ea.loc[fix, 'ticker'].map(usual).fillna('during_market')
print('timing replaced by the firm\'s usual timing:', int(fix.sum()), 'announcements')

# Yahoo sometimes lists one announcement twice (e.g. two EPS rows); keep one per firm-day
n0 = len(ea)
ea = ea.sort_values(['ticker', 'announce_time']).drop_duplicates(['ticker', 'announce_date'], keep='first')
print('duplicate firm-days dropped:', n0 - len(ea))

# ---- timing_past_only: the same replacement, using only announcements BEFORE this one ----
# `timing` above uses the firm's most common timing over the whole sample, so a 2021 placeholder
# is filled with information from 2026. Here a placeholder gets the most common timing of the
# firm's EARLIER announcements only (rows are one per firm-day now, sorted by firm and time).
# If the firm has no earlier non-placeholder announcement, the whole-sample value is kept.
ea['timing_past_only'] = ea['timing']
n_no_earlier = 0
for i in ea.index[ea['timing_raw'] == 'during_market']:
    earlier = ea[(ea['ticker'] == ea.loc[i, 'ticker']) & (ea['announce_time'] < ea.loc[i, 'announce_time'])
                 & (ea['timing_raw'] != 'during_market')]
    if len(earlier) > 0:
        ea.loc[i, 'timing_past_only'] = earlier['timing_raw'].mode()[0]
    else:
        n_no_earlier += 1
print('placeholders:', int((ea['timing_raw'] == 'during_market').sum()),
      '| timing differs when only earlier announcements are used:',
      int((ea['timing'] != ea['timing_past_only']).sum()),
      '| no earlier announcement (whole-sample value kept):', n_no_earlier)

ea = ea[['ticker', 'announce_time', 'announce_date', 'timing', 'timing_raw', 'eps_estimate',
         'eps_reported', 'surprise_pct', 'timing_past_only']].reset_index(drop=True)

# checks
assert not ea.duplicated(['ticker', 'announce_date']).any()
per_firm = ea.groupby('ticker').size()
print('announcements per firm in the price window:', per_firm.describe().round(1).to_dict())
print('firms with fewer than 24:', per_firm[per_firm < 24].to_dict())
print('firms with no earnings dates:', sorted(set(FIRMS) - set(ea['ticker'])))

ea.to_csv(PROC / 'earnings.csv', index=False)
print(ea.shape)
