# Hand checks

`src/99_hand_checks.py` runs last in `python run_all.py`. For each pipeline step it recomputes at
least one number **a different way**, starting from an earlier file (raw where possible), and
`assert`s that it matches. If any check fails, `run_all.py` stops with an error. The printed
output of the last run is in the console; the checks themselves are below.

One check (or more) per pipeline step:

| step | what is recomputed | how it is done differently | compared with |
|---|---|---|---|
| 0 universe | the 50 tickers, in order | re-rank `data/raw/dollar_volume_2020.csv` (members with >= 200 priced days in 2020), keep one share class per CIK, take the top 50 | `data/raw/universe.csv` |
| 1 ratings: count | number of rating changes | from the raw per-ticker files: keep `Action` in {up, down}, convert UTC to Eastern, keep 2021-01-01 to 2026-10-09, map brokers with `broker_aliases.csv`, drop repeats of (ticker, broker, day, action) | row count of `data/processed/events.csv` |
| 1 ratings: time-of-day table | total of the `n` column | rows of `events.csv` plus rows of `dropped_events.csv` (every rating change after de-duplication) | `outputs/tables/rating_time_of_day.csv` |
| 1 ratings: timing and day 0 from the raw stamp | timing class and day 0 of one before-open, one during-market and one after-close rating change | straight from the raw `GradeDate` in `data/raw/ratings/<T>.csv`: UTC -> Eastern, clock rule written out by hand (before 09:30 / from 16:00), day 0 by walking the dates of `data/raw/prices.csv`, event_id rebuilt by hand. Does not use the pipeline's `timing` column | `events.csv` `timing` and `day0` |
| 1/4 day 0 for every event | day 0 of all events | walk the trading calendar ("first trading day >= the date", or "> the date" for after-close calls) instead of `searchsorted`; this one takes the pipeline's timing label as given | `events.csv` `day0` |
| 2 earnings | earnings day 0 for one after-close firm (AAPL) and one before-open firm (JPM) | first 2024 row of the raw `data/raw/earnings/<T>.csv`: parse the stamp (it carries its offset), convert to Eastern, apply the clock rule by hand, walk the calendar from `data/raw/prices.csv` | `data/processed/earnings_day0.csv` |
| 3 returns | one AAPL daily return | `close_t / close_{t-1} - 1` from `data/raw/prices.csv` | `data/processed/returns.csv` |
| 4 market model | alpha, beta, AR at t = -1, 0, +1 and the episode's CAR[-1,+1] for one AAPL event | OLS by `np.polyfit` on returns rebuilt from the raw closes in `data/raw/prices.csv`, window [-250, -30] | `events.csv` alpha/beta/car_m1_p1, `episodes.csv` car_m1_p1 and `event_panel.csv` AR (`np.allclose`) |
| 4 earnings flags | `days_from_earnings`, `near_earnings` and `earnings_in_window` for one event | from raw pieces only: the rating's day 0 from its raw `GradeDate`, and every earnings day 0 of that firm from its raw earnings file (during-market stamps replaced by the firm's most common other timing, as `02_get_earnings.py` does), then the nearest gap in trading days (on a tie, the positive gap) | `events.csv` |
| 4 episodes | number of episodes and of mixed episodes | set of directions per (ticker, day 0) | `episodes.csv` |
| 5 headline | upgrades CAR[-1,+1], n and t-stat | sum the panel's AR over t = -1..+1 for the first call of each upgrade episode, then mean / (sd / sqrt n) | `outputs/tables/window_summary.csv` |
| 5 clean headline | `other_call_in_window` for every episode, and the clean CAR[-1,+1] n and mean by direction | other calls recomputed by comparing every pair of day 0 positions of the same stock (gap of 1 or 2 trading days) | `episodes.csv`, `outputs/tables/window_summary.csv` (`sample = clean`) |
| 5 clustered SE | standard error of the clean upgrade mean CAR[-1,+1], clustered by day 0 | no regression: sum the residuals (CAR minus the mean) within each day 0, square the sums, add them up, divide by n^2, multiply by statsmodels' small-sample factor G/(G-1) x (n-1)/(n-k) with k = 1, take the square root | `outputs/tables/robustness.csv` (`clean (headline), SE clustered by day0`) |
| 5 backward-looking clean | `other_call_before` for every episode, and the n and mean of the backward-looking clean row by direction | other calls recomputed by comparing every pair of day 0 positions of the same stock (the other one 1 or 2 trading days earlier); earnings day 0 on day 0 or 1-2 trading days before it, read from `days_from_earnings` in `episodes.csv` (not recomputed) | `episodes.csv`, `outputs/tables/robustness.csv` (`clean, backward-looking filter: ...`) |
| 5 timing table | mean AR at t = -1, no-earnings upgrade episodes | straight from `event_panel.csv`, first call of each episode | `outputs/tables/ar_by_day_timing.csv` |
| 5 leaderboard | n, mean and SE of the rank-1 upgrade broker in the headline (no_earnings) leaderboard | straight from `events.csv` | `outputs/tables/broker_leaderboard.csv` |
| 5 standardized leaderboard | one event's residual sd, and that broker's mean standardized CAR | residual sd from an `np.polyfit` fit on raw closes, sqrt(sum of squared residuals / (n - 2)) | `events.csv` `resid_sd`, `outputs/tables/broker_leaderboard_standardized.csv` |

## Examples worth reading by eye

The day-0 check from the raw stamp prints its three rating changes. In the committed snapshot:

- `TSLA_20260605_JPMorgan`, 08:44 ET Friday 2026-06-05 (before the open) -> day 0 = 2026-06-05.
- `TSLA_20251208_MorganStanley`, 10:42 ET Monday 2025-12-08 (during the market) -> day 0 = 2025-12-08,
  the same day: investors could trade on it that afternoon.
- `TSLA_20251024_FreedomCapitalMarkets`, 16:25 ET Friday 2025-10-24 (after the close) -> day 0 =
  Monday 2025-10-27 (the next trading day, over the weekend).

The earnings check prints AAPL's 2024-02-01 16:00 ET report (after the close -> day 0 2024-02-02) and
JPM's 2024-01-12 06:00 ET report (before the open -> day 0 2024-01-12). The earnings-flag check
rebuilds `DAL_20210115_VerticalGroup`: day 0 2021-01-15, one trading day after DAL's earnings day 0,
so it is near earnings.

## Timing check from the data

If the day-0 rule were wrong, the average abnormal return would peak at t = -1 or t = +1.
`outputs/tables/ar_by_day_timing.csv` (mean daily AR by timing class, t = -3..+3) shows the jump at
t = 0 for before-open and during-market calls alike. For no-earnings during-market episodes, the
mean AR is +1.22% (upgrades) and -1.36% (downgrades) at t = 0 against -0.28% and -0.09% at t = -1;
moving those calls to the next day would put their reaction on t = -1. The move at t = -1 over all
episodes (+0.52% upgrades, -0.70% downgrades, same file, `timing = all`) comes mostly from
near-earnings episodes; see "Threats to validity" in the README.
