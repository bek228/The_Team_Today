"""Step 5: every table and figure. Numbers in the tables are in PERCENT (1.25 means 1.25%).

Unit of observation
  - window_summary, car_by_day, robustness: one EPISODE (ticker x day 0). Several brokers moving
    the same stock on the same day share one price reaction, so counting each call would count
    the same return several times. Mixed episodes (upgrade and downgrade on one day) are left
    out; their number is in sample_summary.
  - broker_leaderboard, broker_equality_test: one RATING CHANGE, because the question is about
    each broker's calls. Calls on a multi-broker day share their CAR with the other brokers.

  - ar_by_day_timing: one episode, like car_by_day, but daily AR (not cumulative) by timing class.

Outputs (outputs/tables/): sample_summary, window_summary, car_by_day, ar_by_day_timing,
  largest_t_minus_1_moves_no_earnings, broker_leaderboard (samples no_earnings = headline, all,
  single_call_days), broker_leaderboard_standardized, broker_rank_stability,
  broker_equality_test (ANOVA, Kruskal-Wallis, permutation F), robustness,
  earnings_comparison, earnings_regression (.csv). Headline sample = 'clean' episodes.
  robustness.csv ends with the rows added after the self-audit: clustered standard errors for
  the clean sample, timestamps read as Eastern (from events_eastern.csv), a backward-looking
  clean filter, earnings timing from earlier announcements only, and three estimation-window
  rows. sample_summary.csv ends with the counts that go with them.
Outputs (outputs/figures/): car_upgrade_vs_downgrade.png, car_earnings_split.png, broker_leaderboard.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from _common import (RAW, PROC, TABLES, FIGS, SAMPLE_START, SAMPLE_END, MIN_BROKER_CALLS,
                     EARNINGS_WINDOW, EST_WINDOW, EVENT_WINDOW, WINDOWS, firms)

ev = pd.read_csv(PROC / 'events.csv', parse_dates=['day0'])
ep = pd.read_csv(PROC / 'episodes.csv', parse_dates=['day0'])
panel = pd.read_csv(PROC / 'event_panel.csv')
ev_next = pd.read_csv(PROC / 'events_day0_next.csv', parse_dates=['day0'])
ev_east = pd.read_csv(PROC / 'events_eastern.csv', parse_dates=['day0'])
earn = pd.read_csv(PROC / 'earnings.csv')

DIRS = ['upgrade', 'downgrade']
COLOR = {'upgrade': '#2a78d6', 'downgrade': '#eb6834', 'no_earnings': '#2a78d6', 'near_earnings': '#eb6834'}
WCOL = {'[-20,-2]': 'car_m20_m2', '[-1,+1]': 'car_m1_p1', '[+2,+20]': 'car_p2_p20'}
ep2 = ep[ep['direction'].isin(DIRS)].copy()   # episodes without the mixed ones


def pick(df, sample):
    """all | clean | no_earnings | near_earnings | clean_window | earnings_at_t_minus_1
    | clean_backward | clean_past_only (the last two are robustness versions of clean)"""
    if sample == 'clean':              # HEADLINE: no earnings in [-1,+2], no other call on the stock
        return df[~df['near_earnings'] & ~df['other_call_in_window']]   # 1-2 days away
    if sample == 'clean_backward':     # clean, using only what is known by day 0: drop if the earnings
        # day 0 is on day 0 or 1-2 trading days before it, or another call came 1-2 days before
        return df[~df['days_from_earnings'].isin([0, 1, 2]) & ~df['other_call_before']]
    if sample == 'clean_past_only':    # clean, with earnings timing placeholders from earlier reports only
        return df[~df['near_earnings_past_only'] & ~df['other_call_in_window']]
    if sample == 'no_earnings':        # no earnings day 0 within [-1,+2] of day 0
        return df[~df['near_earnings']]
    if sample == 'near_earnings':
        return df[df['near_earnings']]
    if sample == 'clean_window':       # no earnings day 0 anywhere in [-20,+20]
        return df[~df['earnings_in_window']]
    if sample == 'earnings_at_t_minus_1':  # the firm's earnings day 0 is exactly t = -1
        return df[df['days_from_earnings'] == 1]
    return df


def mean_se(x):
    """n, mean, standard error, t-stat and 95% CI (mean +- 1.96 SE), in percent."""
    x = pd.Series(x).dropna()
    n, m = len(x), x.mean()
    se = x.std() / np.sqrt(n) if n > 1 else np.nan
    return dict(n=n, mean_pct=100 * m, se_pct=100 * se, t_stat=m / se if n > 1 else np.nan,
                ci_lo_pct=100 * (m - 1.96 * se), ci_hi_pct=100 * (m + 1.96 * se))


def save(df, name):
    df.round(4).to_csv(TABLES / name, index=False)


# ---- window_summary: CAR over three windows, by sample and direction ----
# clean_window drops every episode with an earnings report anywhere in [-20,+20], so its
# CAR[-20,-2] and CAR[+2,+20] really are "before" and "after" with no earnings inside.
rows = []
for sample in ['all', 'no_earnings', 'near_earnings', 'clean_window', 'clean']:
    for d in DIRS:
        sub = pick(ep2[ep2['direction'] == d], sample)
        for w, col in WCOL.items():
            rows.append(dict(sample=sample, direction=d, window=w, **mean_se(sub[col])))
window_summary = pd.DataFrame(rows)
save(window_summary, 'window_summary.csv')
print(window_summary.round(2).to_string(index=False))

# ---- car_by_day: the mean CAR path, one episode = its first call's panel rows ----
first_call = ev.sort_values('event_id').groupby(['ticker', 'day0'])['event_id'].first().reset_index()
ep_key = ep2[['ticker', 'day0', 'direction', 'near_earnings', 'other_call_in_window']].merge(first_call, on=['ticker', 'day0'],
                                                                      how='left', validate='1:1')
pan = panel.merge(ep_key[['event_id', 'direction', 'near_earnings', 'other_call_in_window']], on='event_id', how='inner', validate='m:1')
rows = []
for sample in ['all', 'no_earnings', 'near_earnings', 'clean']:
    for (d, t), s in pick(pan, sample).groupby(['direction', 't']):
        r = mean_se(s['CAR'])
        rows.append(dict(sample=sample, direction=d, t=t, n=r['n'], mean_pct=r['mean_pct'],
                         ci_lo_pct=r['ci_lo_pct'], ci_hi_pct=r['ci_hi_pct']))
car_by_day = pd.DataFrame(rows)
car_by_day['direction'] = pd.Categorical(car_by_day['direction'], DIRS)
car_by_day = car_by_day.sort_values(['sample', 'direction', 't'])
save(car_by_day, 'car_by_day.csv')

# ---- ar_by_day_timing: mean AR (not cumulative) on t = -3..+3, by timing of the call ----
# Same unit as car_by_day (one episode = its first call's panel rows). The episode's timing is
# the timing of that first call. If the day-0 rule were wrong, the jump would sit on t = -1 or +1.
timing_of = ev.set_index('event_id')[['timing', 'days_from_earnings', 'earnings_in_window']]
pan_t = pan.merge(timing_of, left_on='event_id', right_index=True, how='left', validate='m:1')
pan_t = pan_t[pan_t['t'].between(-3, 3)]
rows = []
for sample in ['all', 'no_earnings', 'near_earnings', 'earnings_at_t_minus_1']:
    for timing in ['all', 'before_open', 'during_market', 'after_close']:
        sub = pick(pan_t, sample)
        if timing != 'all':
            sub = sub[sub['timing'] == timing]
        for d in DIRS:
            for t in range(-3, 4):
                r = mean_se(sub.loc[(sub['direction'] == d) & (sub['t'] == t), 'AR'])
                rows.append(dict(sample=sample, timing=timing, direction=d, t=t, n=r['n'],
                                 mean_ar_pct=r['mean_pct'], se_pct=r['se_pct'], t_stat=r['t_stat']))
ar_by_day_timing = pd.DataFrame(rows)
save(ar_by_day_timing, 'ar_by_day_timing.csv')
print(ar_by_day_timing[ar_by_day_timing['t'].between(-1, 1)].pivot_table(
    index=['sample', 'timing', 'direction'], columns='t', values='mean_ar_pct').round(2).to_string())

# the ten largest abnormal returns at t = -1 among no-earnings episodes: news BEFORE the call?
big = pan_t[(pan_t['t'] == -1) & ~pan_t['near_earnings']].copy()
big = big.reindex(big['AR'].abs().sort_values(ascending=False).index).head(10)
ar0 = pan_t[pan_t['t'] == 0].set_index('event_id')['AR']
big = pd.DataFrame({'first_call_event_id': big['event_id'], 'direction': big['direction'],
                    'timing': big['timing'], 'ar_t_minus_1_pct': 100 * big['AR'],
                    'ar_t0_pct': 100 * big['event_id'].map(ar0).values})
save(big, 'largest_t_minus_1_moves_no_earnings.csv')

# ---- broker leaderboard: CAR[-1,+1] per rating change, by broker and direction ----
# Shrinkage, in plain English: a broker with few calls has a noisy average, so we pull its
# average toward the average of ALL calls in that direction. How hard we pull depends on two
# things: how noisy the broker's average is (its squared standard error, se^2 = s^2 / n, with s
# the spread of CARs across all calls in that direction), and how much brokers truly differ
# (tau^2 = variance of the ranked brokers' averages minus the part that noise alone explains).
#   weight on the broker's own average  w = tau^2 / (tau^2 + se^2)
#   shrunk mean = grand mean + w * (broker mean - grand mean)
# If brokers do not truly differ (tau^2 = 0), every shrunk mean equals the grand mean.
# Ranking: brokers with n >= MIN_BROKER_CALLS, by shrunk mean in the direction of the call
# (largest first for upgrades, most negative first for downgrades); raw mean breaks ties.
#
# Samples: no_earnings is the HEADLINE leaderboard (a broker that re-rates right after earnings
# would otherwise get credit for the earnings move); all and single_call_days are robustness.
#
# Standardized version (robustness): SCAR = CAR[-1,+1] / (resid_sd * sqrt(3)), i.e. the CAR
# measured in units of the stock's usual 3-day noise, so a call on a volatile stock (e.g. TSLA)
# does not count more just because the stock moves a lot. Ranked by the plain mean SCAR.
#
# Permutation F test (robustness for ANOVA, which assumes roughly normal returns): shuffle the
# broker labels among the ranked brokers' calls 2,000 times; p-value = share of shuffled F
# statistics at least as large as the actual one. Fixed seed, so every rerun gives the same p.
N_SHUFFLES = 2000
LEADERBOARD_SAMPLES = ['all', 'no_earnings', 'single_call_days']  # no_earnings = headline


def board_sample(sample):
    """The calls used for one leaderboard sample."""
    if sample == 'single_call_days':
        return ev[ev['n_same_day_calls'] == 1]
    return pick(ev, sample)


def anova_f(values, labels, k):
    """One-way ANOVA F = (between-group variance) / (within-group variance); labels are 0..k-1."""
    n_per = np.bincount(labels, minlength=k)                           # calls per broker
    means = np.bincount(labels, weights=values, minlength=k) / n_per   # mean per broker
    ss_between = (n_per * (means - values.mean()) ** 2).sum()
    ss_within = ((values - means[labels]) ** 2).sum()
    return (ss_between / (k - 1)) / (ss_within / (len(values) - k))


def permutation_f_pvalue(groups, seed=331):
    """Share of label shuffles whose ANOVA F is at least the actual F."""
    k = len(groups)
    values = np.concatenate(groups)
    labels = np.repeat(np.arange(k), [len(g) for g in groups])  # 0,0,0,1,1,2,... one per call
    actual_f = anova_f(values, labels, k)
    assert np.isclose(actual_f, stats.f_oneway(*groups).statistic)  # same F as scipy
    rng = np.random.default_rng(seed)
    n_bigger = 0
    for _ in range(N_SHUFFLES):
        shuffled = rng.permutation(labels)      # brokers' names randomly reassigned to the calls
        if anova_f(values, shuffled, k) >= actual_f:
            n_bigger += 1
    return actual_f, n_bigger / N_SHUFFLES


boards, tests, std_boards = [], [], []
for sample in LEADERBOARD_SAMPLES:
    base = board_sample(sample)
    for d in DIRS:
        sub = base[base['direction'] == d]
        grand, s_all = sub['car_m1_p1'].mean(), sub['car_m1_p1'].std()
        b = pd.DataFrame([dict(broker=k, **mean_se(g['car_m1_p1']),
                               share_near_earnings_pct=100 * g['near_earnings'].mean())
                          for k, g in sub.groupby('broker')])
        b['meets_min_n'] = b['n'] >= MIN_BROKER_CALLS
        ranked = b['meets_min_n']

        # shrinkage (see the comment block above), step by step:
        se2 = (s_all / np.sqrt(b['n'])) ** 2                      # noise in each broker's average
        spread = (b.loc[ranked, 'mean_pct'] / 100).var()          # how much ranked averages differ
        tau2 = max(0.0, spread - se2[ranked].mean())              # ... minus what noise alone explains
        w = tau2 / (tau2 + se2)                                   # weight on the broker's own average
        b['shrunk_mean_pct'] = 100 * (grand + w * (b['mean_pct'] / 100 - grand))

        # rank: upgrades largest first, downgrades most negative first
        best_first = (d == 'downgrade')   # ascending sort puts the most negative first
        order = b[ranked].sort_values(['shrunk_mean_pct', 'mean_pct'], ascending=best_first)
        b['rank'] = pd.Series(np.arange(1, len(order) + 1), index=order.index)
        b.insert(0, 'direction', d)
        b.insert(0, 'sample', sample)
        print(f'{sample:16s} {d:9s}: {ranked.sum()} ranked brokers, tau = {100 * np.sqrt(tau2):.2f} pp, '
              f'grand mean {100 * grand:.2f}%')
        boards.append(b)

        # standardized leaderboard: same calls, CAR in units of the stock's own 3-day noise
        scar = sub['car_m1_p1'] / (sub['resid_sd'] * np.sqrt(3))
        sb = []
        for k, g in scar.groupby(sub['broker']):
            n, m = len(g), g.mean()
            se = g.std() / np.sqrt(n) if n > 1 else np.nan
            sb.append(dict(sample=sample, broker=k, direction=d, n=n, mean_scar=m, se_scar=se,
                           t_stat=m / se if n > 1 else np.nan, meets_min_n=n >= MIN_BROKER_CALLS))
        sb = pd.DataFrame(sb)
        s_order = sb[sb['meets_min_n']].sort_values('mean_scar', ascending=best_first)
        sb['rank'] = pd.Series(np.arange(1, len(s_order) + 1), index=s_order.index)
        std_boards.append(sb)

        # joint tests: do all ranked brokers have the same mean CAR[-1,+1]?
        groups = [g['car_m1_p1'].values for k, g in sub.groupby('broker') if len(g) >= MIN_BROKER_CALLS]
        f, pf = stats.f_oneway(*groups)
        h, ph = stats.kruskal(*groups)
        f_perm, p_perm = permutation_f_pvalue(groups)
        n_obs = sum(len(g) for g in groups)
        common = dict(sample=sample, direction=d, n_brokers=len(groups), n_obs=n_obs)
        tests.append(dict(**common, test='one-way ANOVA F', statistic=f, p_value=pf, tau_pct=100 * np.sqrt(tau2)))
        tests.append(dict(**common, test='Kruskal-Wallis H', statistic=h, p_value=ph, tau_pct=100 * np.sqrt(tau2)))
        tests.append(dict(**common, test=f'permutation F ({N_SHUFFLES} label shuffles)', statistic=f_perm,
                          p_value=p_perm, tau_pct=100 * np.sqrt(tau2)))

board = pd.concat(boards, ignore_index=True)
board['rank'] = board['rank'].astype('Int64')
board = board.sort_values(['sample', 'direction', 'rank', 'n'], ascending=[True, False, True, False])
board = board[['sample', 'broker', 'direction', 'n', 'mean_pct', 'se_pct', 't_stat', 'ci_lo_pct',
               'ci_hi_pct', 'shrunk_mean_pct', 'rank', 'meets_min_n', 'share_near_earnings_pct']]
save(board, 'broker_leaderboard.csv')
equality = pd.DataFrame(tests)[['sample', 'direction', 'test', 'n_brokers', 'n_obs', 'statistic', 'p_value',
                                 'tau_pct']]
save(equality, 'broker_equality_test.csv')
print(equality.round(3).to_string(index=False))

std_board = pd.concat(std_boards, ignore_index=True)
std_board['rank'] = std_board['rank'].astype('Int64')
std_board = std_board.sort_values(['sample', 'direction', 'rank', 'n'], ascending=[True, False, True, False])
std_board = std_board[['sample', 'broker', 'direction', 'n', 'mean_scar', 'se_scar', 't_stat', 'rank',
                       'meets_min_n']]
save(std_board, 'broker_leaderboard_standardized.csv')

# how much do ranks move? Spearman correlation of the two rankings, brokers ranked in both
rows = []
for sample in LEADERBOARD_SAMPLES:
    for d in DIRS:
        raw_r = board[(board['sample'] == sample) & (board['direction'] == d)].set_index('broker')['rank']
        std_r = std_board[(std_board['sample'] == sample) & (std_board['direction'] == d)].set_index('broker')['rank']
        both = pd.concat([raw_r, std_r], axis=1, keys=['raw', 'std']).dropna().astype(float)
        rho = stats.spearmanr(both['raw'], both['std']).statistic
        rows.append(dict(sample=sample, direction=d, n_brokers=len(both), spearman_rho=rho,
                         same_rank_1=raw_r.idxmin() == std_r.idxmin()))
rank_stability = pd.DataFrame(rows)
save(rank_stability, 'broker_rank_stability.csv')
print(rank_stability.round(3).to_string(index=False))

# calls per broker: why MIN_BROKER_CALLS = 10 (saved in sample_summary.csv below)
calls = ev.groupby(['broker', 'direction']).size()
print('\ncalls per broker x direction:', calls.describe().round(1).to_dict())
print('broker-directions with n >= MIN_BROKER_CALLS:', (calls >= MIN_BROKER_CALLS).sum(), 'of', len(calls),
      '| their share of all calls:', round(calls[calls >= MIN_BROKER_CALLS].sum() / calls.sum(), 3))
print('SE of a broker mean at n = 10 (pp):', round(100 * ev['car_m1_p1'].std() / np.sqrt(10), 2))

# does the 'all' leaderboard reward brokers that re-rate right after earnings? correlation, across
# ranked brokers, between |mean CAR| and the broker's share of near-earnings calls
corr_near = {}
for d in DIRS:
    s = board[(board['sample'] == 'all') & (board['direction'] == d) & board['meets_min_n']]
    corr_near[d] = s['mean_pct'].abs().corr(s['share_near_earnings_pct'])
print('corr(|mean CAR|, share near earnings), all sample:', {k: round(v, 3) for k, v in corr_near.items()})

# ---- robustness: headline CAR[-1,+1] by direction under alternatives (unit = episode) ----
ep_next = (ev_next.groupby(['ticker', 'day0'])
           .agg(direction=('direction', lambda s: s.iloc[0] if s.nunique() == 1 else 'mixed'),
                car_m1_p1=('car_m1_p1', 'first')).reset_index())
specs = {
    'all episodes: market model, day0 same-day rule': (ep2, 'car_m1_p1'),
    'market-adjusted (ret - SPY)': (ep2, 'car_m1_p1_mktadj'),
    'day0: during-market calls -> next day (prototype rule)': (ep_next[ep_next['direction'].isin(DIRS)], 'car_m1_p1'),
    'excluding near-earnings': (ep2[~ep2['near_earnings']], 'car_m1_p1'),
    'excluding multi-broker days': (ep2[ep2['n_calls'] == 1], 'car_m1_p1'),
    'unit = rating change (not episode)': (ev, 'car_m1_p1'),
    # CAR[0,+1] leaves out t = -1, the day before Yahoo's timestamp
    'CAR[0,+1] instead of CAR[-1,+1], excluding near-earnings': (ep2[~ep2['near_earnings']], 'car_0_p1'),
    'clean (headline): no earnings in [-1,+2], no other call within 2 days': (pick(ep2, 'clean'), 'car_m1_p1'),
}
rows = []
for spec, (df, col) in specs.items():
    for d in DIRS:
        r = mean_se(df.loc[df['direction'] == d, col])
        rows.append(dict(spec=spec, direction=d, n=r['n'], mean_pct=r['mean_pct'], se_pct=r['se_pct'],
                         t_stat=r['t_stat']))
for d in DIRS:  # same mean, standard errors clustered by day 0 (calendar day)
    s = ep2[ep2['direction'] == d]
    fit = sm.OLS(s['car_m1_p1'].values, np.ones(len(s))).fit(
        cov_type='cluster', cov_kwds={'groups': pd.factorize(s['day0'])[0]})
    rows.append(dict(spec='SE clustered by day0', direction=d, n=len(s), mean_pct=100 * fit.params[0],
                     se_pct=100 * fit.bse[0], t_stat=fit.tvalues[0]))

# rows added after the self-audit; they come after the rows above, which do not move
# the clean headline with clustered standard errors: by day 0, then two-way by stock and day 0
clean = pick(ep2, 'clean')
for spec, two_way in [('clean (headline), SE clustered by day0', False),
                      ('clean (headline), SE clustered two-way by stock and day0', True)]:
    for d in DIRS:
        s = clean[clean['direction'] == d]
        day_codes = pd.factorize(s['day0'])[0]        # 0, 1, 2, ... one number per calendar day
        stock_codes = pd.factorize(s['ticker'])[0]    # one number per stock
        groups = np.column_stack([stock_codes, day_codes]) if two_way else day_codes
        fit = sm.OLS(s['car_m1_p1'].values, np.ones(len(s))).fit(cov_type='cluster', cov_kwds={'groups': groups})
        rows.append(dict(spec=spec, direction=d, n=len(s), mean_pct=100 * fit.params[0],
                         se_pct=100 * fit.bse[0], t_stat=fit.tvalues[0]))

# Yahoo's time stamps read as Eastern instead of UTC: episodes rebuilt from events_eastern.csv
ep_east = (ev_east.groupby(['ticker', 'day0'])
           .agg(direction=('direction', lambda s: s.iloc[0] if s.nunique() == 1 else 'mixed'),
                near_earnings=('near_earnings', 'first'),
                other_call_in_window=('other_call_in_window', 'first'),
                car_m1_p1=('car_m1_p1', 'first')).reset_index())
ep_east = ep_east[ep_east['direction'].isin(DIRS)]
more_specs = {
    'timestamps read as Eastern (not UTC): all episodes': (ep_east, 'car_m1_p1'),
    'timestamps read as Eastern (not UTC): clean': (pick(ep_east, 'clean'), 'car_m1_p1'),
    'clean, backward-looking filter: earnings day 0 at t = -2..0, other call at t = -2..-1':
        (pick(ep2, 'clean_backward'), 'car_m1_p1'),
    'clean, earnings timing placeholders from earlier announcements only':
        (pick(ep2, 'clean_past_only'), 'car_m1_p1'),
    # estimation window [-250,-30]: first drop the episodes whose window contains other news ...
    'clean, no other rating change in the estimation window': (clean[~clean['est_has_other_call']], 'car_m1_p1'),
    'clean, no earnings day and no other rating change in the estimation window':
        (clean[~clean['est_has_other_call'] & ~clean['est_has_earnings']], 'car_m1_p1'),
    # ... then keep the episodes and take those days out of the estimation window instead
    'clean, market model estimated without earnings and rating-change days': (clean, 'car_m1_p1_cleanest'),
}
for spec, (df, col) in more_specs.items():
    for d in DIRS:
        r = mean_se(df.loc[df['direction'] == d, col])   # n can be 0: the row is still written, empty
        rows.append(dict(spec=spec, direction=d, n=r['n'], mean_pct=r['mean_pct'], se_pct=r['se_pct'],
                         t_stat=r['t_stat']))
robust = pd.DataFrame(rows)
save(robust, 'robustness.csv')
print(robust.round(2).to_string(index=False))

# ---- earnings_comparison: CAR[-1,+1] by direction, with and without earnings overlap ----
# unit = episode (mixed left out); overlap = earnings day 0 within [-1,+2] of the rating's day 0
rows = []
for d in DIRS:
    for label, overlap in [('no earnings overlap', False), ('earnings overlap', True)]:
        sub = ep2[(ep2['direction'] == d) & (ep2['near_earnings'] == overlap)]
        rows.append(dict(direction=d, earnings=label, **mean_se(sub['car_m1_p1'])))
earnings_comparison = pd.DataFrame(rows)
save(earnings_comparison, 'earnings_comparison.csv')
print(earnings_comparison.round(2).to_string(index=False))

# ---- earnings_regression: direction x earnings in one regression, SE clustered by stock ----
# CAR[-1,+1] (percent) = b0 + b1*upgrade + b2*near_earnings + b3*upgrade*near_earnings
#   raw CAR model:  b0 = mean CAR of downgrades not near earnings
#                   b1 = upgrades minus downgrades, not near earnings
#                   b2 = how much earnings shift the downgrade CAR (more negative = bigger drop)
#                   b3 = how much MORE earnings shift the upgrade CAR than the downgrade CAR
#   signed CAR model (CAR for upgrades, minus CAR for downgrades, so "reaction in the
#   direction of the call" is positive for both):
#                   b0 = size of the downgrade reaction, not near earnings
#                   b1 = how much bigger the upgrade reaction is than the downgrade one
#                   b2 = how much bigger the downgrade reaction is near earnings
#                   b3 = difference between upgrades and downgrades in that earnings boost
X = pd.DataFrame({'const': 1.0,
                  'upgrade': (ep2['direction'] == 'upgrade').astype(float),
                  'near_earnings': ep2['near_earnings'].astype(float)})
X['upgrade_x_near_earnings'] = X['upgrade'] * X['near_earnings']
sign = np.where(ep2['direction'] == 'upgrade', 1.0, -1.0)
clusters = pd.factorize(ep2['ticker'])[0]           # one cluster per stock
rows = []
for model, y in [('CAR[-1,+1] (%)', 100 * ep2['car_m1_p1']), ('signed CAR[-1,+1] (%)', 100 * sign * ep2['car_m1_p1'])]:
    fit = sm.OLS(y.values, X.values).fit(cov_type='cluster', cov_kwds={'groups': clusters})
    for i, term in enumerate(X.columns):
        rows.append(dict(model=model, term=term, coef=fit.params[i], se=fit.bse[i], t_stat=fit.tvalues[i],
                         p_value=fit.pvalues[i], n=len(y), n_clusters=len(set(clusters))))
earnings_regression = pd.DataFrame(rows)
save(earnings_regression, 'earnings_regression.csv')
print(earnings_regression.round(3).to_string(index=False))

# ---- sample_summary ----
man = pd.read_csv(RAW / 'MANIFEST.csv')
pulled = man.loc[man['file'].str.startswith('data/raw/ratings/'), 'pulled_utc'].str[:10]
ranked_all = board[(board['sample'] == 'all') & board['meets_min_n']]
ranked_ne = board[(board['sample'] == 'no_earnings') & board['meets_min_n']]
members_dropped = pd.read_csv(RAW / 'universe_dropped.csv')

# pieces for the counts added after the self-audit (the last block of the list below)
# day 0 of each call in the main run next to its day 0 when the stamps are read as Eastern
east = ev[['event_id', 'day0']].merge(ev_east[['event_id', 'day0']], on='event_id', how='left',
                                      suffixes=('', '_eastern'), validate='1:1')
# earnings timing placeholders; earnings.csv is sorted by firm and time, so the running count of
# real (non-placeholder) timings tells whether a placeholder has an earlier real one to learn from
placeholder = earn['timing_raw'] == 'during_market'
real_so_far = (~placeholder).groupby(earn['ticker']).cumsum()
either = ep2['est_has_earnings'] | ep2['est_has_other_call']
either_clean = clean['est_has_earnings'] | clean['est_has_other_call']
# leaderboard unit = rating change: how many calls sit on mixed days or share their CAR
on_mixed_day = ev.groupby(['ticker', 'day0'])['direction'].transform('nunique') > 1
ne_calls = pick(ev, 'no_earnings')

summary = [
    ('n_firms', len(firms())),
    ('n_firms_with_rating_changes', ev['ticker'].nunique()),
    ('n_rating_changes', len(ev)),
    ('n_upgrades', (ev['direction'] == 'upgrade').sum()),
    ('n_downgrades', (ev['direction'] == 'downgrade').sum()),
    ('n_rating_changes_dropped', len(pd.read_csv(PROC / 'dropped_events.csv'))),
    ('n_duplicate_rows_removed', len(pd.read_csv(PROC / 'ratings_duplicates_dropped.csv'))),
    ('n_episodes', len(ep)),
    ('n_episodes_upgrade', (ep['direction'] == 'upgrade').sum()),
    ('n_episodes_downgrade', (ep['direction'] == 'downgrade').sum()),
    ('n_episodes_mixed_excluded', (ep['direction'] == 'mixed').sum()),
    ('n_episodes_multi_broker', (ep['n_calls'] > 1).sum()),
    ('n_brokers', ev['broker'].nunique()),
    ('n_brokers_ranked', ranked_all['broker'].nunique()),
    ('n_brokers_ranked_upgrade', (ranked_all['direction'] == 'upgrade').sum()),
    ('n_brokers_ranked_downgrade', (ranked_all['direction'] == 'downgrade').sum()),
    ('min_broker_calls', MIN_BROKER_CALLS),
    ('share_near_earnings', round(ev['near_earnings'].mean(), 4)),
    ('share_episodes_near_earnings', round(ep2['near_earnings'].mean(), 4)),
    ('earnings_window_trading_days', f'[{EARNINGS_WINDOW[0]},+{EARNINGS_WINDOW[1]}]'),
    ('share_before_open', round((ev['timing'] == 'before_open').mean(), 4)),
    ('share_during_market', round((ev['timing'] == 'during_market').mean(), 4)),
    ('share_after_close', round((ev['timing'] == 'after_close').mean(), 4)),
    ('sample_start', SAMPLE_START),
    ('sample_end', SAMPLE_END),
    ('first_day0', ev['day0'].min().date()),
    ('last_day0', ev['day0'].max().date()),
    ('data_pull_date', f'{pulled.min()} to {pulled.max()}' if pulled.min() != pulled.max() else pulled.min()),
    ('market_model', f'OLS vs SPY, estimation window {EST_WINDOW}, event window {EVENT_WINDOW}'),
    ('day0_rule', 'before 09:30 ET and during market -> same trading day; at/after 16:00 -> next trading day'),
    ('median_beta', round(ev['beta'].median(), 3)),
    # added later; kept at the end so the rows above do not move
    ('n_sp500_members_2020', len(pd.read_csv(RAW / 'sp500_members_2020-12-31.csv'))),
    ('n_members_no_yahoo_prices', (members_dropped['n_days_2020'] == 0).sum()),
    ('n_members_short_2020_history', members_dropped['n_days_2020'].between(1, 199).sum()),
    ('n_extra_share_classes', (members_dropped['n_days_2020'] >= 200).sum()),
    ('share_episodes_earnings_in_window', round(ep2['earnings_in_window'].mean(), 4)),
    ('n_broker_directions', len(calls)),
    ('median_calls_per_broker_direction', calls.median()),
    ('n_broker_directions_with_min_calls', (calls >= MIN_BROKER_CALLS).sum()),
    ('share_calls_by_broker_directions_with_min_calls',
     round(calls[calls >= MIN_BROKER_CALLS].sum() / calls.sum(), 4)),
    ('se_of_broker_mean_at_n10_pp', round(100 * ev['car_m1_p1'].std() / np.sqrt(10), 4)),
    ('n_brokers_ranked_upgrade_no_earnings', (ranked_ne['direction'] == 'upgrade').sum()),
    ('n_brokers_ranked_downgrade_no_earnings', (ranked_ne['direction'] == 'downgrade').sum()),
    ('corr_abs_mean_car_vs_share_near_earnings_upgrade_all', round(corr_near['upgrade'], 4)),
    ('corr_abs_mean_car_vs_share_near_earnings_downgrade_all', round(corr_near['downgrade'], 4)),
    # the dashed line in broker_leaderboard.png: mean CAR[-1,+1] over all no-earnings calls (percent)
    ('mean_car_m1_p1_pct_no_earnings_calls_upgrade',
     round(100 * pick(ev, 'no_earnings').query('direction == "upgrade"')['car_m1_p1'].mean(), 4)),
    ('mean_car_m1_p1_pct_no_earnings_calls_downgrade',
     round(100 * pick(ev, 'no_earnings').query('direction == "downgrade"')['car_m1_p1'].mean(), 4)),
    # added after the self-audit; kept at the end so the rows above do not move
    # timestamps read as Eastern instead of UTC: calls whose day 0 is a different day
    ('n_rating_changes_day0_moves_if_eastern', (east['day0'] != east['day0_eastern']).sum()),
    # earnings timing placeholders filled from earlier announcements only (timing_past_only)
    ('n_earnings_timing_placeholders', placeholder.sum()),
    ('n_earnings_timing_changed_past_only', (earn['timing'] != earn['timing_past_only']).sum()),
    ('n_earnings_placeholders_no_earlier_announcement', (placeholder & (real_so_far == 0)).sum()),
    ('n_near_earnings_flags_changed_past_only', (ev['near_earnings'] != ev['near_earnings_past_only']).sum()),
    ('n_episodes_near_earnings_flag_changed_past_only',
     (ep2['near_earnings'] != ep2['near_earnings_past_only']).sum()),
    # estimation window [-250,-30]: episodes (mixed left out) with other news of the stock inside it
    ('n_episodes_est_window_has_earnings', ep2['est_has_earnings'].sum()),
    ('n_episodes_est_window_has_other_rating_change', ep2['est_has_other_call'].sum()),
    ('n_episodes_est_window_has_either', either.sum()),
    ('n_clean_episodes_est_window_has_earnings', clean['est_has_earnings'].sum()),
    ('n_clean_episodes_est_window_has_other_rating_change', clean['est_has_other_call'].sum()),
    ('n_clean_episodes_est_window_has_either', either_clean.sum()),
    ('n_episodes_dropped_cleaned_estimation_window', ep2['car_m1_p1_cleanest'].isna().sum()),
    # broker leaderboard (unit = rating change): calls on mixed days and on multi-broker days
    ('n_calls_on_mixed_days', on_mixed_day.sum()),
    ('n_calls_no_earnings_leaderboard', len(ne_calls)),
    ('n_calls_on_mixed_days_no_earnings_leaderboard', on_mixed_day[ne_calls.index].sum()),
    ('n_calls_on_multi_broker_days_no_earnings_leaderboard', (ne_calls['n_same_day_calls'] > 1).sum()),
]
pd.DataFrame(summary, columns=['metric', 'value']).to_csv(TABLES / 'sample_summary.csv', index=False)
print(pd.DataFrame(summary, columns=['metric', 'value']).to_string(index=False))


# ---- figures ----
def car_lines(ax, stats_df, key_col, keys, labels):
    for k, lab in zip(keys, labels):
        s = stats_df[stats_df[key_col] == k]
        ax.plot(s['t'], s['mean_pct'], color=COLOR[k], lw=2, label=f'{lab} (n={s["n"].iloc[0]})')
        ax.fill_between(s['t'], s['ci_lo_pct'], s['ci_hi_pct'], color=COLOR[k], alpha=0.18, lw=0)
    ax.axvline(0, color='gray', ls=':')
    ax.axhline(0, color='gray', lw=0.8)
    ax.set_xlabel('Trading days relative to the rating change (day 0)')
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)


fig, ax = plt.subplots(figsize=(8, 4.5))
car_lines(ax, car_by_day[car_by_day['sample'] == 'clean'], 'direction', DIRS, ['Upgrades', 'Downgrades'])
ax.set_ylabel('Average CAR from t = -20 (%)')
ax.set_title('Upgrades vs. downgrades, CLEAN episodes (no earnings nearby, no other call within 2 days)\n'
             '50 large firms, 2021-2026, 95% bands', fontsize=10)
fig.tight_layout()
fig.savefig(FIGS / 'car_upgrade_vs_downgrade.png', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
for ax, d in zip(axes, DIRS):
    s = car_by_day[(car_by_day['direction'] == d) & (car_by_day['sample'] != 'all')]
    car_lines(ax, s, 'sample', ['no_earnings', 'near_earnings'],
              ['No earnings nearby', f'Within [{EARNINGS_WINDOW[0]},+{EARNINGS_WINDOW[1]}] days of earnings'])
    ax.set_title(f'{d.capitalize()}s')
axes[0].set_ylabel('Average CAR from t = -20 (%)')
fig.suptitle('Rating changes right after earnings vs. the rest (95% bands)')
fig.tight_layout()
fig.savefig(FIGS / 'car_earnings_split.png', dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(12, 7))
for ax, d in zip(axes, DIRS):
    # headline leaderboard = calls NOT near earnings
    s = board[(board['sample'] == 'no_earnings') & (board['direction'] == d) & board['meets_min_n']]
    s = s.sort_values('rank', ascending=False)   # rank 1 ends up at the top of the plot
    y = np.arange(len(s))
    ax.errorbar(s['mean_pct'], y, xerr=[s['mean_pct'] - s['ci_lo_pct'], s['ci_hi_pct'] - s['mean_pct']],
                fmt='o', color=COLOR[d], ms=5, capsize=2, lw=1.2, label='raw mean, 95% CI')
    ax.plot(s['shrunk_mean_pct'], y, 'D', color='black', ms=4, label='shrunk mean (ranking)')
    ne = pick(ev, 'no_earnings')
    gm = ne.loc[ne['direction'] == d, 'car_m1_p1'].mean() * 100
    ax.axvline(gm, color='gray', ls='--', lw=1, label=f'all no-earnings {d}s: {gm:.2f}%')
    ax.axvline(0, color='gray', lw=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels([f'{b} (n={n})' for b, n in zip(s['broker'], s['n'])], fontsize=8)
    ax.set_xlabel('CAR[-1,+1] per rating change (%)')
    ax.set_title(f'{d.capitalize()}s: brokers with >= {MIN_BROKER_CALLS} calls')
    ax.grid(alpha=0.2, axis='x')
    ax.legend(frameon=False, fontsize=8, loc='lower right' if d == 'upgrade' else 'lower left')
fig.suptitle('Does the broker matter? Calls NOT near earnings (no_earnings sample)\n'
             'ranked by shrunk mean, rank 1 at the top')
fig.tight_layout()
fig.savefig(FIGS / 'broker_leaderboard.png', dpi=150)
plt.close(fig)
print('figures saved')

# ---- results block in README.md, written from the tables above (never typed by hand) ----
def fmt(r):
    return f'{r["mean_pct"]:+.2f}% (t = {r["t_stat"]:.1f}, n = {r["n"]})'


# headline first: clean episodes, with all episodes and near-earnings episodes next to them
ws = window_summary[window_summary['window'] == '[-1,+1]'].set_index(['sample', 'direction'])
lines = ['**Headline: CAR[-1,+1] of clean episodes** (no earnings day 0 within [-1,+2] trading days, no other',
         'rating change on the same stock within 2 trading days, mixed days left out), next to all and near-earnings episodes:',
         '', '| direction | clean (headline) | all episodes | near earnings |', '|---|---|---|---|']
for d in DIRS:
    lines.append(f'| {d} | **{fmt(ws.loc[("clean", d)])}** | {fmt(ws.loc[("all", d)])} | {fmt(ws.loc[("near_earnings", d)])} |')
lines += ['', 'All samples and windows (`clean_window` = no earnings day 0 anywhere in [-20,+20], the stricter '
          'sample for the long windows):', '',
          '| sample | direction | CAR[-20,-2] | CAR[-1,+1] | CAR[+2,+20] |', '|---|---|---|---|---|']
for sample in ['clean', 'all', 'no_earnings', 'near_earnings', 'clean_window']:
    for d in DIRS:
        s = window_summary[(window_summary['sample'] == sample) & (window_summary['direction'] == d)].set_index('window')
        lines.append(f'| {sample} | {d} | ' + ' | '.join(fmt(s.loc[w]) for w in WINDOWS) + ' |')
perm_test = f'permutation F ({N_SHUFFLES} label shuffles)'
lines += ['', 'Do all ranked brokers (n >= MIN_BROKER_CALLS) have the same mean CAR[-1,+1] per call? '
          'p-values from `broker_equality_test.csv`:', '',
          '| sample | direction | brokers | ANOVA F p-value | permutation F p-value | Kruskal-Wallis p-value |',
          '|---|---|---|---|---|---|']
for sample in LEADERBOARD_SAMPLES:
    for d in DIRS:
        q = equality[(equality['sample'] == sample) & (equality['direction'] == d)].set_index('test')
        lines.append(f'| {sample} | {d} | {q["n_brokers"].iloc[0]} | {q.loc["one-way ANOVA F", "p_value"]:.3f} '
                     f'| {q.loc[perm_test, "p_value"]:.3f} | {q.loc["Kruskal-Wallis H", "p_value"]:.3f} |')
block = ('<!-- RESULTS:START (written by src/05_results.py; do not edit by hand) -->\n'
         + '\n'.join(lines) + '\n<!-- RESULTS:END -->')
readme = RAW.parents[1] / 'README.md'
text = readme.read_text(encoding='utf-8')
start, end = text.find('<!-- RESULTS:START'), text.find('<!-- RESULTS:END -->')
# fail loudly instead of silently skipping: the README numbers must come from this script
assert start >= 0 and end > start, 'README.md is missing the RESULTS:START / RESULTS:END markers'
readme.write_text(text[:start] + block + text[end + len('<!-- RESULTS:END -->'):], encoding='utf-8')
print('README results block updated')
