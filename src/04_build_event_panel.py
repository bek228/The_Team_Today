"""Step 4: day 0, the market model, and AR/CAR for every rating change; earnings flags; episodes.

Same logic as the HW6 worked example (03_build_event_panel.py):
  day 0      = first trading day investors could trade on the news (_common.find_day0)
  model      = market model vs SPY, alpha and beta from trading days [-250, -30], >= 150 returns
  AR, CAR    = ret - (alpha + beta * mkt); CAR is the running sum of AR from t = -20
An event whose window is incomplete is dropped, with the reason recorded.

Outputs:
  data/processed/event_panel.csv     one row per rating change x event day (t = -20..+20)
  data/processed/events.csv          one row per rating change (kept), with window CARs, CAR[0,+1],
                                     earnings_in_window (any earnings day 0 in t = -20..+20) and
                                     resid_sd (estimation-window residual sd, for standardized CARs) and
                                     other_call_in_window (another call on the stock 1-2 trading days away)
  data/processed/episodes.csv        one row per ticker x day 0: several brokers moving the same
                                     stock on the same day are ONE price reaction
  data/processed/dropped_events.csv  rating changes not used, and why
  data/processed/earnings_day0.csv   earnings announcements with their day 0
  data/processed/events_day0_next.csv  the same events under the teammates' day-0 rule
                                     (during-market calls -> next day), for robustness only
"""
import numpy as np
import pandas as pd
from _common import (PROC, MKT, EST_WINDOW, EVENT_WINDOW, MIN_EST_DAYS, EARNINGS_WINDOW, WINDOWS,
                     find_day0)

rat = pd.read_csv(PROC / 'ratings.csv', parse_dates=['announce_date'])
ea = pd.read_csv(PROC / 'earnings.csv', parse_dates=['announce_date'])
rets = pd.read_csv(PROC / 'returns.csv', index_col='date', parse_dates=True)
tdays = rets.index  # the trading calendar
N_DAYS = EVENT_WINDOW[1] - EVENT_WINDOW[0] + 1

# ---- earnings day 0, same rule; keep only announcements inside the price calendar ----
ea = ea[(ea['announce_date'] >= tdays[0]) & (ea['announce_date'] <= tdays[-1])].copy()
ea['p0'] = [find_day0(tdays, d, tm) for d, tm in zip(ea['announce_date'], ea['timing'])]
ea = ea[ea['p0'] < len(tdays)].copy()   # an after-close report on the last price day has no day 0 yet
ea['day0'] = tdays[ea['p0']]
ea_pos = ea.groupby('ticker')['p0'].apply(np.array).to_dict()


def nearest_earnings(ticker, p0):
    """Signed trading days from the nearest earnings day 0 (positive = rating AFTER earnings)."""
    pos = ea_pos.get(ticker)
    if pos is None:                     # firm has no earnings dates at all
        return np.nan
    gaps = p0 - pos                     # one gap per earnings date of this firm
    closest = np.abs(gaps).min()
    ties = gaps[np.abs(gaps) == closest]  # usually one gap; two if one report is as far before as another is after
    return int(ties.max())              # on a tie, take the positive one (the rating came after that report)


def earnings_in_event_window(ticker, p0):
    """True if the firm has any earnings day 0 inside the event window t = -20..+20."""
    pos = ea_pos.get(ticker)
    if pos is None:
        return False
    return bool((np.abs(p0 - pos) <= EVENT_WINDOW[1]).any())


def build(rat, during):
    """Day 0, alpha, beta and the 41-day AR/CAR window for every rating change."""
    rows, panels = [], []
    for e in rat.itertuples():
        p0 = find_day0(tdays, e.announce_date, e.timing, during)
        info = dict(event_id=e.event_id, dropped='')
        if p0 + EVENT_WINDOW[1] >= len(tdays):
            info['dropped'] = 'event window not over yet'
            rows.append(info)
            continue
        info['day0'] = tdays[p0]
        if p0 + EST_WINDOW[0] < 0:
            info['dropped'] = 'estimation window starts before the price data'
            rows.append(info)
            continue

        est = rets.iloc[p0 + EST_WINDOW[0]: p0 + EST_WINDOW[1] + 1][[e.ticker, MKT]].dropna()
        if len(est) < MIN_EST_DAYS:
            info['dropped'] = 'short estimation window'
            rows.append(info)
            continue

        # market model: r_i = alpha + beta * r_m
        beta = est[e.ticker].cov(est[MKT]) / est[MKT].var()
        alpha = est[e.ticker].mean() - beta * est[MKT].mean()

        win = rets.iloc[p0 + EVENT_WINDOW[0]: p0 + EVENT_WINDOW[1] + 1][[e.ticker, MKT]].copy()
        win.columns = ['ret', 'mkt']
        if win['ret'].isna().any():
            info['dropped'] = 'missing stock return inside the event window'
            rows.append(info)
            continue
        win['t'] = np.arange(EVENT_WINDOW[0], EVENT_WINDOW[1] + 1)
        win['expected'] = alpha + beta * win['mkt']
        win['AR'] = win['ret'] - win['expected']
        win['CAR'] = win['AR'].cumsum()  # CAR starts accumulating at t = -20
        win['event_id'], win['ticker'] = e.event_id, e.ticker

        # residual standard deviation in the estimation window (how noisy this stock usually is);
        # ddof=2 because two numbers (alpha and beta) were estimated from the same data
        resid = est[e.ticker] - (alpha + beta * est[MKT])

        dfe = nearest_earnings(e.ticker, p0)
        near = pd.notna(dfe) and EARNINGS_WINDOW[0] <= dfe <= EARNINGS_WINDOW[1]
        info.update(alpha=alpha, beta=beta, est_days=len(est), days_from_earnings=dfe,
                    near_earnings=bool(near), ar_0=win.loc[win['t'] == 0, 'AR'].item())
        for name, (lo, hi) in WINDOWS.items():
            col = {'[-20,-2]': 'car_m20_m2', '[-1,+1]': 'car_m1_p1', '[+2,+20]': 'car_p2_p20'}[name]
            info[col] = win.loc[win['t'].between(lo, hi), 'AR'].sum()
        # market-adjusted CAR[-1,+1] (ret - SPY, no model), for the robustness table
        info['car_m1_p1_mktadj'] = (win['ret'] - win['mkt'])[win['t'].between(-1, 1)].sum()
        # CAR[0,+1]: leaves out t = -1, the day before the stamp (robustness)
        info['car_0_p1'] = win.loc[win['t'].between(0, 1), 'AR'].sum()
        # any earnings report inside [-20,+20]? (then CAR[-20,-2] / CAR[+2,+20] may contain it)
        info['earnings_in_window'] = earnings_in_event_window(e.ticker, p0)
        info['resid_sd'] = resid.std(ddof=2)
        rows.append(info)
        panels.append(win.reset_index())

    out = rat.merge(pd.DataFrame(rows), on='event_id', how='left', validate='1:1')
    return out, pd.concat(panels, ignore_index=True)


ev_all, panel = build(rat, during='same_day')
dropped = ev_all[ev_all['dropped'] != '']
ev = ev_all[ev_all['dropped'] == ''].drop(columns='dropped').copy()
ev['n_same_day_calls'] = ev.groupby(['ticker', 'day0'])['event_id'].transform('size')

# other_call_in_window: another rating change on the SAME stock has its day 0 one or two trading
# days away, so the two [-1,+1] windows overlap and the CARs mix two pieces of news
ev['p0'] = tdays.get_indexer(ev['day0'])                      # day 0 as a position in the calendar
day0s_of = ev.groupby('ticker')['p0'].apply(np.unique).to_dict()   # every distinct day 0 per stock


def other_call_nearby(ticker, p0):
    gaps = np.abs(day0s_of[ticker] - p0)      # gap 0 is this episode itself
    return bool(((gaps >= 1) & (gaps <= 2)).any())


ev['other_call_in_window'] = [other_call_nearby(t, p) for t, p in zip(ev['ticker'], ev['p0'])]

cols = ['event_id', 'ticker', 'broker', 'broker_raw', 'grade_datetime_et', 'announce_date', 'timing',
        'day0', 'direction', 'from_grade', 'to_grade', 'near_earnings', 'days_from_earnings',
        'n_same_day_calls', 'alpha', 'beta', 'est_days', 'ar_0', 'car_m1_p1', 'car_m20_m2', 'car_p2_p20',
        'car_m1_p1_mktadj', 'car_0_p1', 'earnings_in_window', 'resid_sd', 'other_call_in_window']
ev = ev[cols].sort_values(['day0', 'ticker', 'broker']).reset_index(drop=True)
panel = panel[['event_id', 'ticker', 'date', 't', 'ret', 'mkt', 'expected', 'AR', 'CAR']]

# ---- episodes: one row per ticker x day 0 ----
def episode_direction(s):
    return s.iloc[0] if s.nunique() == 1 else 'mixed'


same = ['alpha', 'beta', 'near_earnings', 'days_from_earnings', 'ar_0', 'car_m1_p1', 'car_m20_m2',
        'car_p2_p20', 'car_m1_p1_mktadj', 'car_0_p1', 'earnings_in_window', 'resid_sd',
        'other_call_in_window']
g = ev.groupby(['ticker', 'day0'])
assert (g[same].nunique(dropna=False) == 1).all().all(), 'calls on one ticker-day should share one CAR'
episodes = g.agg(direction=('direction', episode_direction), n_calls=('event_id', 'size'),
                 n_upgrades=('direction', lambda s: (s == 'upgrade').sum()),
                 n_downgrades=('direction', lambda s: (s == 'downgrade').sum()),
                 brokers=('broker', lambda s: '; '.join(sorted(s))),
                 **{c: (c, 'first') for c in same}).reset_index()
episodes.insert(0, 'episode_id', episodes['ticker'] + '_' + episodes['day0'].dt.strftime('%Y%m%d'))

# ---- the teammates' day-0 rule, for robustness only ----
ev_next, _ = build(rat, during='next_day')
ev_next = ev_next[ev_next['dropped'] == ''][['event_id', 'ticker', 'direction', 'day0', 'near_earnings',
                                              'ar_0', 'car_m1_p1']]

# checks
assert ev['event_id'].is_unique and episodes['episode_id'].is_unique
assert not panel.duplicated(['event_id', 't']).any()
assert (panel.groupby('event_id').size() == N_DAYS).all(), 'every event needs 41 rows'
assert panel['AR'].notna().all(), 'missing AR inside an event window'
d0 = panel[panel['t'] == 0].merge(ev[['event_id', 'day0']], on='event_id', how='left', validate='1:1')
assert (d0['date'] == d0['day0']).all(), 'event time is misaligned'
assert set(panel['event_id']) == set(ev['event_id'])
assert episodes['n_calls'].sum() == len(ev)
assert (ev['day0'] >= ev['announce_date']).all(), 'day 0 before the announcement: look-ahead'
assert len(ev) + len(dropped) == len(rat)

print('kept', len(ev), 'rating changes,', len(episodes), 'episodes | dropped:',
      dropped['dropped'].value_counts().to_dict())
print('beta range:', ev['beta'].min().round(2), 'to', ev['beta'].max().round(2),
      '| median', ev['beta'].median().round(2))
print('episodes:', episodes['direction'].value_counts().to_dict())
print('near earnings (rating changes):', ev['near_earnings'].mean().round(3),
      '| any earnings in [-20,+20]:', ev['earnings_in_window'].mean().round(3))
print('days_from_earnings, rating changes within +-5 trading days:')
print(ev['days_from_earnings'].value_counts().sort_index().loc[-5:5].to_string())

# fixed 10 decimals: the last bits of a mean or covariance can differ between numpy builds,
# and rounding keeps the CSVs byte-identical across machines (precision lost: < 1e-10)
f = '%.10f'
panel.to_csv(PROC / 'event_panel.csv', index=False, float_format=f)
ev.to_csv(PROC / 'events.csv', index=False, float_format=f)
episodes.to_csv(PROC / 'episodes.csv', index=False, float_format=f)
dropped[['event_id', 'ticker', 'broker', 'announce_date', 'timing', 'direction', 'dropped']].rename(
    columns={'dropped': 'reason'}).to_csv(PROC / 'dropped_events.csv', index=False)
ea[['ticker', 'announce_time', 'announce_date', 'timing', 'timing_raw', 'day0']].to_csv(
    PROC / 'earnings_day0.csv', index=False)
ev_next.to_csv(PROC / 'events_day0_next.csv', index=False, float_format=f)
