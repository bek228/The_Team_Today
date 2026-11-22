# Instructor audit: The Team Today, Checkpoint 3

**Repo:** bek228/The_Team_Today · **Audited commit:** `f22bb66` (2026-11-19, `main`, merge of PR #10) · **Seed:** 7, do analyst upgrades move prices, and does the broker matter? · **CP2 audit:** `audits/02_instructor_audit.md` (commit `206e3e9`)

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

An excellent v1.
- A clean environment built only from `requirements.txt` runs `python run_all.py` offline in 66 s. Every table in `outputs/tables/` and every file in `data/processed/` comes out identical, and all hand checks pass.
- My own market-model code reproduces all 1,436 episode CARs from your raw snapshot. A fresh yfinance pull agrees.
- All six CP2 findings are fixed. I tested A5's fail-loud behavior myself: it stops with a clear message.
- Your threats section already answers the questions I would have asked: Yahoo's coverage holes, the ~1,000-row cap, survivors-only ranking, clustered SEs, and the UTC timestamp assumption.

The one item is small (B1). The real work before Dec 1 is choosing what to cut for 9–10 minutes.

## Follow-up on your Checkpoint 2 audit

Response file: `audits/03_audit_response.md` found (on `main`).

| CP2 finding | Status | Evidence |
|---|---|---|
| A1 · IPython not in `requirements.txt` | fixed | `uv venv --python 3.12 && uv pip install -r requirements.txt` (no IPython), then `python run_all.py`: exit 0, 65.7 s. This also shows it runs on Python 3.12.13, which `requirements.txt` says was "not actually tested" |
| A2 · Every run re-downloads and drifts | fixed | `src/_common.py` fixes the window (`SAMPLE_END = '2026-10-09'`, `PRICE_END = '2026-11-14'`). `data/raw/` is committed, with `MANIFEST.csv` (source, pull time, rows, yfinance version). A fresh offline run reproduced all 14 `outputs/tables/*.csv` and 11 `data/processed/*.csv` identically, and `README.md` was unchanged |
| A3 · Earnings comparison pools directions | fixed | `earnings_comparison.csv` is by direction × overlap (e.g. upgrades 1.89% without earnings vs 4.77% with). `earnings_regression.csv` has SEs clustered by stock. The README headline uses the `clean` rows of `window_summary.csv` |
| A4 · `STATUS.md`, `specs_tried.md`, hand check missing | fixed | Both files exist (`specs_tried.md`, 95 lines). `src/99_hand_checks.py` runs last in `run_all.py` and printed "all hand checks passed". (`STATUS.md` has only the CP1 memo: see B1) |
| A5 · Failed downloads tolerated silently | fixed | Test: on a copy, I deleted `data/raw/earnings/AAPL.csv` and pointed the proxy at a closed local port. `run_all.py` exited 1 at step 02 with "ERROR: earnings download failed and no cached file exists for ['AAPL'] … Nothing was written for them" |
| A6 · Sample and broker plan | fixed | `src/00_universe.py` (2020-12-31 members, ranked by 2020 dollar volume; `data/raw/universe.csv`, `universe_dropped.csv`). `broker_leaderboard.csv` has 95% CIs, `meets_min_n` (10 calls), a shrunk mean, and `broker_equality_test.csv` |

**6 of 6 fixed, 0 still open.**

## Checkpoint 3 checks

| Check | Result |
|---|---|
| Reruns from scratch (full sample) | ✅ exit 0, 65.7 s, offline from `data/raw/`; outputs identical |
| Inputs have provenance | ✅ `data/raw/MANIFEST.csv` per file |
| Keys unique, merges validated | ✅ `ratings_duplicates_dropped.csv` logs the 1 dropped duplicate. Hand checks recompute one number per step |
| No look-ahead / survivorship | ✅ timing classes and a day-0 rule, with the UTC-vs-Eastern assumption reported as a robustness row. Survivors-only ranking disclosed (`README.md:281-288`) |
| LLM leakage handled | n/a |
| `specs_tried.md` complete | ✅ |
| Magnitudes discussed | ✅ CARs in percent with CIs, and the broker leaderboard with shrinkage |
| Hand checks | ✅ `src/99_hand_checks.py`, e.g. "XOM_20210113_JPMorgan: residual sd 0.02404" |
| Threats to validity | ✅ unusually complete (coverage holes, the row cap, survivorship, timestamps, clustering) |
| Every number traces to `outputs/` | ✅ the README results block is written by `src/05_results.py` |
| Dashboard matches `outputs/` | ✅ "Upgrades: +1.74% … (t = 10.1, 582 episodes)", "Downgrades: −1.29% (t = −7.6, 419)" = `window_summary.csv` `clean`, `[-1,+1]` rows (1.7372, 10.1443, 582; −1.2899, −7.6435, 419) |

Steps not rerun by design: none. The default run uses the committed snapshot. (`--refresh` would call `finance.yahoo.com` and wasn't used.)

## Getting ready for Dec 1

Presentations run only from URLs, with a hard cutoff at 9 minutes (10:45 section) or 10 minutes (12:10 section). Put your URL(s) in column G of the Team Projects sheet.

| Check | Result |
|---|---|
| Dashboard launches from a clean clone | ✅ `streamlit run dashboard/app.py --server.headless true --server.port 8608` (venv from `requirements.txt`) on a clean export of `f22bb66`: `/_stcore/health` returned `ok` after 3 s, with no exceptions on the page or in the log |
| Dashboard shows the v1 numbers from `outputs/` | ✅ see the last row above. Each figure names its source file (e.g. "Source: outputs/tables/car_by_day.csv") |
| README links the live URL(s) | ✅ `README.md:3` and `:264` link the `…streamlit.app` dashboard (the live site itself wasn't checked). `requirements.txt` pins `streamlit==1.58.0` and `plotly==7.1.0`. Set Streamlit Cloud's Python to 3.12 or later (scipy 1.18 needs it, per your own note) |

**Core story for 9–10 minutes:** the clean-sample CAR path (upgrades +1.74%, downgrades −1.29%); how much of the raw effect is earnings days (1.89% vs 4.77% for upgrades); and the broker answer, "we can't tell brokers apart" (ANOVA p = 0.31 / 0.21), which is a result, not a failure. Timing, coverage holes and robustness can be one backup slide.

## What holds up

- **Exact, offline reproduction** from a clean `requirements.txt` environment on Python 3.12.13.
- **Independent recomputation.** My own code, separate from your scripts, fits a market model on sessions −250 to −30 vs SPY (≥ 150 obs) from `data/raw/prices.csv` and sums ARs over [−1,+1]. It reproduces `car_m1_p1` for all 1,436 episodes (max difference 8.5e-11). The means are +2.3922% (upgrades, n = 794) and −2.4171% (downgrades, n = 628), as in `window_summary.csv`. A fresh yfinance pull for 12 random episodes (seed 331) agrees to 6e-7.
- **Clustering done.** By my own count, about 46% of episodes share a day 0 with another episode in the same direction. Your `robustness.csv` already reports day-0 and two-way clustered t-statistics (8.2 and −6.9 two-way), and the README discusses them.
- **The ~1,000-row cap, checked rather than assumed** (`README.md:275-279`): the most-covered tickers have rows from before 2021, so nothing in the window rolled off.
- **Seed 7 items:** confounds (earnings, other calls, mixed days); timestamps (time-of-day table, an Eastern-time robustness row, during-market calls moved); and brokers with few calls (threshold fixed in advance, shrinkage, equality test).

## New findings

### B1 · Minor · `STATUS.md` is the Checkpoint 1 memo only

**Evidence:** `STATUS.md:1` "# Status memo (Checkpoint 1)" is the only heading. It was added in `b23f9cf` (2026-11-16, "Add STATUS.md (Checkpoint 1 memo)") and not updated since.

**Fix:** Add a current section: what v1 contains, what's left before the final, and who owns what.

**How to show it's fixed:** `STATUS.md` has a dated current-status section.

## How to respond

This audit is `audits/06_instructor_audit.md` in your repo (`04` and `05` are your own self-audit files). Fix what you can, then add `audits/07_audit_response.md`, replying to each **B** finding (no CP2 findings are still open): fixed (the commit), disputed (why), or disclosed as a limitation (where).

There's no separate deadline for this response. Keep working through these until your final deliverables are due: the final repo is audited again then.
