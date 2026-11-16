# Specifications tried

Every specification that was run on this project and looked at, including the HW8 prototype's.
Nothing run has been left off. CAR numbers are in percent; t-stats in parentheses. "Ep." = episode
(one ticker x day 0); "call" = one rating change.

**Count: 31 specifications** (7 in the HW8 prototype, 24 in the final pipeline), plus 5 diagnostics
that only checked the data or explained a choice (D1-D5). Of the 24 final ones, 1 is the headline (F22, clean episodes; F1 was the headline before the instructor's audit);
the others are reported as windows, splits, robustness or broker analysis, and all of them are in
`outputs/tables/`. The equality tests (F14, F17) are 18 p-values (3 tests x 2 directions x 3 samples),
all reported.

## HW8 prototype (teammates; `dev/pipeline.py`, outputs in `dev/prototype_outputs/`)

Common setup: 5 hand-picked firms (AAPL, MSFT, AMZN, JPM, NVDA), 2021 to the pull date, market-adjusted
AR (ret - SPY), during-market calls moved to the **next** trading day, raw broker names, CIs from the t-distribution.

| id | specification | result | headline? |
|---|---|---|---|
| P1 | CAR[-1,+1], episodes, by direction | up +2.37 (n 62), down -1.67 (n 56), mixed -3.29 (n 2) | yes (HW8) |
| P2 | AR[0], episodes | up +1.65 (n 62), down -0.96 (n 57) | no |
| P3 | CAR[0,+1], episodes | up +1.83 (n 62), down -0.92 (n 56) | no |
| P4 | earnings overlap = earnings within +-1 trading day; upgrades and downgrades **pooled** (signed CARs mixed together), CAR[-1,+1] | no overlap -0.06 (n 97), overlap +2.32 (n 23) | no (pooling signed CARs is not interpretable; replaced by F3) |
| P5 | same as P4 with AR[0] and CAR[0,+1] | AR[0]: +0.01 / +1.93; CAR[0,+1]: +0.10 / +2.11 | no |
| P6 | daily mean AR, t = -3..+3, by direction (figure) | peak at t = 0 | no |
| P7 | broker table, top 20 brokers by number of calls, raw names, mean AR[0] and CAR[-1,+1] | displayed only, not saved | no |

## Final pipeline (`run_all.py`)

Common setup: 50 firms chosen without hindsight (S&P 500 on 2021-01-01, top 50 by 2020 dollar volume),
rating changes 2021-01-01 to 2026-10-09, market model vs SPY on [-250,-30], event window [-20,+20],
day 0 = same trading day for before-open and during-market calls, next trading day for after-close,
mean +- 1.96 SE. Near earnings = rating day 0 within [-1,+2] trading days of an earnings day 0.

| id | specification | result (upgrades / downgrades) | headline? | where |
|---|---|---|---|---|
| F1 | CAR[-1,+1], episodes, all, plain SE | +2.39 (13.4), n 794 / -2.42 (-10.8), n 628 | no (former headline; shown next to F22) | window_summary, robustness |
| F2 | CAR[-20,-2] and CAR[+2,+20], episodes, all | pre +0.59 (1.6) / -0.42 (-1.0); drift +0.50 (1.6) / +0.36 (1.0) | no | window_summary |
| F3 | F1-F2 on episodes NOT near earnings | [-1,+1] +1.89 (11.3), n 656 / -1.36 (-8.6), n 500 | no (cleanest estimate) | window_summary |
| F4 | F1-F2 on episodes near earnings | [-1,+1] +4.77 (7.8), n 138 / -6.56 (-8.1), n 128 | no | window_summary |
| F5 | mean CAR path t = -20..+20, for all / no_earnings / near_earnings | jump at t = 0, small move at t = -1, flat after | no | car_by_day, figures |
| F6 | market-adjusted CAR[-1,+1] (ret - SPY) | +2.43 (13.4) / -2.51 (-10.8) | no | robustness |
| F7 | day 0: during-market calls moved to the next day (prototype rule) | +2.38 (13.6), n 798 / -2.28 (-10.8), n 626 | no | robustness |
| F8 | excluding near-earnings episodes (same numbers as F3) | +1.89 (11.3) / -1.36 (-8.6) | no | robustness |
| F9 | excluding multi-broker days | +2.06 (12.3), n 761 / -1.96 (-10.2), n 598 | no | robustness |
| F10 | unit = rating change instead of episode | +2.82 (14.2), n 852 / -3.58 (-12.0), n 696 | no | robustness |
| F11 | F1 with SE clustered by day 0 (statsmodels OLS on a constant) | t = 12.9 / -10.0 | no | robustness |
| F12 | broker leaderboard, CAR[-1,+1] per call, all calls; ranked if n >= 10, by empirical-Bayes shrunk mean | 34 / 28 brokers ranked; rank 1 JP Morgan (+5.36, n 27) / B of A Securities (-6.52, n 27) | no (robustness for the broker question) | broker_leaderboard (`sample = all`) |
| F13 | F12 on calls not near earnings | 31 / 23 brokers ranked; rank 1 JP Morgan (+4.20, n 22) / B of A Securities (-3.34, n 19) | **headline for the broker question** | broker_leaderboard (`sample = no_earnings`), broker_leaderboard.png |
| F14 | joint test "all ranked brokers have the same mean": ANOVA F and Kruskal-Wallis, for all / no_earnings / single-call days | ANOVA p 0.1409 / 0.2217 (all), 0.3104 / 0.2115 (no_earnings), 0.2645 / 0.2005 (single-call); Kruskal-Wallis p 0.0031 / 0.1104, 0.0954 / 0.132, 0.0036 / 0.0248 | no | broker_equality_test |
| F15 | between-broker spread tau (from the shrinkage step) | 0.72 / 0.25 pp (all), 0.48 / 0.32 pp (no_earnings), 0.53 / 0.52 pp (single-call) | no | broker_equality_test (`tau_pct`) |
| F16 | F12 on single-call days only (calls with no other broker on that stock-day) | 32 / 24 brokers ranked; rank 1 DZ Bank (+4.68, n 18) / B of A Securities (-4.14, n 21) | no | broker_leaderboard (`sample = single_call_days`) |
| F17 | label-permutation F test (2,000 shuffles of broker labels among ranked brokers' calls, seed 331), same 3 samples | p 0.1445 / 0.2175 (all), 0.297 / 0.2155 (no_earnings), 0.257 / 0.2095 (single-call) | no | broker_equality_test (`permutation F` rows) |
| F18 | standardized leaderboard: SCAR = CAR[-1,+1] / (estimation-window residual sd x sqrt 3), ranked by mean SCAR, same 3 samples; Spearman correlation with the F12/F13/F16 ranks | no_earnings rank 1 Evercore ISI (1.52, n 11) / Oppenheimer (-1.17, n 15); Spearman 0.92 / 0.93 (all), 0.92 / 0.91 (no_earnings), 0.91 / 0.95 (single-call); rank 1 differs in all 6 lists | no | broker_leaderboard_standardized, broker_rank_stability |
| F19 | F1-F2 on episodes with no earnings day 0 anywhere in [-20,+20] (`clean_window`) | [-1,+1] +2.41 (7.3), n 227 / -1.25 (-4.4), n 169; pre +0.98 (1.5) / -0.26 (-0.4); drift -0.52 (-0.9) / -0.05 (-0.1) | no | window_summary |
| F20 | CAR[0,+1] instead of CAR[-1,+1], episodes not near earnings | +1.60 (12.4), n 656 / -1.23 (-10.1), n 500 | no | robustness |
| F21 | mean daily AR, t = -3..+3, by timing class of the first call (before_open, during_market, after_close, all) and sample (all, no_earnings, near_earnings, earnings day 0 exactly at t = -1) | t = -1: all +0.52 / -0.70, no_earnings +0.30 / -0.13, near_earnings +1.58 / -2.92, earnings at t = -1 +3.72 (n 52) / -6.00 (n 59); no-earnings during-market calls react at t = 0 (+1.22 / -1.36); after-close has only 12 / 4 episodes | no | ar_by_day_timing |
| F22 | CAR[-1,+1] (and the long windows) on **clean** episodes: not near earnings ([-1,+2], wider than the instructor's +-1 session), no other call on the same stock within 2 trading days, not mixed | [-1,+1] +1.74 (10.1), n 582 / -1.29 (-7.6), n 419; pre +0.20 (0.5) / -0.79 (-1.6); drift +0.28 (0.7) / +0.29 (0.7) | **yes** | window_summary, car_by_day, robustness, car_upgrade_vs_downgrade.png |
| F23 | CAR[-1,+1] by direction x earnings overlap (same split as F3/F4, as its own table) | no overlap +1.89 (11.3), n 656 / -1.36 (-8.6), n 500; overlap +4.77 (7.8), n 138 / -6.56 (-8.1), n 128 | no | earnings_comparison |
| F24 | OLS of episode CAR[-1,+1] (%) on upgrade, near_earnings, upgrade x near_earnings and a constant, SE clustered by stock; and the same on signed CAR (minus CAR for downgrades) | raw: const -1.36, upgrade +3.25, near -5.20, interaction +8.08; signed: const 1.36, upgrade +0.53 (p 0.0535), near +5.20, interaction -2.32 (p 0.0178); n 1,422, 49 clusters | no | earnings_regression |

Diagnostics (checked the data or explained a choice; not reported as results):

| id | check | finding | where |
|---|---|---|---|
| D1 | clock-time distribution of Yahoo timestamps, read as UTC -> Eastern | peak 05:00-08:00 ET, none at midnight or on a round hour: real times. Decided the day-0 rule. | rating_time_of_day |
| D2 | calls per broker x direction, and the SE of a broker mean at n = 10 (why MIN_BROKER_CALLS = 10) | median 6 calls; 62 of 177 broker-directions have >= 10 calls and make 72.0% of calls; SE at n = 10 is 2.38 pp | sample_summary |
| D3 | Yahoo coverage per ticker and year (raw rows of any action, kept rating changes) | holes: META (one 2021 row, nothing 2024-10 to 2026-04), C (3 rows in 2021), GE (starts 2021-10-08), BRK-B (23 rows in total) | ratings_coverage_by_year |
| D4 | across ranked brokers (all calls), correlation of \|mean CAR\| with the broker's share of near-earnings calls | 0.35 / 0.58: the `all` leaderboard partly rewards re-rating right after earnings, so no_earnings became the headline | sample_summary, broker_leaderboard (`share_near_earnings_pct`) |
| D5 | the 10 largest abnormal returns at t = -1 among no-earnings episodes | e.g. +23.37 before SBUX_20240814_DeutscheBank, +23.12 before AMD_20251007_Jefferies: news can come before the call | largest_t_minus_1_moves_no_earnings |

## What was NOT tried (so nobody has to wonder)

- **Broker threshold fixed in advance.** `MIN_BROKER_CALLS = 10` was set in `src/_common.py` before
  the broker leaderboard was computed for the first time, and it was never changed: no other value was
  run (the code has one value and no loop over thresholds). The pipeline code is not yet in git
  history, so this order is the team's own record and cannot be shown from commits.
- No other earnings windows than [-1,+2] (and no +-1-session version of the clean sample), no other
  "other call" window than 2 trading days, no other estimation or event windows than the HW6 defaults.
- No factor models (Fama-French, industry) and no other benchmark than SPY.
- No subsamples by year, sector, firm, size of the rating jump, or broker size.
- The pipeline was run several times while being built (and once with `--refresh`); because the raw
  data were cached, every run gave the same numbers. Broker-name merging changes only F12-F18.
