# Response to the instructor audit of Checkpoint 2

Audit: `audits/02_instructor_audit.md` (audited commit `206e3e9`). All fixes below are in commit `02122c6` on the branch `v1-pipeline`, which replaces the five-stock prototype with a 50-firm pipeline. The prototype is kept in `dev/` for reference.

| Finding | Severity | Status |
|---|---|---|
| A1 | Blocking | Fixed |
| A2 | Major | Fixed |
| A3 | Major | Fixed, with one difference from the suggested rule (disclosed) |
| A4 | Major | Fixed |
| A5 | Minor | Fixed |
| A6 | Minor | Fixed, with two limitations disclosed |

## A1. The documented setup fails (IPython not in requirements)

**Fixed** in `02122c6`. The pipeline no longer imports IPython or calls `display()`. `requirements.txt` lists every import with pinned versions and states the Python version needed (3.12 or newer; we ran 3.14).

To check: in a clean environment, `pip install -r requirements.txt`, then `python run_all.py`.

## A2. Every run re-downloads and the results drift

**Fixed** in `02122c6`.

- The sample window is fixed in `src/_common.py`: rating changes from 2021-01-01 to 2026-10-09, prices to 2026-11-13. Nothing depends on today's date.
- The raw Yahoo pulls are committed in `data/raw/`. `python run_all.py` rebuilds everything from that snapshot without using the network. `python run_all.py --refresh` pulls again.
- `data/raw/MANIFEST.csv` records the source, pull time and row count of every raw file. The README's data provenance table points to it.

To check: two runs of `python run_all.py` give byte-identical files in `outputs/tables/` and `data/processed/`, and the README results block (written by `src/05_results.py`) matches them.

## A3. The earnings comparison pools upgrades and downgrades

**Fixed** in `02122c6`.

- The README headline now uses clean episodes: no earnings nearby, no other call on the same stock within two trading days, and not a mixed upgrade/downgrade day. See the `clean` rows of `outputs/tables/window_summary.csv`.
- `outputs/tables/earnings_comparison.csv` has rows by direction and by earnings overlap.
- `outputs/tables/earnings_regression.csv` holds the regression of CAR[-1,+1] on an upgrade dummy, an earnings dummy and their interaction, with standard errors clustered by stock.

One difference from the audit's suggestion: our "near earnings" flag covers one trading day before to two trading days after the earnings day, which is wider than ±1 session, because analysts usually re-rate just after a report. This is stated in the README methodology.

## A4. Required files are missing

**Fixed.**

- `specs_tried.md` (in `02122c6`) lists every specification run, including the prototype's.
- Hand checks run as the last step of `run_all.py` (`src/99_hand_checks.py`, described in `docs/hand_checks.md`). They recompute one number per pipeline step from the raw files, including one episode's CAR from `data/raw/prices.csv`.
- `STATUS.md` is added in commit `b23f9cf`.

## A5. A failed earnings download is tolerated silently

**Fixed** in `02122c6`. If a raw file is missing and its download fails, the run stops with an error naming the tickers and writes nothing. We tested this on a copy of the repo by deleting one cached earnings file and blocking the network: `run_all.py` exited with code 1 and the message "ERROR: earnings download failed and no cached file exists for ['AAPL'] ...".

## A6. Sample and broker plan

**Fixed** in `02122c6`, with two limitations disclosed.

- **Sample:** the 50 firms are the S&P 500 members on December 31, 2020, ranked by average daily dollar trading volume in 2020 (`src/00_universe.py`, `data/raw/universe.csv`).
- **Brokers:** only brokers with at least 10 calls in a direction are ranked. `outputs/tables/broker_leaderboard.csv` reports each broker's mean reaction with a 95% confidence interval and a shrunk mean, and `outputs/tables/broker_equality_test.csv` tests whether ranked brokers differ at all.

Disclosed as limitations (README, "Threats to validity"):

- Some 2020 index members can no longer be priced on Yahoo (delisted, acquired or renamed) and could not be ranked. They are listed in `data/raw/universe_dropped.csv`.
- The 10-call threshold was set before the leaderboard was first computed and was not changed afterward, and `specs_tried.md` says so. Git history cannot prove that order, because the pipeline was first committed after it was built.
