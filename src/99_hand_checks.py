"""Step 99: recompute at least one number per pipeline step, a different way, and assert they match.

Each check starts from an earlier file (raw where possible) and does not reuse the pipeline's
functions. docs/hand_checks.md explains each one. If any assert fails, run_all.py stops.
"""
import numpy as np
import pandas as pd
from _common import (RAW, PROC, TABLES, RATINGS_DIR, EARNINGS_DIR, SAMPLE_START, SAMPLE_END, MKT,
                     MIN_BROKER_CALLS)

ev = pd.read_csv(PROC / 'events.csv', parse_dates=['day0', 'announce_date'])
ep = pd.read_csv(PROC / 'episodes.csv', parse_dates=['day0'])
panel = pd.read_csv(PROC / 'event_panel.csv', parse_dates=['date'])
px = pd.read_csv(RAW / 'prices.csv', index_col='date', parse_dates=True)
rets = pd.read_csv(PROC / 'returns.csv', index_col='date', parse_dates=True)
tdays = list(rets.index)

# ---- step 0: the universe is the top 50 priced members by 2020 dollar volume, one class per CIK ----
mem = pd.read_csv(RAW / 'sp500_members_2020-12-31.csv')
dv = pd.read_csv(RAW / 'dollar_volume_2020.csv')
uni = pd.read_csv(RAW / 'universe.csv')
ok = dv[dv['n_days_2020'] >= 200].copy()
cik =dict(zip(mem['Symbol'].str.replace('.', '-', regex=False), mem['CIK']))
cik.update(dict(zip(uni['ticker'], [cik.get(t2.replace('.', '-')) for t2 in uni['ticker_2020']])))
ok['CIK'] = ok['ticker'].map(cik)
top = ok.sort_values('avg_dollar_volume_2020', ascending=False).drop_duplicates('CIK').head(50)
assert list(top['ticker']) == list(uni['ticker']), 'universe does not match the dollar-volume ranking'
print('[0] universe = top 50 by 2020 dollar volume: OK (#1', top['ticker'].iloc[0], ', #50', top['ticker'].iloc[-1], ')')

# ---- step 1: number of rating changes, recounted from the raw per-ticker files ----
aliases = pd.read_csv(RAW / 'broker_aliases.csv')
raw = pd.concat([pd.read_csv(RATINGS_DIR / f'{t}.csv') for t in uni['ticker']])
raw = raw[raw['Action'].isin(['up', 'down'])].copy()
et = pd.to_datetime(raw['GradeDate']).dt.tz_localize('UTC').dt.tz_convert('America/New_York')
raw['day'] = et.dt.date.astype(str)
raw = raw[(raw['day'] >= SAMPLE_START) & (raw['day'] <= SAMPLE_END)]
raw['broker'] = raw['Firm'].str.strip().map(dict(zip(aliases['raw_name'], aliases['broker'])))
n_unique = len(raw.drop_duplicates(['ticker', 'broker', 'day', 'Action']))
assert n_unique == len(ev), (n_unique, len(ev))
print(f'[1] rating changes recounted from raw files: {n_unique} = events.csv rows: OK')

# ---- day 0: every event, by walking the calendar instead of searchsorted ----
# (this one takes the pipeline's timing label as given; the next check starts from the raw stamp)
def day0_by_hand(date, timing):
    if timing == 'after_close':
        return next(d for d in tdays if d > date)
    return next(d for d in tdays if d >= date)  # before the open or during the market: same day


hand = [day0_by_hand(d, tm) for d, tm in zip(ev['announce_date'], ev['timing'])]
assert (pd.Series(hand) == ev['day0']).all(), 'day 0 mismatch'
print(f'[1] day 0 recomputed by walking the calendar for all {len(ev)} events: OK')

# ---- step 1: timing AND day 0 from the raw GradeDate, one call per timing class ----
# Everything here is redone by hand: UTC -> Eastern, the clock rule, the calendar walk (the
# calendar is the date column of the raw prices file), and the event_id.
raw_calendar = list(px.index)
broker_of = dict(zip(aliases['raw_name'], aliases['broker']))


def clock_class(et_time):
    minutes = et_time.hour * 60 + et_time.minute
    if minutes < 9 * 60 + 30:
        return 'before_open'
    if minutes >= 16 * 60:
        return 'after_close'
    return 'during_market'


def walk_calendar(date, timing):
    """First trading day on or after the date; strictly after it for after-close news."""
    if timing == 'after_close':
        return next(d for d in raw_calendar if d > date)
    return next(d for d in raw_calendar if d >= date)


ev_by_id = ev.set_index('event_id')
found = {}
for t in uni['ticker']:
    rows = pd.read_csv(RATINGS_DIR / f'{t}.csv')
    for stamp, firm, action in zip(rows['GradeDate'], rows['Firm'], rows['Action']):
        if action not in ('up', 'down'):
            continue
        et_time = pd.Timestamp(stamp, tz='UTC').tz_convert('America/New_York')
        date = pd.Timestamp(et_time.date())
        if not (pd.Timestamp(SAMPLE_START) <= date <= pd.Timestamp(SAMPLE_END)):
            continue
        cls = clock_class(et_time)
        broker = broker_of.get(firm.strip(), firm.strip())
        event_id = f'{t}_{date:%Y%m%d}_' + ''.join(ch for ch in broker if ch.isalnum())
        if cls not in found and event_id in ev_by_id.index:
            found[cls] = (event_id, et_time, cls, walk_calendar(date, cls))
    if len(found) == 3:
        break
for cls in ['before_open', 'during_market', 'after_close']:
    event_id, et_time, cls_hand, day0_hand = found[cls]
    assert ev_by_id.loc[event_id, 'timing'] == cls_hand, (event_id, 'timing')
    assert ev_by_id.loc[event_id, 'day0'] == day0_hand, (event_id, 'day 0')
    print(f'[1] from raw GradeDate: {event_id} at {et_time:%Y-%m-%d %H:%M} ET ({et_time:%a}) '
          f'-> {cls_hand}, day 0 {day0_hand.date()}: OK')

# ---- step 2: earnings day 0 from raw earnings rows (one after-close firm, one before-open firm) ----
ed = pd.read_csv(PROC / 'earnings_day0.csv', parse_dates=['announce_date', 'day0'])
for t in ['AAPL', 'JPM']:
    rows = pd.read_csv(EARNINGS_DIR / f'{t}.csv')
    stamp = [s for s in rows['Earnings Date'] if s.startswith('2024')][-1]  # first 2024 report (file is newest first)
    et_time = pd.Timestamp(stamp).tz_convert('America/New_York')            # the stamp carries its offset
    cls = clock_class(et_time)
    assert cls != 'during_market', 'pick a stamp outside market hours (those get the firm\'s usual timing)'
    day0_hand = walk_calendar(pd.Timestamp(et_time.date()), cls)
    pipe = ed[(ed['ticker'] == t) & (ed['announce_date'] == pd.Timestamp(et_time.date()))]
    assert len(pipe) == 1 and pipe['day0'].iloc[0] == day0_hand, (t, stamp)
    print(f'[2] {t} earnings stamp {stamp} -> {cls}, day 0 {day0_hand.date()}: OK')

# ---- step 3: one return from the raw adjusted closes ----
d = rets.index[500]
r_hand = px.loc[d, 'AAPL'] / px['AAPL'].shift(1).loc[d] - 1
assert np.isclose(r_hand, rets.loc[d, 'AAPL'], rtol=1e-8), 'return mismatch'
print(f'[3] AAPL return on {d.date()}: {r_hand:.6f} from prices.csv: OK')

# ---- step 4: one event's alpha, beta and AR from the raw closes, OLS via np.polyfit ----
e = ev[(ev['ticker'] == 'AAPL') & (ev['timing'] == 'before_open')].iloc[-1]
r_all = px.pct_change(fill_method=None)
p0 = list(r_all.index).index(e['day0'])
est = r_all.iloc[p0 - 250: p0 - 30 + 1][['AAPL', MKT]].dropna()
b, a = np.polyfit(est[MKT], est['AAPL'], 1)
assert np.allclose([a, b], [e['alpha'], e['beta']], rtol=1e-6, atol=1e-9), 'alpha/beta mismatch'
w = r_all.iloc[p0 - 1: p0 + 2][['AAPL', MKT]]
ar_hand = (w['AAPL'] - (a + b * w[MKT])).values
ar_pipe = panel[(panel['event_id'] == e['event_id']) & panel['t'].between(-1, 1)].sort_values('t')['AR'].values
assert np.allclose(ar_hand, ar_pipe, atol=1e-9) and np.isclose(ar_hand.sum(), e['car_m1_p1'], atol=1e-9)
# the same number is that EPISODE's CAR[-1,+1] in episodes.csv
ep_row = ep[(ep['ticker'] == 'AAPL') & (ep['day0'] == e['day0'])].iloc[0]
assert np.isclose(ar_hand.sum(), ep_row['car_m1_p1'], atol=1e-9)
print(f'[4] {e["event_id"]}: alpha {a:.6f}, beta {b:.4f}, CAR[-1,+1] {100 * ar_hand.sum():.3f}% from raw '
      f'prices.csv = events.csv = episode {ep_row["episode_id"]} in episodes.csv: OK')

# ---- step 4: one near-earnings flag (and earnings_in_window) from raw pieces only ----
# rating day 0 from the raw GradeDate; earnings day 0s from the raw earnings file; both by hand.
e = ev[ev['near_earnings']].iloc[0]       # the event is chosen from events.csv, then rebuilt from raw
rows = pd.read_csv(RATINGS_DIR / f'{e["ticker"]}.csv')
mine = []
for stamp, firm, action in zip(rows['GradeDate'], rows['Firm'], rows['Action']):
    et_time = pd.Timestamp(stamp, tz='UTC').tz_convert('America/New_York')
    if (action in ('up', 'down') and broker_of.get(firm.strip(), firm.strip()) == e['broker']
            and pd.Timestamp(et_time.date()) == e['announce_date']):
        mine.append(et_time)
et_time = min(mine)                        # earliest stamp, as in the pipeline's de-duplication
rating_day0 = walk_calendar(pd.Timestamp(et_time.date()), clock_class(et_time))

erows = pd.read_csv(EARNINGS_DIR / f'{e["ticker"]}.csv')
etimes = [pd.Timestamp(s).tz_convert('America/New_York') for s in erows['Earnings Date']]
etimes = [x for x in etimes if raw_calendar[0] <= pd.Timestamp(x.date()) <= raw_calendar[-1]]
classes = [clock_class(x) for x in etimes]
# Yahoo's during-market times are placeholders: use the firm's usual (most common other) timing
others = [c for c in classes if c != 'during_market']
usual = max(set(others), key=others.count)
assert others.count(usual) > len(others) / 2, 'usual timing is ambiguous; pick another event'
pos = {d: i for i, d in enumerate(raw_calendar)}
earn_day0 = set()
for x, c in zip(etimes, classes):
    c = usual if c == 'during_market' else c
    after = [d for d in raw_calendar if (d > pd.Timestamp(x.date()) if c == 'after_close' else d >= pd.Timestamp(x.date()))]
    if after:
        earn_day0.add(after[0])
gaps = [pos[rating_day0] - pos[d] for d in earn_day0]   # positive = rating after earnings
nearest = min(gaps, key=lambda g: (abs(g), -g))         # nearest; on a tie the positive gap
assert rating_day0 == e['day0'] and nearest == e['days_from_earnings'] and -1 <= nearest <= 2
assert any(abs(g) <= 20 for g in gaps) == e['earnings_in_window']
print(f'[4] {e["event_id"]}: from raw files, day 0 {rating_day0.date()}, {nearest} trading days after '
      f'an earnings day 0 -> near_earnings True, earnings_in_window {e["earnings_in_window"]}: OK')

# ---- step 4: episode counts ----
groups = ev.groupby(['ticker', 'day0'])['direction'].agg(set)
assert len(groups) == len(ep)
n_mixed = sum(len(s) > 1 for s in groups)
assert n_mixed == (ep['direction'] == 'mixed').sum()
print(f'[4] episodes = distinct ticker-days: {len(groups)}, mixed {n_mixed}: OK')

# ---- step 5: the headline number, from the panel's ARs ----
ws = pd.read_csv(TABLES / 'window_summary.csv')
up = ep[ep['direction'] == 'upgrade']
first = ev.sort_values('event_id').groupby(['ticker', 'day0'])['event_id'].first()
ids = [first[(t, d)] for t, d in zip(up['ticker'], up['day0'])]
car = panel[panel['event_id'].isin(ids) & panel['t'].between(-1, 1)].groupby('event_id')['AR'].sum()
row = ws[(ws['sample'] == 'all') & (ws['direction'] == 'upgrade') & (ws['window'] == '[-1,+1]')].iloc[0]
assert np.isclose(100 * car.mean(), row['mean_pct'], atol=1e-4) and len(car) == row['n']
t_hand = car.mean() / (car.std() / np.sqrt(len(car)))
assert np.isclose(t_hand, row['t_stat'], atol=1e-3)
print(f'[5] upgrades CAR[-1,+1] from panel ARs: {100 * car.mean():.4f}%, t = {t_hand:.2f}: OK')

# ---- step 5: the CLEAN headline, with "other call nearby" recomputed by hand from day 0 dates ----
pos = {d: i for i, d in enumerate(tdays)}
ep['p0_hand'] = ep['day0'].map(pos)
nearby = []
for t, p in zip(ep['ticker'], ep['p0_hand']):
    others = ep.loc[ep['ticker'] == t, 'p0_hand']
    nearby.append(any(1 <= abs(p - q) <= 2 for q in others))
assert (pd.Series(nearby, index=ep.index) == ep['other_call_in_window']).all()
for d in ['upgrade', 'downgrade']:
    clean = ep[(ep['direction'] == d) & ~ep['near_earnings'] & ~pd.Series(nearby, index=ep.index)]
    row = ws[(ws['sample'] == 'clean') & (ws['direction'] == d) & (ws['window'] == '[-1,+1]')].iloc[0]
    assert len(clean) == row['n'] and np.isclose(100 * clean['car_m1_p1'].mean(), row['mean_pct'], atol=1e-4)
    print(f'[5] clean {d}s CAR[-1,+1]: {100 * clean["car_m1_p1"].mean():.4f}% (n {len(clean)}): OK')

# ---- step 5: one leaderboard row (headline no_earnings sample) from events.csv ----
lb = pd.read_csv(TABLES / 'broker_leaderboard.csv')
top1 = lb[(lb['sample'] == 'no_earnings') & (lb['direction'] == 'upgrade') & (lb['rank'] == 1)].iloc[0]
calls = ev[(ev['broker'] == top1['broker']) & (ev['direction'] == 'upgrade') & ~ev['near_earnings']]
x = calls['car_m1_p1']
assert len(x) == top1['n'] and len(x) >= MIN_BROKER_CALLS
assert np.isclose(100 * x.mean(), top1['mean_pct'], atol=1e-4)
assert np.isclose(100 * x.std() / np.sqrt(len(x)), top1['se_pct'], atol=1e-4)
print(f'[5] no-earnings leaderboard #1 upgrade broker {top1["broker"]}: n {len(x)}, mean {100 * x.mean():.4f}%: OK')

# same broker's standardized CAR: CAR[-1,+1] / (residual sd x sqrt 3), residual sd rebuilt by polyfit
sl = pd.read_csv(TABLES / 'broker_leaderboard_standardized.csv')
srow = sl[(sl['sample'] == 'no_earnings') & (sl['direction'] == 'upgrade') & (sl['broker'] == top1['broker'])].iloc[0]
e = calls.iloc[0]
p0 = list(r_all.index).index(e['day0'])
est = r_all.iloc[p0 - 250: p0 - 30 + 1][[e['ticker'], MKT]].dropna()
b, a = np.polyfit(est[MKT], est[e['ticker']], 1)
resid = est[e['ticker']] - (a + b * est[MKT])
sd_hand = np.sqrt((resid ** 2).sum() / (len(resid) - 2))
assert np.isclose(sd_hand, e['resid_sd'], rtol=1e-6)
scar = calls['car_m1_p1'] / (calls['resid_sd'] * np.sqrt(3))
assert np.isclose(scar.mean(), srow['mean_scar'], atol=1e-4) and len(scar) == srow['n']
print(f'[5] {e["event_id"]}: residual sd {sd_hand:.5f}; {top1["broker"]} mean SCAR {scar.mean():.4f}: OK')

# ---- step 5: one cell of ar_by_day_timing (no-earnings upgrades, all timings, t = -1) ----
abt = pd.read_csv(TABLES / 'ar_by_day_timing.csv')
cell = abt[(abt['sample'] == 'no_earnings') & (abt['timing'] == 'all') & (abt['direction'] == 'upgrade')
           & (abt['t'] == -1)].iloc[0]
up_ne = up[~up['near_earnings']]
ids = [first[(t, d)] for t, d in zip(up_ne['ticker'], up_ne['day0'])]
ar = panel[panel['event_id'].isin(ids) & (panel['t'] == -1)]['AR']
assert len(ar) == cell['n'] and np.isclose(100 * ar.mean(), cell['mean_ar_pct'], atol=1e-4)
print(f'[5] no-earnings upgrades, mean AR at t = -1: {100 * ar.mean():.4f}% (n {len(ar)}): OK')

print('\nall hand checks passed')
