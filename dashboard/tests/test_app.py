"""Headless checks for the dashboard. Run from anywhere:

    python dashboard/tests/test_app.py

Each test_* function also works under pytest, but pytest is not required.
Checks: every page renders without an exception, the selectors and filters work (including a
filter that matches nothing), key numbers on screen equal the source files, and the CAR path the
dashboard computes for clean_window uses a method that reproduces car_by_day.csv exactly.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "dashboard" / "app.py")
TABLES = ROOT / "outputs" / "tables"
PAGES = ["Introduction", "Methodology", "Results", "Broker leaderboard", "Explore"]


def fresh():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def goto(at, page):
    at.sidebar.radio(key="page").set_value(page).run()
    assert not at.exception, f"{page}: {at.exception}"
    assert not at.error, f"{page}: {[e.value for e in at.error]}"
    return at


def all_text(at):
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [str(m.value) for m in at.metric] + [w.value for w in at.warning] + [i.value for i in at.info]
    return "\n".join(parts)


def test_every_page_renders():
    at = fresh()
    for page in PAGES:
        goto(at, page)


def test_results_samples():
    at = goto(fresh(), "Results")
    box = at.selectbox(key="res_sample")
    assert box.value == "clean"
    ws = pd.read_csv(TABLES / "window_summary.csv")
    for s in dict.fromkeys(ws["sample"]):
        at.selectbox(key="res_sample").set_value(s).run()
        assert not at.exception, f"Results/{s}: {at.exception}"
        assert not at.error, f"Results/{s}: {[e.value for e in at.error]}"


def test_leaderboard_toggles():
    at = goto(fresh(), "Broker leaderboard")
    assert at.selectbox(key="lb_sample").value == "no_earnings"
    lb = pd.read_csv(TABLES / "broker_leaderboard.csv")
    for s in dict.fromkeys(lb["sample"]):
        for d in ["upgrade", "downgrade"]:
            at.selectbox(key="lb_sample").set_value(s)
            at.radio(key="lb_dir").set_value(d).run()
            assert not at.exception, f"Leaderboard/{s}/{d}: {at.exception}"
    at.checkbox(key="lb_unranked").check().run()
    assert not at.exception


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
        assert not at.exception, f"Explore {combo}: {at.exception}"
    assert at.metric[0].value == "0", at.metric[0].value
    assert any("No rating changes match" in i.value for i in at.info)


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
    sys.path.insert(0, str(ROOT / "dashboard"))
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
