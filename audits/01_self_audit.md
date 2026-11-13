# Self-Audit — Analyst Rating Event Study

**Project:** The Team Today  
**Checkpoint:** HW8 — v0 end-to-end  
**Sample:** AAPL, MSFT, AMZN, JPM, NVDA  
**Audit date:** November 13, 2026

## 1. Skeptical Review: Findings

The project currently provides a working five-company exploratory event study and a live Streamlit dashboard. The analysis examines stock-price reactions around analyst upgrades and downgrades, with an additional comparison of events occurring near earnings announcements.

### Findings that are real

1. **Limited sample:** Five companies are sufficient for the HW8 prototype but are not representative of the broader market.
2. **Earnings confounding:** Analyst rating changes can occur near earnings announcements, which may independently affect stock prices.
3. **Small Mixed category:** Only two episodes are classified as Mixed. Their average and confidence interval are not reliable enough for meaningful conclusions.
4. **Potential dependence:** Multiple analyst calls can occur for the same company on the same date. Consolidating calls into event episodes helps, but observations may still have overlapping event windows.
5. **Timing uncertainty:** Yahoo Finance timestamps are used to assign rating changes to trading sessions. Daily returns cannot isolate the precise intraday market reaction.
6. **Exploratory confidence intervals:** The reported intervals are preliminary and do not adjust for every possible source of dependence.

### Issues to investigate

- Confirm that `run_all.py` rebuilds all processed data, tables, and figures from the raw inputs on a clean environment.
- Confirm that all merges use appropriate keys and validation checks.
- Reconcile the episode counts across the dashboard and saved output files, particularly the downgrade count.
- Confirm that the confidence intervals are clearly labeled and interpreted as preliminary.
- Add a complete record of specifications tested in `specs_tried.md`.

## 2. What Has Been Completed and What Remains Open

### Completed

- Collected Yahoo Finance analyst rating history for five companies.
- Collected adjusted daily prices for the five companies and SPY.
- Collected historical earnings-date information.
- Classified qualifying analyst rating changes as upgrades or downgrades.
- Assigned rating events to trading sessions using a pre-market versus after-market timing convention.
- Created event-level and event-day datasets.
- Consolidated multiple calls on the same company and event date into event episodes.
- Calculated cumulative abnormal returns around analyst rating changes.
- Created saved tables and an event-study figure.
- Built and deployed a Streamlit dashboard with Introduction, Methodology, Results, and Explore sections.

### Still open

- Verify that the complete pipeline runs from scratch using one command.
- Verify that every dashboard result comes directly from saved output files.
- Reconcile the episode counts across the dashboard and underlying files.
- Improve the treatment of overlapping event windows and statistical dependence.
- Document all specifications tested.
- Complete manual checks of representative observations at each pipeline stage.
- Expand the sample beyond five companies for the later final-project stage.

## 3. Ten-Point Project Checklist

| # | Requirement | Status | Notes |
|---|---|---|---|
| 1 | Reproducibility | NOT YET | `run_all.py` exists; a clean end-to-end run still needs verification. |
| 2 | Input provenance | PROBLEM | Yahoo Finance is identified as the source; retrieval dates and reproducible download details need fuller documentation. |
| 3 | Correct unit of observation | NOT YET | Event episodes are consolidated, but uniqueness and merge-validation checks need confirmation. |
| 4 | No look-ahead | PROBLEM | Trading-session assignment is implemented, but exact publication timing cannot be independently verified from daily data. |
| 5 | No LLM leakage | OK | The current analysis does not rely on an LLM-generated predictive variable. |
| 6 | No p-hacking | NOT YET | A complete specification log has not yet been documented. |
| 7 | Magnitudes, not just stars | OK | CAR magnitudes are reported in percentage terms, although economic significance remains exploratory. |
| 8 | Checks by hand | NOT YET | Manual verification of representative observations and calculations remains to be documented. |
| 9 | Honest limitations | OK | The small sample and exploratory nature of the results are disclosed; the README should retain a full threats-to-validity section. |
| 10 | Team understanding | NOT YET | Every team member should be able to explain the data, timing convention, event study, and limitations. |

## 4. Next Steps

1. Verify that `run_all.py` rebuilds the project from scratch.
2. Reconcile dashboard figures and episode counts with the saved CSV files.
3. Complete manual checks of selected raw observations, event assignments, and CAR calculations.
4. Create `specs_tried.md` and document the specifications evaluated.
5. Improve the README's explanation of data provenance, reproducibility, and threats to validity.
6. Keep the five-company sample for HW8 and expand the universe during the later final-project stage.

**Overall assessment:** The project has a functioning end-to-end prototype and a live dashboard. The remaining work is primarily verification, documentation, and strengthening the research design before expanding the sample.
