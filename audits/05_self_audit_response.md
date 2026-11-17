# Response to the self-audit of v1

Audit: `audits/04_self_audit_v1.md` (findings S1 to S11). All changes are on the branch `audit-fixes`.
Every number below is copied from `outputs/tables/`. CAR numbers are CAR[-1,+1] in percent,
upgrades / downgrades.

The headline did not move: clean upgrades +1.7372 (n 582), clean downgrades -1.2899 (n 419)
(`window_summary.csv`), 1,548 rating changes (`sample_summary.csv`).

| Finding | Severity | Status |
|---|---|---|
| S1 | Major | Disclosed (wording fixed; the bias is not measured) |
| S2 | Major | Disclosed, with a new robustness row (timestamps still not verified) |
| S3 | Major | Fixed (new rows; they weaken the t-statistics) |
| S4 | Minor | Fixed |
| S5 | Minor | Fixed (new row) and disclosed |
| S6 | Minor | Fixed (counted: no flag changes) |
| S7 | Minor | Fixed (counted; new rows) |
| S8 | Minor | Fixed (wording and counts) |
| S9 | Minor | (b) Fixed. (a), (c), (d) Not done, disclosed |
| S10 | Minor | Fixed |
| S11 | Minor | Fixed |

## S1. The universe is survivors only

**Disclosed.** Files: `README.md` (Research Sample, Threats to validity), `specs_tried.md`.

- "No hindsight" is removed. The README now says: the firm list uses 2020 membership and 2020
  volume, but only firms Yahoo can still price today could be ranked.
- 47 of the 505 members could not be priced (`n_members_no_yahoo_prices`, `n_sp500_members_2020`).
  From `data/raw/universe_dropped.csv`, they include Twitter, Activision Blizzard, Electronic Arts,
  Xilinx, Walgreens Boots Alliance, First Republic Bank and SVB Financial.
- Not done: the size of the bias is not measured. We have no 2020 volume for the dropped firms, so
  we cannot say how many would have made the top 50. That needs a data source that keeps dead firms.

## S2. Timestamps are read as UTC without outside proof

**Disclosed, with a new robustness row.** Files: `src/04_build_event_panel.py`, `src/05_results.py`,
`data/processed/events_eastern.csv` (new), `README.md`.

- New rows in `robustness.csv`, timestamps read as U.S. Eastern instead of UTC:
  all episodes +2.3999 (t 13.5, n 795) / -2.3790 (t -10.8, n 625);
  clean +1.7531 (t 10.4, n 587) / -1.3407 (t -7.9, n 421).
- Day 0 moves for 156 of the 1,548 rating changes (`n_rating_changes_day0_moves_if_eastern`).
- The headline does not depend on the time zone.
- Not done: no timestamp was checked against a broker note or another vendor. The README now says
  that UTC is an assumption and that the clock-time argument is circular.

## S3. The headline t-statistics assume independent episodes

**Fixed.** File: `src/05_results.py`. New rows in `robustness.csv` for the clean sample:

| standard errors | upgrades | downgrades |
|---|---|---|
| plain (as before) | t = 10.14 | t = -7.64 |
| clustered by day 0 | t = 9.52 | t = -7.15 |
| clustered two-way by stock and day 0 | t = 8.17 | t = -6.93 |

- This weakens the headline t-statistics. The plain ones were too large. The means do not change,
  and the result is still far from zero.
- The README shows the clustered t-statistics next to the plain ones, below the results block.
- A hand check recomputes the day-0-clustered standard error without a regression.
- Not done: the leaderboard intervals are still not clustered, and the regression still clusters by
  stock only. Both are stated in Threats to validity.

## S4. The time-of-day table counted 1,549 rows

**Fixed.** File: `src/01_get_ratings.py`.

- The hour table is now built after the duplicate row is removed. `rating_time_of_day.csv` adds up
  to 1,548. The 10:00 bucket went from 61 to 60, and four other shares changed in the fourth decimal.
- `share_before_open` (0.7913), `share_during_market` (0.197) and `share_after_close` (0.0116) in
  `sample_summary.csv` did not move. They were already computed on the 1,548 final rows.
- A hand check now asserts that the table adds up to the number of rating changes.

## S5. The clean sample uses information from after day 0

**Fixed (new row) and disclosed.** Files: `src/04_build_event_panel.py`, `src/05_results.py`, `README.md`.

- New row in `robustness.csv`: a clean sample that drops only on what is known by day 0 (an
  earnings day 0 at t = -2 to 0, or another call on the stock at t = -2 to -1):
  +1.8149 (t 10.6, n 617) / -1.3492 (t -8.1, n 459).
- It keeps more episodes and the numbers are slightly larger. It does not weaken the headline.
- Our choice: an earnings day 0 on the same day as the rating's day 0 counts as known.
- The README now says the clean sample is an event-study control, not a tradable filter.

## S6. Earnings timing placeholders use the whole sample

**Fixed (counted).** Files: `src/02_get_earnings.py`, `src/04_build_event_panel.py`, `src/05_results.py`.

- Only 12 earnings times are placeholders (`n_earnings_timing_placeholders`).
- Using earlier announcements only changes 0 of them (`n_earnings_timing_changed_past_only`).
- So 0 `near_earnings` flags change (`n_near_earnings_flags_changed_past_only`), and the robustness
  row is identical to the headline: +1.7372 (n 582) / -1.2899 (n 419).

## S7. The estimation window is not cleaned

**Fixed (counted, new rows).** Files: `src/04_build_event_panel.py`, `src/05_results.py`.

- Counts, non-mixed episodes (`sample_summary.csv`): an earnings day in the estimation window:
  1,422 of 1,422. Another rating change of the stock: 1,300. Clean episodes: 1,001 of 1,001 and 920.
- Rerun without them (`robustness.csv`):
  - no earnings day and no other rating change: n = 0 for both directions. This cannot be run,
    because every episode has an earnings day in its window. The empty row is kept in the file.
  - no other rating change: +1.7354 (t 2.8, n 54) / -1.5317 (t -2.6, n 27). The means are close to
    the headline, but with so few episodes the t-statistics are much smaller.
- Because dropping episodes does not work, we added one more row: the market model is estimated
  after removing every day within [-1,+1] of an earnings day 0 or another rating-change day 0 from
  the estimation window. Result: +1.7670 (t 10.3, n 582) / -1.3008 (t -7.7, n 419). No episode is lost
  (`n_episodes_dropped_cleaned_estimation_window` = 0). The headline does not depend on this.

## S8. Rank-1 broker numbers could be read as a finding

**Fixed.** Files: `README.md`, `src/05_results.py` (counts only).

- The README now says "the tests cannot tell brokers apart" before any rank-1 number, and calls the
  ranks a description, not a finding.
- Mixed-day calls: 37 in the whole sample (`n_calls_on_mixed_days`). In the headline no-earnings
  leaderboard, 16 of 1,201 calls are from mixed days and 69 are from multi-broker days
  (`n_calls_on_mixed_days_no_earnings_leaderboard`, `n_calls_on_multi_broker_days_no_earnings_leaderboard`).
- The leaderboard itself is unchanged.

## S9. Reproducibility

- **(b) Fixed.** File: `src/01_get_ratings.py`. A raw broker name that is not in
  `data/raw/broker_aliases.csv` now stops the run with an error that names it. Tested by removing
  one row from a copy: the run stopped with "ERROR: broker names not in data/raw/broker_aliases.csv:
  ['TD Cowen'] ...". All 105 raw names in the sample are covered today.
- **(a) Not done, on purpose.** The README results block is still rewritten in place by
  `src/05_results.py`. It is written from the tables so the README numbers are never typed by hand,
  and a rerun on the committed data leaves the file unchanged (checked: two runs, no diff).
- **(c) Not done.** `--refresh` is still not all-or-nothing. A failed ticker keeps its old file and
  `MANIFEST.csv` records the pull dates. We did not run `--refresh` for this response.
- **(d) Disclosed.** `data/processed/` is committed because the dashboard reads it. The README
  repository tree now says so.
- Checked for this response: `python run_all.py` twice on Python 3.13 on a second machine. Both
  runs passed the hand checks and the second run changed no file. On that machine the three PNG
  figures are redrawn with different bytes (font rendering), so the figures are not byte-identical
  across machines; the tables are.

## S10. `specs_tried.md` was not exact

**Fixed.** File: `specs_tried.md`.

- (a) F5 now lists the `clean` sample.
- (b) F8 is marked as the same run as F3. The count now says 40 entries, 32 distinct final
  specifications.
- (c) The git-history sentence is updated: the code and the first leaderboard entered git together
  in commit `02122c6`, so commit order cannot show which came first.
- (d) The text no longer states as fact that the 10-call threshold was set in advance. It says this
  is the team's record and cannot be verified from the repo.
- New entries F25 to F33 and D6 to D9 log every specification added for this response.

## S11. Missing threats to validity

**Fixed.** File: `README.md`, section 7. New or rewritten bullets:

- (a) the clean sample and the near-earnings flags use information from after day 0;
- (b) the estimation window is not cleaned;
- (c) current-vintage vendor data;
- (d) for during-market calls, the t = 0 return includes the part of the day before the call;
- (e) CAR[-20,-2] for clean downgrades is -0.79 (t = -1.6, `window_summary.csv`), which can mean
  calls follow price moves.
- The timestamp bullet now says that UTC is an assumption and that the argument for it is circular.
- The clustered-events bullet now reports the clustered t-statistics from S3.
