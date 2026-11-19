"""Headless checks for the dashboard. Run from anywhere:

    python dashboard/tests/test_app.py

Each test_* function also works under pytest, but pytest is not required.
Checks: every page renders without an exception or st.error and shows at least the expected number
of Plotly charts; the selectors and filters work (including a filter that matches nothing) and the
single-event view; key numbers on screen equal the source files; and everything the dashboard
computes itself (the clean_window CAR path, daily AR from CAR differences, per-broker and
per-company means, the single-event CAR, the funnel's firm step) is checked against pipeline output.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "dashboard" / "app.py")
TABLES = ROOT / "outputs" / "tables"
DIRS = ["upgrade", "downgrade"]
PAGES = ["Introduction", "Methodology", "Results", "Broker leaderboard", "Explore"]
# minimum number of Plotly charts each page renders with its default settings
MIN_CHARTS = {"Introduction": 2, "Methodology": 5, "Results": 7, "Broker leaderboard": 3, "Explore": 5}
sys.path.insert(0, str(ROOT / "dashboard"))


def fresh():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def ok(at, where):
    assert not at.exception, f"{where}: {at.exception}"
    assert not at.error, f"{where}: {[e.value for e in at.error]}"


def charts(at):
    return len(at.get("plotly_chart"))


def goto(at, page):
    at.sidebar.radio(key="page").set_value(page).run()
    ok(at, page)
    return at


def all_text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [str(m.value) for m in at.metric] + [w.value for w in at.warning] + [i.value for i in at.info]
    return "\n".join(parts)


def test_no_image_charts():
    """Image charts break on Streamlit Cloud (the media endpoint returns 500), so none are allowed."""
    for f in (ROOT / "dashboard").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        # built from pieces so a plain grep of dashboard/ for these names finds nothing
        for bad in ["matplot" + "lib", "st." + "pyplot", "st." + "image"]:
            assert bad not in text, f"{f.name} contains {bad}"


def test_every_page_renders():
    at = fresh()
    for page in PAGES:
        goto(at, page)
        assert charts(at) >= MIN_CHARTS[page], f"{page}: {charts(at)} Plotly charts, expected {MIN_CHARTS[page]}"


def test_results_samples():
    at = goto(fresh(), "Results")
    box = at.selectbox(key="res_sample")
    assert box.value == "clean"
    ws = pd.read_csv(TABLES / "window_summary.csv")
    for s in dict.fromkeys(ws["sample"]):
        at.selectbox(key="res_sample").set_value(s).run()
        ok(at, f"Results/{s}")
        assert charts(at) >= MIN_CHARTS["Results"], f"Results/{s}: {charts(at)} charts"
    for days in [20, 1]:
        at.slider(key="res_ar_days").set_value(days).run()
        ok(at, f"Results/AR days {days}")
    for m in dict.fromkeys(pd.read_csv(TABLES / "earnings_regression.csv")["model"]):
        at.radio(key="res_reg").set_value(m).run()
        ok(at, f"Results/regression {m}")
        assert charts(at) >= MIN_CHARTS["Results"]


def test_methodology_coverage_toggle():
    at = goto(fresh(), "Methodology")
    for v in ["rating_changes_kept", "raw_rows"]:
        at.radio(key="me_cov").set_value(v).run()
        ok(at, f"Methodology/{v}")
        assert charts(at) >= MIN_CHARTS["Methodology"]


def test_leaderboard_toggles():
    at = goto(fresh(), "Broker leaderboard")
    assert at.selectbox(key="lb_sample").value == "no_earnings"
    lb = pd.read_csv(TABLES / "broker_leaderboard.csv")
    for s in dict.fromkeys(lb["sample"]):
        for d in ["upgrade", "downgrade"]:
            at.selectbox(key="lb_sample").set_value(s)
            at.radio(key="lb_dir").set_value(d).run()
            ok(at, f"Leaderboard/{s}/{d}")
            assert charts(at) >= MIN_CHARTS["Broker leaderboard"], f"Leaderboard/{s}/{d}: {charts(at)} charts"
    at.checkbox(key="lb_unranked").check().run()
    ok(at, "Leaderboard/unranked")


def test_explore_filters():
    at = goto(fresh(), "Explore")
    ev = pd.read_csv(ROOT / "data" / "processed" / "events.csv")
    assert at.metric[0].value == f"{len(ev):,}"
    combos = [
        dict(ex_firms=["AAPL", "MSFT"]),
        dict(ex_dir="upgrade", ex_earn="no"),
        dict(ex_dir="downgrade", ex_earn="yes", ex_years=(2023, 2024)),
        dict(ex_brokers=["JP Morgan"], ex_firms=[]),
    ]
    # matches nothing: a real firm and a real broker that never rated it
    pairs = set(zip(ev["ticker"], ev["broker"]))
    firm = sorted(ev["ticker"].unique())[0]
    broker = next(b for b in sorted(ev["broker"].unique()) if (firm, b) not in pairs)
    combos.append(dict(ex_firms=[firm], ex_brokers=[broker], ex_dir="both", ex_earn="all"))
    for combo in combos:
        for key, val in combo.items():
            w = {"ex_firms": at.multiselect, "ex_brokers": at.multiselect, "ex_dir": at.radio,
                 "ex_earn": at.selectbox, "ex_years": at.slider}[key](key=key)
            w.set_value(val)
        at.run()
        ok(at, f"Explore {combo}")
        if at.metric[0].value != "0":
            assert charts(at) >= 3, f"Explore {combo}: {charts(at)} charts"
    assert at.metric[0].value == "0", at.metric[0].value
    assert any("No rating changes match" in i.value for i in at.info)
    assert charts(at) == 0


def test_explore_single_event():
    """Pick several rating changes; the caption's CAR[-1,+1] must match events.csv, and the panel CAR the
    chart plots must reproduce events.csv (CAR[-1,+1] = CAR(+1) - CAR(-2))."""
    at = goto(fresh(), "Explore")
    ev = pd.read_csv(ROOT / "data" / "processed" / "events.csv")
    assert len(at.selectbox(key="ex_event").options) == len(ev)
    for eid in [ev["event_id"].iloc[0], ev["event_id"].iloc[len(ev) // 2], ev["event_id"].iloc[-1]]:
        at.selectbox(key="ex_event").set_value(eid).run()
        ok(at, f"Explore single event {eid}")
        assert charts(at) >= MIN_CHARTS["Explore"]
        car = 100 * ev.set_index("event_id").loc[eid, "car_m1_p1"]
        assert any(f"is {car:+.2f}%" in c.value for c in at.caption), f"{eid}: CAR[-1,+1] {car:+.2f}% not shown"
    # the single-event list follows the filter
    at.multiselect(key="ex_firms").set_value(["AAPL"]).run()
    ok(at, "Explore AAPL")
    assert len(at.selectbox(key="ex_event").options) == int((ev["ticker"] == "AAPL").sum())
    # histogram, scatter and single event always; group bars only where a group has enough calls
    assert charts(at) >= 3

    pan = pd.read_csv(ROOT / "data" / "processed" / "event_panel.csv", usecols=["event_id", "t", "CAR"])
    w = pan.pivot(index="event_id", columns="t", values="CAR")
    diff = (w[1] - w[-2]).reindex(ev["event_id"]).to_numpy() - ev["car_m1_p1"].to_numpy()
    assert np.nanmax(np.abs(diff)) < 1e-8, "event_panel CAR does not reproduce events.csv car_m1_p1"
    assert not np.isnan(diff).any(), "some rating changes have no t = -2 / +1 rows in event_panel.csv"


def test_numbers_match_files():
    ws = pd.read_csv(TABLES / "window_summary.csv")
    summ = pd.read_csv(TABLES / "sample_summary.csv").set_index("metric")["value"]
    lb = pd.read_csv(TABLES / "broker_leaderboard.csv")
    at = fresh()
    text = all_text(at)
    clean = ws[(ws["sample"] == "clean") & (ws["window"] == "[-1,+1]")].set_index("direction")
    for d in ["upgrade", "downgrade"]:
        r = clean.loc[d]
        expect = f"**{r['mean_pct']:+.2f}%** on average (t = {r['t_stat']:.1f}, {int(r['n'])} episodes)"
        assert expect in text, f"headline {d} not shown as: {expect}"
        m = [x for x in at.metric if x.label == f"{d.capitalize()} reaction"][0]
        assert m.value == f"{r['mean_pct']:+.2f}%", m.value
    firms = [m for m in at.metric if m.label == "Firms"][0]
    assert firms.value == str(int(summ["n_firms"])), firms.value

    at = goto(at, "Broker leaderboard")   # defaults: upgrades, no_earnings
    top = lb[(lb["sample"] == "no_earnings") & (lb["direction"] == "upgrade") & (lb["rank"] == 1)].iloc[0]
    df = at.dataframe[0].value
    assert df.iloc[0]["Broker"] == top["broker"], (df.iloc[0]["Broker"], top["broker"])
    assert df.iloc[0]["Calls"] == top["n"]
    assert df.iloc[0]["Mean CAR[-1,+1]"] == f"{top['mean_pct']:+.2f}%"

    # call-weighted broker mean (the dashed line) equals the pipeline's no-earnings call mean
    for d in ["upgrade", "downgrade"]:
        s = lb[(lb["sample"] == "no_earnings") & (lb["direction"] == d)]
        ref = (s["n"] * s["mean_pct"]).sum() / s["n"].sum()
        assert abs(ref - float(summ[f"mean_car_m1_p1_pct_no_earnings_calls_{d}"])) < 1e-3

    # Explore with no filters: per-call means equal robustness.csv 'unit = rating change'
    at = goto(at, "Explore")
    rb = pd.read_csv(TABLES / "robustness.csv").set_index(["spec", "direction"])
    for d, label in [("upgrade", "Upgrades"), ("downgrade", "Downgrades")]:
        m = [x for x in at.metric if x.label.startswith(label)][0]
        assert m.value == f"{rb.loc[('unit = rating change (not episode)', d), 'mean_pct']:+.2f}%", m.value


def test_panel_path_reproduces_file():
    import ui_data
    computed = ui_data._panel_paths.__wrapped__(
        str(ROOT / "data/processed/events.csv"), str(ROOT / "data/processed/episodes.csv"),
        str(ROOT / "data/processed/event_panel.csv"), ())
    cbd = pd.read_csv(TABLES / "car_by_day.csv")
    m = cbd.merge(computed, on=["sample", "direction", "t"], suffixes=("", "_dash"), validate="1:1")
    assert len(m) == len(cbd), "every row of car_by_day.csv should be reproduced"
    assert (m["n"] == m["n_dash"]).all()
    for c in ["mean_pct", "ci_lo_pct", "ci_hi_pct"]:
        assert np.abs(m[c] - m[f"{c}_dash"]).max() < 1e-9, c
    cw = computed[computed["sample"] == "clean_window"]
    ws = pd.read_csv(TABLES / "window_summary.csv")
    n_ws = ws[(ws["sample"] == "clean_window") & (ws["window"] == "[-1,+1]")].set_index("direction")["n"]
    for d in ["upgrade", "downgrade"]:
        assert int(cw.loc[cw["direction"] == d, "n"].iloc[0]) == int(n_ws[d])
    # n is constant across days in every computed sample, so daily AR can be read off the path
    import ui_charts
    for s, path in computed.groupby("sample"):
        assert ui_charts.daily_ar_from_path(path) is not None, s


def test_daily_ar_from_car_path():
    """Daily AR = difference of mean CAR (n constant) must equal the pipeline's mean AR by day."""
    import ui_charts
    cbd = pd.read_csv(TABLES / "car_by_day.csv")
    abt = pd.read_csv(TABLES / "ar_by_day_timing.csv")
    abt = abt[abt["timing"] == "all"]
    checked = 0
    for s, path in cbd.groupby("sample"):
        ar = ui_charts.daily_ar_from_path(path)
        assert ar is not None, f"{s}: n varies across days"
        assert set(ar["t"]) == set(path["t"])
        m = abt[abt["sample"] == s].merge(ar, on=["direction", "t"], suffixes=("", "_dash"))
        if m.empty:
            continue
        assert (m["n"] == m["n_dash"]).all()
        # both files round to 4 decimals, so a difference of two rounded CARs can be off by up to 1.5e-4
        assert np.abs(m["mean_ar_pct"] - m["ar_pct"]).max() <= 1.5e-4 + 1e-9, s
        checked += len(m)
    assert checked > 0


def test_group_means_match_pipeline():
    """Explore's per-broker means (no filter) equal broker_leaderboard.csv sample 'all';
    per-company means, weighted by n, add back up to the per-call means in robustness.csv."""
    import ui_data
    ev = pd.read_csv(ROOT / "data" / "processed" / "events.csv")
    lb = pd.read_csv(TABLES / "broker_leaderboard.csv")
    g = ui_data.group_means(ev, "broker", 1)
    m = lb[lb["sample"] == "all"].merge(g, left_on=["broker", "direction"], right_on=["group", "direction"],
                                        suffixes=("", "_dash"), validate="1:1")
    assert len(m) == (lb["sample"] == "all").sum()
    assert (m["n"] == m["n_dash"]).all()
    assert np.abs(m["mean_pct"] - m["mean_pct_dash"]).max() < 1e-3
    rb = pd.read_csv(TABLES / "robustness.csv").set_index(["spec", "direction"])
    gc = ui_data.group_means(ev, "ticker", 1)
    for d in ["upgrade", "downgrade"]:
        s = gc[gc["direction"] == d]
        assert abs((s["n"] * s["mean_pct"]).sum() / s["n"].sum()
                   - rb.loc[("unit = rating change (not episode)", d), "mean_pct"]) < 1e-3
    assert (ui_data.group_means(ev, "ticker", 10)["n"] >= 10).all()


def takeaways(at):
    """The text inside every 'Show takeaway' expander on the current page."""
    import ui_takeaways
    return ["\n".join(m.value for m in e.markdown) for e in at.expander if e.label == ui_takeaways.LABEL]


def test_takeaways():
    """Each page shows its takeaway boxes, and the numbers in them equal the tables (and follow the controls)."""
    expected = {"Introduction": 1, "Methodology": 3, "Results": 3, "Broker leaderboard": 2, "Explore": 1}
    ws = pd.read_csv(TABLES / "window_summary.csv")
    rb = pd.read_csv(TABLES / "robustness.csv").set_index(["spec", "direction"])
    ec = pd.read_csv(TABLES / "earnings_comparison.csv").set_index(["direction", "earnings"])
    eq = pd.read_csv(TABLES / "broker_equality_test.csv")
    summ = pd.read_csv(TABLES / "sample_summary.csv").set_index("metric")["value"]
    two_way = "clean (headline), SE clustered two-way by stock and day0"
    eastern = "timestamps read as Eastern (not UTC): clean"

    def react(sample, d, col):
        return ws[(ws["sample"] == sample) & (ws["window"] == "[-1,+1]") & (ws["direction"] == d)][col].iloc[0]

    at = fresh()
    for page in PAGES:
        goto(at, page)
        boxes = takeaways(at)
        assert len(boxes) == expected[page], f"{page}: {len(boxes)} takeaway boxes, expected {expected[page]}"
        for b in boxes:
            assert b and "{" not in b, f"{page}: empty or unfilled takeaway: {b[:80]}"
        text = "\n".join(boxes)
        must = []
        if page == "Introduction":
            must = [f"{react('clean', d, 'mean_pct'):+.2f}%" for d in DIRS] + \
                   [f"t = {rb.loc[(two_way, 'upgrade'), 't_stat']:.1f} and {rb.loc[(two_way, 'downgrade'), 't_stat']:.1f}"]
        elif page == "Methodology":
            must = [f"{rb.loc[(eastern, d), 'mean_pct']:+.2f}%" for d in DIRS] + \
                   [f"for {int(float(summ['n_rating_changes_day0_moves_if_eastern']))} of"]
        elif page == "Results":
            must = [f"{react('clean', d, 'mean_pct'):+.2f}% (t = {react('clean', d, 't_stat'):.1f}, "
                    f"{int(react('clean', d, 'n'))} episodes)" for d in DIRS]
            must += [f"{ec.loc[(d, e), 'mean_pct']:+.2f}%" for d in DIRS
                     for e in ["earnings overlap", "no earnings overlap"]]
        elif page == "Broker leaderboard":
            q = eq[(eq["sample"] == "no_earnings") & (eq["direction"] == "upgrade")].set_index("test")
            must = [f"p = {q.loc['one-way ANOVA F', 'p_value']:.3f} (ANOVA)",
                    f"median {int(float(summ['median_calls_per_broker_direction']))} per broker"]
        elif page == "Explore":
            unit = "unit = rating change (not episode)"
            must = [f"{rb.loc[(unit, d), 'mean_pct']:+.2f}%" for d in DIRS]
        for m in must:
            assert m in text, f"{page}: takeaway does not show {m!r}"

    # the boxes follow the page controls
    at = goto(at, "Results")
    at.selectbox(key="res_sample").set_value("near_earnings").run()
    ok(at, "Results/near_earnings")
    text = "\n".join(takeaways(at))
    for d in DIRS:
        assert f"{react('near_earnings', d, 'mean_pct'):+.2f}%" in text, f"Results takeaway ignores the sample ({d})"
    at = goto(at, "Broker leaderboard")
    at.radio(key="lb_dir").set_value("downgrade").run()
    ok(at, "Leaderboard/downgrade")
    q = eq[(eq["sample"] == "no_earnings") & (eq["direction"] == "downgrade")].set_index("test")
    assert f"p = {q.loc['one-way ANOVA F', 'p_value']:.3f} (ANOVA)" in "\n".join(takeaways(at))


def test_funnel_firm_step():
    """The funnel's 'priced, full history, one share class' step (members minus the three drop counts)
    equals the members file minus universe_dropped.csv."""
    summ = pd.read_csv(TABLES / "sample_summary.csv").set_index("metric")["value"].astype(str)
    members = int(float(summ["n_sp500_members_2020"]))
    dropped = sum(int(float(summ[k])) for k in
                  ["n_members_no_yahoo_prices", "n_members_short_2020_history", "n_extra_share_classes"])
    n_members_file = len(pd.read_csv(ROOT / "data" / "raw" / "sp500_members_2020-12-31.csv"))
    n_dropped_file = len(pd.read_csv(ROOT / "data" / "raw" / "universe_dropped.csv"))
    assert members == n_members_file, (members, n_members_file)
    assert dropped == n_dropped_file, (dropped, n_dropped_file)
    assert members - dropped >= int(float(summ["n_firms"]))


if __name__ == "__main__":
    failed = 0
    tests = [(n, f) for n, f in dict(globals()).items() if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:  # report every failure, then exit non-zero
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
