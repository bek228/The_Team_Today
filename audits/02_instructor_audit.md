# Instructor audit: The Team Today, Checkpoint 2

**Repo:** bek228/The_Team_Today · **Audited commit:** `206e3e9` (2026-11-13, `main`) · **Seed:** 7, do analyst upgrades move prices, and does the broker matter?

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

The event-study logic is right. Timestamps are converted from UTC to Eastern, each call goes to the correct session, and CAR windows must be complete. My own code, run on your committed raw files, reproduces your headline exactly: upgrades +2.37% over 62 episodes, downgrades −1.67% over 56. Three things need fixing first:
1. The documented setup doesn't run: `pip install -r requirements.txt` then `python run_all.py` fails on line 8 (A1).
2. Every run re-downloads all data through "today" and overwrites your raw files, so your numbers change from run to run (A2).
3. Your earnings comparison pools upgrades with downgrades, so it can't answer the confound question. Split by direction, much of the headline comes from calls that coincide with earnings (A3).

`STATUS.md` and `specs_tried.md` are also missing (A4).

| Check | Result |
|---|---|
| Reruns from scratch | ❌ fails with only `requirements.txt` installed (A1). With IPython added, it runs (exit 0, 14.6 s) but changes the README numbers (A2) |
| Inputs have provenance | ⚠️ the source (yfinance) is named, but there are no pull dates and raw files are overwritten on each run (A2) |
| Keys unique, merges validated | ⚠️ `validate=` on the merges (`pipeline.py:614, 704, 1008`). No `assert` on the episode key |
| No look-ahead / survivorship | ✅ timing rule. ⚠️ five of today's largest firms (A6) |
| LLM leakage handled | n/a |
| `specs_tried.md` complete | ❌ missing (A4) |
| Magnitudes discussed | ⚠️ CARs in percent, no costs |
| Hand checks | ❌ none in the repo (self-audit: "NOT YET"). The auditor's recomputation matches |
| Threats to validity | ✅ README §7 "Limitations" |
| Every number traces to `outputs/` | ✅ README table = `upgrade_downgrade_summary.csv` |

## What holds up

- **Headline recomputed independently.** My own code reads your committed `data/raw/ratings_raw.csv` and `prices_raw.csv` and applies the README's rules: up/down actions only, from 2021-01-01, UTC → ET, before 9:30 ET = that session, AR = stock − SPY, full 3-day window, one episode per stock-session. It gives 138 calls (70 up, 68 down), 3 not yet assigned, and 121 episodes. Upgrades: 62 episodes, CAR[−1,+1] 0.023695. Downgrades: 56, −0.016659. Mixed: 2, −0.032939. All identical to `outputs/tables/upgrade_downgrade_summary.csv`.
- **Seed 7, timestamps:** `pipeline.py:162-163` parses Yahoo's times as UTC and converts to ET (e.g. 12:45 UTC → 07:45 ET). Calls at or after 9:30 ET go to the next session. Two things confirm the dating: the signed abnormal return in `event_day_panel.csv` peaks on day 0 (+1.76%, vs. +0.54% on day −1), and `window_car()` (`pipeline.py:683-692`) returns NaN rather than a partial sum when a day is missing.
- **Simultaneous calls** on the same stock and session are consolidated into one episode.

## Findings

### A1 · Blocking · The documented setup fails: `IPython` is imported but not in `requirements.txt`

**Evidence:** `src/pipeline.py:8` reads `from IPython.display import display`. In a fresh environment with only `pip install -r requirements.txt` (pandas, numpy, yfinance, matplotlib, streamlit, scipy), `python run_all.py` exits with code 1 after 0.05 s: `ModuleNotFoundError: No module named 'IPython'`. The script also calls `display()` throughout (left over from the notebook).

**Why it matters:** Following the README's steps exactly on a fresh machine reproduces nothing. It's a one-line fix.

**Fix:** Replace `display(...)` with `print(...)` (or `print(df.head().to_string())`) and remove the import, or add `ipython` to `requirements.txt`. Then pin versions (`pip freeze > requirements.txt`).

**How to show it's fixed:** The auditor will create a clean environment from `requirements.txt` only and run `python run_all.py`.

### A2 · Major · Every run re-downloads all data through "today" and overwrites the raw files, so the results drift

**Evidence:**
- `pipeline.py:27` sets `END_DATE = today + 1` ("to include today's data"). Lines 69, 108 and 145 always download and overwrite `data/raw/ratings_raw.csv`, `prices_raw.csv` and `earnings_dates_raw.csv`. There is no cache check and no pull date.
- My rerun on 2026-11-15 changed your README results:

  | | Committed (README) | Rerun 2026-11-15 |
  |---|---|---|
  | Downgrade episodes with CAR[−1,+1] | 56 | 57 |
  | Downgrade mean CAR[−1,+1] | −1.666% | −1.708% |
  | Upgrade mean CAR[−1,+1] | 2.3695% | 2.3707% |

  The causes:
  - NVDA's 2026-11-12 downgrade gained its day +1.
  - AAPL's 2026-11-11 episode moved from 0.614% to 0.690% because the 2026-11-12 close changed between pulls.
  - Yahoo's ratings list itself changed: 4,385 → 4,346 rows (it drops its oldest records; all 39 dropped rows are pre-2021, so the sample wasn't affected this time).

**Why it matters:** Nobody can reproduce the numbers in your README, and a run made during the trading day uses a provisional close.

**Fix:** Fix `END_DATE` (e.g. `"2026-11-12"`, the last full day used). Make each download step reuse the committed raw file if it exists, with a `--refresh` flag to pull again. Record the pull date of each raw file in the README.

**How to show it's fixed:** Two consecutive runs of `python run_all.py` produce byte-identical `outputs/tables/*.csv` matching the README.

### A3 · Major · The earnings comparison mixes upgrades and downgrades, and earnings-day calls drive much of the headline

**Evidence:**
- `pipeline.py:936-958` summarizes `episodes` by `earnings_overlap` only, pooling upgrades (positive CARs) with downgrades (negative CARs). So `outputs/tables/earnings_comparison.csv` reports a "No earnings overlap" mean CAR[−1,+1] of −0.06%, which is an average of +1.4% and −1.4%.
- Split by direction (from your `event_reaction_episodes.csv`):

  | CAR[−1,+1] | No earnings overlap | Earnings overlap |
  |---|---|---|
  | Upgrades | +1.39% (n = 47) | **+5.45%** (n = 15) |
  | Downgrades | −1.35% (n = 48) | **−3.56%** (n = 8) |

- 17 of 121 episodes also have another episode of the same stock within 2 trading days, so their [−1,+1] windows overlap. Dropping them: upgrades +2.12% (57), downgrades −1.35% (46) (auditor's recount).

**Why it matters:** "Confounds (changes issued right after earnings)" is the first item on this seed's audit list. Your headline (+2.37% / −1.67%) includes the earnings-day calls, so a large part of it may be the earnings news, not the analysts.

**Fix:** Make the main result "clean" episodes: no earnings within ±1 session, and no other call within the window. Report the earnings-overlap episodes separately by direction, and test direction × earnings in one regression (CAR on upgrade dummy, earnings dummy and their interaction, clustered by stock).

**How to show it's fixed:** `earnings_comparison.csv` has rows by direction, and the README headline uses clean episodes.

### A4 · Major · Required files are missing: `STATUS.md` and `specs_tried.md`

**Evidence:** Neither file exists on any branch (`git ls-tree -r origin/main`; there are no other branches or PRs). Your self-audit lists `specs_tried.md` as to-do (items 6 and step 4). There is also no hand check in the repo (self-audit item 8: "NOT YET").

**Fix:**
- Add `STATUS.md` (the Checkpoint 1 memo, updated).
- Add `specs_tried.md` listing every window, filter and grouping you have run, including the notebook's versions.
- Add a small hand check, e.g. recompute one episode's CAR from `prices_raw.csv` and assert it equals `events.csv`.

**How to show it's fixed:** The files exist, and the hand check runs inside `run_all.py`.

### A5 · Minor · A failed earnings download is tolerated silently

**Evidence:** `pipeline.py:117-142` catches any download error per ticker and continues. In the audit environment, Yahoo's earnings page was blocked (proxy 403). The run still exited 0, with `earnings_dates_raw.csv` empty, every `earnings_overlap` missing, and an `earnings_comparison.csv` with no usable rows. The same happens to you if Yahoo rate-limits the request.

**Fix:** Stop with an error if any ticker's earnings dates fail to download, or reuse the cached file (see A2).

**How to show it's fixed:** With the earnings host unreachable, `run_all.py` stops with a clear message instead of writing empty outputs.

### A6 · Minor · Sample and broker plan

**Evidence:**
- The five stocks are today's mega caps (`pipeline.py:22`), studied from 2021, which is survivorship in how the sample was chosen.
- `PROPOSAL.md` and the dashboard ask "does the broker matter?", but no broker-level table exists yet. With 138 calls across many brokers, most brokers have one or two calls.

**Fix:** When you expand to ~50 firms, choose them by size at the start of the sample, not today. For brokers, set a minimum number of calls before ranking, report confidence intervals, and log the threshold in `specs_tried.md` before looking at the leaderboard. This seed's audit list includes "brokers with few calls ranked by noise".

**How to show it's fixed:** The selection rule and broker threshold are documented, and a broker table with CIs exists in `outputs/`.

## How to respond

This audit is `audits/02_instructor_audit.md` in your repo. Fix what you can, then add `audits/03_audit_response.md`, replying to each finding ID: fixed (the commit), disputed (why), or disclosed as a limitation (where).

**Deadline: Saturday, November 21, 2026.**
