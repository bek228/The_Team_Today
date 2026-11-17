# Analyst Rating Changes: Do Upgrades Move Stock Prices?

**[Launch the Live Interactive Dashboard](https://theteamtoday-8gqhfahmohefpa7weqnw9k.streamlit.app/)**

## 1. Project Overview

This project examines whether analyst rating upgrades and downgrades are associated with subsequent stock-price movements, and explores whether the broker issuing the recommendation matters.

The analysis uses historical analyst recommendations, adjusted daily stock prices, and earnings announcement dates to conduct an event study around analyst rating changes.

The sample is 50 large U.S. firms from January 2021 to October 2026. The earlier five-company HW8 prototype is kept in `dev/` for reference; none of its numbers are used here.

## 2. Research Sample

- **Companies:** 50 firms: the S&P 500 members on December 31, 2020, ranked by average daily dollar trading volume during 2020, top 50 (one share class per firm). The membership list and the volume are from 2020, but only firms that Yahoo can still price today could be ranked, so this is a survivors-only universe, not a hindsight-free one. Well-known members that could not be ranked include Twitter, Activision Blizzard, Electronic Arts, Xilinx, Walgreens Boots Alliance, First Republic Bank and SVB Financial. The list and the ranking metric are in `data/raw/universe.csv`; the members that could not be ranked are listed in `data/raw/universe_dropped.csv` (see Threats to validity).
- **Time period:** rating changes from January 1, 2021 through October 9, 2026 (fixed, so reruns do not drift). Prices run from October 2019 (for the estimation window) to November 13, 2026.
- **Market benchmark:** SPDR S&P 500 ETF (SPY).
- **Data source:** Yahoo Finance via `yfinance`, pulled once and committed as a snapshot (see Data provenance below). Yahoo's rating history has holes for a few firms (META, C, GE, BRK-B); see `outputs/tables/ratings_coverage_by_year.csv` and Threats to validity.
- **Counts** (firms, rating changes, episodes, brokers): `outputs/tables/sample_summary.csv`.

## 3. Methodology

The design follows the class event-study recipe (HW6). Every setting is a named constant in `src/_common.py`.

### Analyst Rating Changes
Yahoo's rating history is filtered to explicit upgrades and downgrades. Initiations, reiterations and price-target changes are excluded. Yahoo reports the brokerage firm, not the individual analyst. Broker names are unified with `data/raw/broker_aliases.csv` (for example, "Cowen & Co." and "TD Cowen" are one broker).

### Event Timing
Yahoo timestamps come without a time zone. We read them as UTC and convert to U.S. Eastern Time. This is an assumption, not a verified fact: the only evidence is that the clock times then look like broker publication times, and no timestamp was checked against an outside source. Reading them as Eastern instead is reported as a robustness check (`outputs/tables/robustness.csv`). Day 0 is the first trading day on which investors could trade on the news:

- Before 9:30 a.m. ET: that trading day.
- During market hours: that same trading day.
- At or after 4:00 p.m. ET: the next trading day.
- Weekends and holidays: the next trading day.

About four in five rating changes (`share_before_open` in `outputs/tables/sample_summary.csv`) are published before the open (clock times by hour: `outputs/tables/rating_time_of_day.csv`). Vendor timestamps are not independently verified publication times. Moving during-market calls to the next day instead is reported as a robustness check, and `outputs/tables/ar_by_day_timing.csv` shows the daily abnormal returns around day 0 for each timing class.

### Abnormal Returns and CAR
Expected returns come from a market model for each event:

**Expected Return = alpha + beta × SPY Return**, with alpha and beta estimated on trading days [-250, -30] before day 0 (at least 150 returns required).

**Abnormal Return = Stock Return − Expected Return.** Cumulative abnormal returns (CAR) sum abnormal returns over the event window [-20, +20]. The headline reaction is CAR[-1,+1]; CAR[-20,-2] is meant to capture anticipation and CAR[+2,+20] drift. Caveat: a 20-day window often contains an earnings report even when the rating change is not "near earnings", so those two windows can carry earnings news. The `clean_window` rows keep only episodes with no earnings day 0 anywhere in [-20,+20].

### Earnings Announcements
A rating change is flagged as "near earnings" when its day 0 falls from one trading day before to two trading days after the same firm's earnings day 0. The window leans forward because analysts usually re-rate just after a report. Results are shown for all events, events with no earnings nearby, and events near earnings.

**Headline sample: clean episodes.** An episode is *clean* when (1) it is not near earnings (the [-1,+2] window above, which is wider than a plus-or-minus-one-session rule, so it removes slightly more), (2) no other rating change on the same stock has its day 0 within 2 trading days (`other_call_in_window`; otherwise the two [-1,+1] windows overlap), and (3) it is not a mixed upgrade/downgrade day. The clean sample is an event-study control, not a tradable filter: rules (1) and (2) also look one to two trading days after day 0. A version that drops only on what is known by day 0 is in `outputs/tables/robustness.csv`. Do not confuse `clean` with `clean_window`: `clean_window` is a separate, stricter sample with no earnings day 0 anywhere in [-20,+20], used only to read the long windows CAR[-20,-2] and CAR[+2,+20]. Earnings-overlap episodes are reported separately by direction in `outputs/tables/earnings_comparison.csv`, and `outputs/tables/earnings_regression.csv` tests direction x earnings in one regression (CAR[-1,+1] on an upgrade dummy, a near-earnings dummy and their interaction, standard errors clustered by stock).

### Episodes
Several brokers changing their rating on the same stock on the same day share one price reaction, so they are consolidated into a single episode for the upgrade-versus-downgrade results. Days with both an upgrade and a downgrade are labelled mixed and left out.

### Does the Broker Matter?
Each broker's average CAR[-1,+1] per rating change is reported with a 95% confidence interval. Only brokers with at least 10 calls in a direction are ranked; the rest are shown but unranked. Because small-sample averages are noisy, the ranking uses a shrunk mean that pulls each broker toward the overall average, and joint tests ask whether ranked brokers differ at all (`outputs/tables/broker_equality_test.csv`).

The **headline leaderboard uses only calls not near earnings** (`sample = no_earnings` in `outputs/tables/broker_leaderboard.csv`, and the figure `broker_leaderboard.png`). On all calls, brokers that often re-rate right after an earnings report get credit for the earnings move: across ranked brokers, |mean CAR| rises with the broker's share of near-earnings calls (correlation in `sample_summary.csv`, rows `corr_abs_mean_car_vs_share_near_earnings_*`; each broker's share is the column `share_near_earnings_pct`). The `all` and `single_call_days` samples are kept in the same file as robustness. A second robustness leaderboard divides each CAR by the stock's own 3-day noise (estimation-window residual sd x sqrt 3), so volatile stocks do not dominate (`broker_leaderboard_standardized.csv`); how much the ranks move is in `broker_rank_stability.csv`.

### Statistical Analysis
Means are reported with standard errors, t-statistics and 95% intervals (mean ± 1.96 standard errors). The t-statistics in the results block treat episodes as independent. Alternative specifications are in `outputs/tables/robustness.csv`, including the clean headline with standard errors clustered by day 0 and two-way by stock and day 0 (reported below the results block), and every specification run is logged in `specs_tried.md`.

## 4. Results

Unit = episode (one stock, one day 0; several brokers moving the same stock on the same day count
once; the mixed upgrade/downgrade days are left out). Market-model CAR in percent; t-stat = mean / (sd / sqrt n).
The headline is the **clean** sample (defined in Methodology). The block below is written by
`src/05_results.py` from `outputs/tables/window_summary.csv` and
`outputs/tables/broker_equality_test.csv`; do not edit it by hand.

<!-- RESULTS:START (written by src/05_results.py; do not edit by hand) -->
**Headline: CAR[-1,+1] of clean episodes** (no earnings day 0 within [-1,+2] trading days, no other
rating change on the same stock within 2 trading days, mixed days left out), next to all and near-earnings episodes:

| direction | clean (headline) | all episodes | near earnings |
|---|---|---|---|
| upgrade | **+1.74% (t = 10.1, n = 582)** | +2.39% (t = 13.4, n = 794) | +4.77% (t = 7.8, n = 138) |
| downgrade | **-1.29% (t = -7.6, n = 419)** | -2.42% (t = -10.8, n = 628) | -6.56% (t = -8.1, n = 128) |

All samples and windows (`clean_window` = no earnings day 0 anywhere in [-20,+20], the stricter sample for the long windows):

| sample | direction | CAR[-20,-2] | CAR[-1,+1] | CAR[+2,+20] |
|---|---|---|---|---|
| clean | upgrade | +0.20% (t = 0.5, n = 582) | +1.74% (t = 10.1, n = 582) | +0.28% (t = 0.7, n = 582) |
| clean | downgrade | -0.79% (t = -1.6, n = 419) | -1.29% (t = -7.6, n = 419) | +0.29% (t = 0.7, n = 419) |
| all | upgrade | +0.59% (t = 1.6, n = 794) | +2.39% (t = 13.4, n = 794) | +0.50% (t = 1.6, n = 794) |
| all | downgrade | -0.42% (t = -1.0, n = 628) | -2.42% (t = -10.8, n = 628) | +0.36% (t = 1.0, n = 628) |
| no_earnings | upgrade | +0.45% (t = 1.1, n = 656) | +1.89% (t = 11.3, n = 656) | +0.34% (t = 1.0, n = 656) |
| no_earnings | downgrade | -0.48% (t = -1.0, n = 500) | -1.36% (t = -8.6, n = 500) | +0.41% (t = 1.0, n = 500) |
| near_earnings | upgrade | +1.26% (t = 1.5, n = 138) | +4.77% (t = 7.8, n = 138) | +1.24% (t = 1.7, n = 138) |
| near_earnings | downgrade | -0.20% (t = -0.2, n = 128) | -6.56% (t = -8.1, n = 128) | +0.17% (t = 0.2, n = 128) |
| clean_window | upgrade | +0.98% (t = 1.5, n = 227) | +2.41% (t = 7.3, n = 227) | -0.52% (t = -0.9, n = 227) |
| clean_window | downgrade | -0.26% (t = -0.4, n = 169) | -1.25% (t = -4.4, n = 169) | -0.05% (t = -0.1, n = 169) |

Do all ranked brokers (n >= MIN_BROKER_CALLS) have the same mean CAR[-1,+1] per call? p-values from `broker_equality_test.csv`:

| sample | direction | brokers | ANOVA F p-value | permutation F p-value | Kruskal-Wallis p-value |
|---|---|---|---|---|---|
| all | upgrade | 34 | 0.141 | 0.144 | 0.003 |
| all | downgrade | 28 | 0.222 | 0.217 | 0.110 |
| no_earnings | upgrade | 31 | 0.310 | 0.297 | 0.095 |
| no_earnings | downgrade | 23 | 0.212 | 0.215 | 0.132 |
| single_call_days | upgrade | 32 | 0.265 | 0.257 | 0.004 |
| single_call_days | downgrade | 24 | 0.201 | 0.209 | 0.025 |
<!-- RESULTS:END -->

**Robustness of the clean headline** (added after the self-audit, `audits/05_self_audit_response.md`;
every row is in `outputs/tables/robustness.csv`, CAR[-1,+1], upgrades / downgrades):

| check | upgrades | downgrades |
|---|---|---|
| clean headline, plain standard errors | +1.74% (t = 10.1, n = 582) | -1.29% (t = -7.6, n = 419) |
| same, standard errors clustered by day 0 | t = 9.5 | t = -7.2 |
| same, clustered two-way by stock and day 0 | t = 8.2 | t = -6.9 |
| timestamps read as Eastern, not UTC (clean) | +1.75% (t = 10.4, n = 587) | -1.34% (t = -7.9, n = 421) |
| clean filter using only what is known by day 0 | +1.81% (t = 10.6, n = 617) | -1.35% (t = -8.1, n = 459) |
| earnings timing placeholders from earlier announcements only | +1.74% (t = 10.1, n = 582) | -1.29% (t = -7.6, n = 419) |
| market model estimated without earnings and rating-change days | +1.77% (t = 10.3, n = 582) | -1.30% (t = -7.7, n = 419) |
| only episodes with no other rating change in the estimation window | +1.74% (t = 2.8, n = 54) | -1.53% (t = -2.6, n = 27) |

Clustering makes the t-statistics smaller (two-way: 8.2 and -6.9 instead of 10.1 and -7.6), so the
plain t-statistics overstate the precision; the means do not change and stay far from zero. If the
timestamps are Eastern, day 0 moves for 156 of the 1,548 rating changes
(`n_rating_changes_day0_moves_if_eastern` in `sample_summary.csv`), and the result barely moves. The
earnings-timing row equals the headline because no near-earnings flag changes
(`n_near_earnings_flags_changed_past_only` = 0; only 12 earnings times are placeholders). Every
episode has an earnings day in its estimation window and 1,300 of the 1,422 have another rating
change there (`n_episodes_est_window_has_*`), so dropping all of them leaves no episodes (that row
is in the file with n = 0); the last row above keeps only 81 episodes and is much noisier.

**Earnings and direction in one regression** (`earnings_regression.csv`, 1,422 non-mixed episodes,
standard errors clustered by stock, 49 clusters). In the signed-CAR version (reaction in the direction
of the call), a downgrade not near earnings moves the price by 1.36%; an upgrade not near earnings
moves it 0.53 percentage points more (p = 0.0535); being near earnings adds 5.20 points for
downgrades (p < 0.001), and that earnings boost is 2.32 points smaller for upgrades (interaction
p = 0.0178). So earnings amplify downgrades more than upgrades.

**Does the broker matter? The tests cannot tell brokers apart.** **ANOVA and the permutation test
agree that average reactions do not detectably differ across brokers** in any sample (every p-value
above 0.1 in the table above). So the ranks below are a description of this sample, not a finding:
they are not distinguishable from noise. On the headline no-earnings leaderboard, rank 1 is JP Morgan
for upgrades (+4.20%, n = 22) and B of A Securities for downgrades (-3.34%, n = 19)
(`broker_leaderboard.csv`, `sample = no_earnings`, `rank = 1`). The leaderboard unit is the rating
change, so it includes calls from days the headline leaves out or counts once: of the 1,201 calls in
the no-earnings leaderboard, 16 come from mixed upgrade/downgrade days and 69 from multi-broker days,
where calls share one CAR (`n_calls_on_mixed_days_no_earnings_leaderboard`,
`n_calls_on_multi_broker_days_no_earnings_leaderboard` in `sample_summary.csv`; 37 calls in the whole
sample are on mixed days). Kruskal-Wallis is a different
question: it compares whole distributions (ranks), not means. Returns are heavy-tailed, and brokers
differ in spread and skew (some cover volatile stocks, some call right after earnings), so
Kruskal-Wallis can reject (it does at 5% for `all` upgrades and for both `single_call_days` lists)
even when the means are equal. The shrinkage step agrees: the estimated between-broker spread of
true means, tau, is 0.25 to 0.72 percentage points (column `tau_pct` of `broker_equality_test.csv`),
small next to the noise in one broker's average at n = 10 (`se_of_broker_mean_at_n10_pp` in
`sample_summary.csv`). Ranks are fairly stable when CARs are standardized
by each stock's noise (Spearman correlation between 0.91 and 0.95 in every sample and direction,
`broker_rank_stability.csv`), although rank 1 changes in every case.

All results, as CSV (percent units: 1.25 means 1.25%):

| file | what it is |
|---|---|
| `outputs/tables/sample_summary.csv` | counts, sample dates, pull date, shares near earnings / by timing, universe counts, calls-per-broker diagnostics |
| `outputs/tables/window_summary.csv` | CAR[-20,-2], CAR[-1,+1], CAR[+2,+20] by sample (all / no_earnings / near_earnings / clean_window / clean) and direction |
| `outputs/tables/earnings_comparison.csv` | CAR[-1,+1] by direction x (no earnings overlap / earnings overlap), unit = episode |
| `outputs/tables/earnings_regression.csv` | CAR[-1,+1] and signed CAR[-1,+1] on upgrade, near-earnings and their interaction, SE clustered by stock |
| `outputs/tables/car_by_day.csv` | mean CAR path t = -20..+20 with 95% bands (the figures) |
| `outputs/tables/ar_by_day_timing.csv` | mean daily AR, t = -3..+3, by sample, timing class of the call and direction |
| `outputs/tables/largest_t_minus_1_moves_no_earnings.csv` | the 10 largest abnormal returns at t = -1 among no-earnings episodes |
| `outputs/tables/broker_leaderboard.csv` | CAR[-1,+1] per call, every broker; ranked only if n >= 10, by an empirical-Bayes shrunk mean; samples no_earnings (headline), all, single_call_days |
| `outputs/tables/broker_leaderboard_standardized.csv` | same, with CAR / (residual sd x sqrt 3), ranked by mean |
| `outputs/tables/broker_rank_stability.csv` | Spearman correlation between the raw and standardized rankings |
| `outputs/tables/broker_equality_test.csv` | joint tests that all ranked brokers have the same mean (ANOVA F, permutation F, Kruskal-Wallis), plus tau |
| `outputs/tables/robustness.csv` | headline CAR[-1,+1] under alternative choices |
| `outputs/tables/rating_time_of_day.csv` | clock-time distribution of Yahoo's rating timestamps (Eastern) |
| `outputs/tables/ratings_coverage_by_year.csv` | raw Yahoo rating rows and kept rating changes, per ticker and calendar year |
| `outputs/figures/*.png` | upgrades vs downgrades (clean sample), earnings split, broker leaderboard (no_earnings sample) |

## 5. Repository Structure

```text
The_Team_Today/
├── run_all.py                  # runs src/00 ... src/05, then src/99 (hand checks)
├── requirements.txt            # pinned versions actually used
├── specs_tried.md              # every specification run, incl. the prototype's
├── src/
│   ├── _common.py              # paths, sample window, event-study constants, day-0 rule, helpers
│   ├── 00_universe.py          # S&P 500 on 2021-01-01 -> top 50 by 2020 dollar volume (firms Yahoo still prices)
│   ├── 01_get_ratings.py       # Yahoo upgrades/downgrades -> data/processed/ratings.csv
│   ├── 02_get_earnings.py      # Yahoo earnings dates -> data/processed/earnings.csv
│   ├── 03_get_returns.py       # one batched price download -> data/processed/returns.csv
│   ├── 04_build_event_panel.py # day 0, market model, AR/CAR, earnings flags, episodes
│   ├── 05_results.py           # all tables and figures (+ the README results block)
│   └── 99_hand_checks.py       # recomputes one number per step a different way, asserts
├── data/
│   ├── raw/                    # downloads as pulled (never hand-edited) + MANIFEST.csv
│   │   ├── ratings/<TICKER>.csv, earnings/<TICKER>.csv
│   │   ├── prices.csv, sp500_members_2020-12-31.csv, sp500_members_current.csv, dollar_volume_2020.csv
│   │   ├── universe.csv, universe_dropped.csv   # derived by 00_universe.py from the three files above
│   │   └── broker_aliases.csv  # hand-built name map (the one hand-made input; see its note column)
│   └── processed/              # everything rebuilt by run_all.py (also committed, because the dashboard reads it)
├── outputs/tables/, outputs/figures/
├── docs/                       # hand_checks.md, dashboard_mockup.png (AI-generated mockup, not a result)
├── dashboard/                  # Streamlit dashboard: app.py (entry point), ui_*.py, tests/test_app.py
├── .streamlit/config.toml      # dashboard colours
├── audits/                     # self-audit
└── dev/                        # HW8 prototype (pipeline.py, HW8_Data.ipynb) and its data/outputs, kept for the record
```

### Data provenance

| data | source | script | file |
|---|---|---|---|
| S&P 500 members on 2021-01-01 | Wikipedia "List of S&P 500 companies", revision 997494787 (2020-12-31 19:55 UTC) | `00_universe.py` | `data/raw/sp500_members_2020-12-31.csv` |
| today's members (only to map old tickers via CIK, e.g. FB -> META) | Wikipedia, current revision | `00_universe.py` | `data/raw/sp500_members_current.csv` |
| 2020 dollar volume | `yf.download(..., 2020, auto_adjust=False)`, close x volume | `00_universe.py` | `data/raw/dollar_volume_2020.csv` |
| analyst rating changes | `yf.Ticker(t).upgrades_downgrades` | `01_get_ratings.py` | `data/raw/ratings/<TICKER>.csv` |
| earnings dates | `yf.Ticker(t).get_earnings_dates(limit=100)` | `02_get_earnings.py` | `data/raw/earnings/<TICKER>.csv` |
| daily prices | `yf.download(50 firms + SPY, 2019-10-01 to 2026-11-13, auto_adjust=True)` | `03_get_returns.py` | `data/raw/prices.csv` |
| the 50 firms, and members not used | **derived, not downloaded**: built by `00_universe.py` from the two membership files and the dollar-volume file above (kept in `data/raw/` because other code reads them there) | `00_universe.py` | `data/raw/universe.csv`, `data/raw/universe_dropped.csv` |

Pull date: every raw file was downloaded on 2026-11-16 UTC (evening of 2026-11-15, US time) with
yfinance 1.7.0. The exact timestamp and row count of each file are in `data/raw/MANIFEST.csv`.

## 6. How to run

```bash
git clone https://github.com/bek228/The_Team_Today.git
cd The_Team_Today
pip install -r requirements.txt     # needs Python >= 3.12 (see below); a fresh venv is fine
python run_all.py                   # 1-2 minutes; rebuilds data/processed/ and outputs/ from the committed raw snapshot
```

**Python version.** The pipeline was run with Python 3.14.6. The minimum is Python 3.12, because
the pinned scipy 1.18.0 declares `Requires-Python >= 3.12` (pandas 3.0.3, numpy 2.4.6 and
matplotlib 3.11.0 need >= 3.11); Python 3.12 and 3.13 were not actually tested. With an older Python
`pip install -r requirements.txt` fails. No `runtime.txt` or other Streamlit Cloud file is included;
the hosted dashboard's Python version is whatever is set in Streamlit Cloud.

`python run_all.py` uses the committed files in `data/raw/`, so it reproduces the committed
numbers exactly (checked in a fresh virtual environment, file by file). `python run_all.py --refresh`
re-downloads everything (about 10 minutes) and records each pull in `data/raw/MANIFEST.csv`; the
numbers will then move, because Yahoo revises its data and drops old rating rows. Each script can
also be run alone from the repo root, in order, e.g. `python src/04_build_event_panel.py`.

To launch the interactive dashboard locally:

```bash
streamlit run dashboard/app.py
```

The dashboard only reads the committed files in `outputs/tables/`, `data/processed/` and `data/raw/universe.csv`.
It downloads nothing and does not rerun the study. To test every page: `python dashboard/tests/test_app.py`.

The live dashboard is also available here:

https://theteamtoday-8gqhfahmohefpa7weqnw9k.streamlit.app/

## 7. Threats to validity

- **Yahoo coverage holes.** Yahoo's rating history is incomplete for some firms, and the holes sit
  inside the sample, not only at its start. From `outputs/tables/ratings_coverage_by_year.csv`
  (raw rows of any action and kept rating changes, per ticker and year):
  **META** has one stray 2021 row (2021-05-03), real coverage only from 2022-01-19, no rows after
  2024-09-30 and none at all in calendar 2025, then rows again from 2026-04-20;
  **C** has only 3 rows in 2021 (none kept as a rating change), so its coverage effectively starts in 2022;
  **GE** starts 2021-10-08; **BRK-B** has 23 raw rows in total and no rating change in the window.
  Yahoo keeps roughly the last ~1,000 rows per ticker, but this does not explain the holes: only
  the most heavily covered tickers come near that cap (GOOGL, AMZN, TSLA, NVDA, CRM, AAPL, MSFT and
  NFLX have 953-995 rows each), and all of them have rows from before 2021, so nothing in the
  sample window has rolled off for them. The gaps look like holes in the vendor's data. We kept the
  2021-01-01 start for every firm and disclose the gaps instead. Yahoo's list is not a complete
  record of every broker call, and we cannot check what it leaves out; that is why the raw snapshot is committed.
- **Survivors-only universe.** The firm list uses 2020 membership (the index on 2020-12-31) and 2020
  dollar volume, but only firms that Yahoo can still price today could be ranked. That step uses
  hindsight. 47 of the 505 members could not be priced on Yahoo today (delisted, acquired, or renamed
  under an identifier not in today's index), among them Twitter (TWTR), Activision Blizzard (ATVI),
  Electronic Arts (EA), Xilinx (XLNX), Walgreens Boots Alliance (WBA), First Republic Bank (FRC) and
  SVB Financial (SIVB). One more (VNT, spun off in late 2020) had fewer than 200 trading days in 2020.
  None of these could be ranked (counts: `n_sp500_members_2020`, `n_members_no_yahoo_prices`,
  `n_members_short_2020_history` in `sample_summary.csv`; list: `data/raw/universe_dropped.csv`). We
  have no 2020 volume for them, so we cannot say how many would have made the top 50; Twitter in
  particular may have been near the cutoff. All 50 chosen firms still trade, so firms that died in
  2021-2026 are missing, and the effect of that on the results is not measured.
- **Ticker map.** Old symbols are mapped to today's through the SEC CIK in the current Wikipedia table.
  Two mappings look odd: EQR (Equity Residential) -> VMRK ("Vivmark Residential") and MMC (Marsh &
  McLennan) -> MRSH. Both keep the same CIK, and Yahoo returns a full 2020 price history under the new
  symbol (`data/raw/dollar_volume_2020.csv`), which fits a real rename rather than a mapping error, but
  we did not verify the renames elsewhere. Neither firm is in the top 50, so no result depends on them.
- **Timestamp reliability and the move at t = -1.** Yahoo's times come without a time zone. Reading
  them as UTC is our assumption. The only support is that the clock times then look like publication
  times (about 79% before the open, `share_before_open` in `sample_summary.csv`; none at midnight or
  on a round hour, `rating_time_of_day.csv`). That argument is circular (the zone was chosen because
  the result looks right), and no timestamp was checked against a broker note or another vendor. If
  the stamps are Eastern instead, day 0 moves for 156 of the 1,548 rating changes and the clean
  CAR[-1,+1] is +1.75% / -1.34% instead of +1.74% / -1.29% (`robustness.csv`), so the headline does
  not depend on the choice, but the day-by-day timing below does. All numbers below are mean daily abnormal returns from
  `outputs/tables/ar_by_day_timing.csv` (unit = episode). Over all episodes there is a move at t = -1
  (+0.52% for upgrades, -0.70% for downgrades) before the main jump at t = 0 (+1.80% / -1.74%).
  **That t = -1 move is mostly earnings, not late timestamps.** Near-earnings episodes have a large
  t = -1 move (+1.58% upgrades, -2.92% downgrades), while no-earnings episodes have only +0.30% and
  -0.13%. When the firm's earnings day 0 is exactly t = -1 (sample `earnings_at_t_minus_1`), the
  t = -1 abnormal return is +3.72% for upgrades (n = 52) and -6.00% for downgrades (n = 59): the
  analyst is re-rating the day after the report. The timing classes support the same-day rule: for
  no-earnings during-market calls, the reaction is on t = 0 (+1.22% upgrades, -1.36% downgrades) and
  t = -1 is small (-0.28% / -0.09%); moving those calls to the next day would put their reaction on
  t = -1, and doing so changes CAR[-1,+1] very little anyway (`robustness.csv`). The only sign of
  lagging stamps is the small after-close group (12 upgrade and 4 downgrade episodes in the `all`
  sample), whose upgrades move at t = -2 and t = -1 (+2.24%, +1.93%) more than at t = 0 (+0.53%): for
  these few calls the price moved before Yahoo's stamp. Other news can also come before a call: the
  largest no-earnings t = -1 moves include +23.37% for SBUX before `SBUX_20240814_DeutscheBank` and
  +23.12% for AMD before `AMD_20251007_Jefferies`
  (`outputs/tables/largest_t_minus_1_moves_no_earnings.csv`). CAR[0,+1], which leaves out t = -1, is
  still +1.60% for no-earnings upgrades and -1.23% for downgrades (`robustness.csv`).
- **Earnings and other confounding news.** About 22% of rating changes (`share_near_earnings` in
  `sample_summary.csv`) come within [-1,+2] trading days of an earnings day 0, and their CAR[-1,+1] is
  several times larger: much of that move is the earnings news, not the analyst. The `clean` rows
  (headline) leave these out. Other news (guidance, M&A, macro days) is not filtered, and a broker
  may simply be reacting to news that already moved the price.
- **Earnings inside the long windows.** CAR[-20,-2] ("anticipation") and CAR[+2,+20] ("drift") span
  20 trading days, so they often contain an earnings report even for `no_earnings` episodes: 72% of
  episodes have an earnings day 0 somewhere in [-20,+20] (`share_episodes_earnings_in_window` in
  `sample_summary.csv`). The `clean_window` rows of the results table (no earnings anywhere in
  [-20,+20]) are the honest version of those two windows. They are based on far fewer episodes, and
  neither window is significant there for either direction.
- **Same-day multi-broker calls.** 77 episodes (`n_episodes_multi_broker`) have several brokers moving
  the same stock on the same day. The main results use one row per episode; the leaderboard uses one
  row per call, so those calls share one CAR (the leaderboard and the equality tests are also run on
  single-call days only, `sample = single_call_days`).
- **Leaderboard confidence intervals assume independent calls.** Each broker's 95% interval treats its
  calls as independent, but some calls on the same stock and day share one CAR with other brokers'
  calls, and calls on the same stock are correlated over time, so the intervals are somewhat too narrow.
- **Clustered events.** Many episodes share a calendar day or a stock. For the clean headline,
  clustering by day 0 lowers the t-statistics from 10.1 / -7.6 to 9.5 / -7.2, and two-way clustering
  by stock and day 0 lowers them to 8.2 / -6.9 (`robustness.csv`). The plain t-statistics in the
  results block are therefore too large, though the result stays far from zero. The broker
  leaderboard intervals are not clustered, and the earnings regression clusters by stock only.
- **The clean sample uses information from after day 0.** `other_call_in_window` looks one to two
  trading days after day 0, `near_earnings` up to one day after, and `earnings_in_window` 20 days
  after. The clean sample is an event-study control, not a filter an investor could apply on day 0. A
  version that drops only on what is known by day 0 keeps more episodes and gives slightly larger
  numbers (+1.81%, n = 617 / -1.35%, n = 459, `robustness.csv`). Earnings timing placeholders are
  filled with each firm's usual timing over the whole sample; using earlier announcements only
  changes no near-earnings flag (`n_near_earnings_flags_changed_past_only` in `sample_summary.csv`).
- **The estimation window is not cleaned.** Days [-250,-30] contain earlier earnings days for every
  episode and earlier rating changes of the same stock for 1,300 of 1,422 episodes
  (`n_episodes_est_window_has_*` in `sample_summary.csv`); they feed alpha, beta and the residual
  sd. Estimating the market model without those days gives +1.77% / -1.30% for the clean sample
  (`robustness.csv`), so the headline does not depend on it.
- **Current-vintage vendor data.** The sample is whatever Yahoo held on the pull date. Yahoo revises
  its data and drops old rating rows, so a new pull gives different numbers, and we cannot see what
  an investor would have seen at the time.
- **During-market calls and the t = 0 return.** There are no intraday prices. For a call published
  during market hours (about 20% of rating changes, `share_during_market`), the t = 0 daily return
  includes the part of the day before the call.
- **Downgrades may follow price falls.** In the clean sample CAR[-20,-2] for downgrades is -0.79%
  (t = -1.6, `window_summary.csv`). It is not significant, but it is consistent with analysts
  downgrading after the price has already fallen, which would mean the call partly follows the move.
- **Small-n brokers and multiple comparisons.** Most brokers make few calls (median 6 per direction,
  `median_calls_per_broker_direction` in `sample_summary.csv`). Only brokers with >= 10 calls are
  ranked, means are shrunk toward the average, and the joint tests are the honest answer to "does the
  broker matter". With 20-35 brokers per list some will look extreme by chance; we ran 18 equality
  tests (3 tests x 2 directions x 3 samples) and report all of them.
- **Market-model choice.** Alpha and beta come from days [-250,-30] vs SPY. Market-adjusted returns give
  almost the same answer; multi-factor models (size, value, momentum, industry) were not tried.
- **One regime.** 2021-2026 only (post-COVID rally, the 2022 rate shock, the AI-led market), and only
  large, heavily followed US stocks. Effects may differ for small firms or other periods.
- **Daily data.** Daily returns cannot separate the analyst's news from other news on the same day.

## 8. Project Outputs

The repository includes:

- Raw analyst rating history.
- Adjusted daily stock and benchmark prices.
- Historical earnings announcement dates.
- Processed analyst event datasets.
- Event-day abnormal return panels.
- Upgrade and downgrade summary statistics.
- Earnings-overlap comparisons.
- Event-study visualizations.

