"""The five dashboard pages. Every number on screen is read from a committed file at runtime."""
import re

import numpy as np
import pandas as pd
import streamlit as st

import ui_charts as C
import ui_data as D

WINDOW_NAMES = {"[-20,-2]": "Anticipation", "[-1,+1]": "Reaction", "[+2,+20]": "Drift"}
ANOVA, KW = "one-way ANOVA F", "Kruskal-Wallis H"
EXPLORE_MIN_N = 30   # dashboard display rule: below this many rating changes we do not report a t-stat
TERM_LABELS = {"const": "Constant (downgrade, not near earnings)", "upgrade": "Upgrade",
               "near_earnings": "Near earnings", "upgrade_x_near_earnings": "Upgrade x near earnings"}


# ---------------------------------------------------------------- shared bits
def sample_descriptions(summ):
    ew = summ.get("earnings_window_trading_days", "")
    paths = D.table("car_by_day.csv")
    tmin, tmax = int(paths["t"].min()), int(paths["t"].max())
    return {
        "clean": f"Headline. No earnings report within {ew} trading days of day 0, and no other rating "
                 "change on the same stock within 2 trading days.",
        "all": "Every upgrade and downgrade episode (days with both an upgrade and a downgrade are left out).",
        "no_earnings": f"Episodes with no earnings report within {ew} trading days of day 0.",
        "near_earnings": f"Episodes with an earnings report within {ew} trading days of day 0. "
                         "Much of this move is the earnings news.",
        "clean_window": f"Stricter: no earnings report anywhere in [{tmin},+{tmax}]. Use it to read the long "
                        "windows (anticipation and drift). Fewer episodes.",
        "single_call_days": "Only calls made on a day when no other broker changed its rating on that stock.",
    }


def clock_hours(hhmm):
    """'09:30' -> 9.5 (None if missing)."""
    try:
        h, m = str(hhmm).split(":")
        return int(h) + int(m) / 60
    except ValueError:
        return None


def window_bounds(w):
    """'[-20,-2]' -> (-20, -2)."""
    m = re.match(r"\[\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\]", str(w))
    return (int(m.group(1)), int(m.group(2))) if m else None


def window_label(w):
    return f"CAR{w} {WINDOW_NAMES.get(w, '').lower()}".strip()


def equality_pvalues(eq, sample, direction):
    q = eq[(eq["sample"] == sample) & (eq["direction"] == direction)].set_index("test")
    perm = [t for t in q.index if t.startswith("permutation F")]
    return dict(n_brokers=int(q["n_brokers"].iloc[0]), n_obs=int(q["n_obs"].iloc[0]),
                anova=q.loc[ANOVA, "p_value"], perm=q.loc[perm[0], "p_value"] if perm else np.nan,
                perm_name=perm[0] if perm else "permutation F", kw=q.loc[KW, "p_value"],
                tau=q["tau_pct"].iloc[0])


def mean_test_verdict(p_anova, p_perm):
    """Plain wording for the mean-equality tests."""
    worst = max(p_anova, p_perm)
    best = min(p_anova, p_perm)
    if best > 0.10:
        return "cannot reliably tell the brokers apart"
    if worst < 0.05:
        return "find that average reactions do differ across brokers"
    return "give only weak evidence that average reactions differ across brokers"


def car_path_for(sample, cbd):
    """The CAR path of a sample: from car_by_day.csv, or rebuilt from event_panel.csv if the file lacks it."""
    if sample in set(cbd["sample"]):
        return cbd[cbd["sample"] == sample], "Source: `outputs/tables/car_by_day.csv`."
    path = D.panel_car_paths()
    return path[path["sample"] == sample], (
        "`car_by_day.csv` does not include this sample, so this path is computed here from "
        "`data/processed/event_panel.csv` with the same method. That method reproduces "
        "`car_by_day.csv` exactly for the samples the file does contain.")


def window_table(ws, sample):
    s = ws[ws["sample"] == sample].copy()
    s["window"] = pd.Categorical(s["window"], list(WINDOW_NAMES), ordered=True)
    s = s.sort_values(["direction", "window"], ascending=[False, True])
    s["label"] = [f"CAR{w}<br>{WINDOW_NAMES.get(w, '').lower()}" for w in s["window"]]
    return s


# ---------------------------------------------------------------- 1. Introduction
def page_intro():
    summ = D.summary()
    ws = D.table("window_summary.csv")
    eq = D.table("broker_equality_test.csv")
    cbd = D.table("car_by_day.csv")

    st.title("Do Analyst Upgrades and Downgrades Move Stock Prices?")
    st.markdown("We line up every analyst rating change on its own day 0 and track the stock's return "
                "beyond the market's. We also ask whether some brokers' calls move prices more than others.")

    r = ws[(ws["sample"] == "clean") & (ws["window"] == "[-1,+1]")].set_index("direction")
    up, dn = r.loc["upgrade"], r.loc["downgrade"]
    both_sig = abs(up["t_stat"]) > 1.96 and abs(dn["t_stat"]) > 1.96
    p_up, p_dn = equality_pvalues(eq, "no_earnings", "upgrade"), equality_pvalues(eq, "no_earnings", "downgrade")

    col_chart, col_text = st.columns([3, 2], gap="large")
    with col_chart:
        st.markdown("##### Clean sample: average cumulative abnormal return (CAR) around the rating change")
        C.show(C.car_path(cbd[cbd["sample"] == "clean"], height=440), key="intro_car")
        st.caption("Shaded bands are 95% confidence intervals; the grey strip marks days -1 to +1. "
                   "Source: `outputs/tables/car_by_day.csv`.")
    with col_text:
        st.subheader("The short answer")
        st.markdown(
            f"**CAR[-1,+1]**, clean sample (no earnings report nearby, no other call on the stock at the "
            f"same time):\n\n"
            f"- Upgrades: **{D.pct(up['mean_pct'])}** on average (t = {up['t_stat']:.1f}, "
            f"{int(up['n'])} episodes).\n"
            f"- Downgrades: **{D.pct(dn['mean_pct'])}** on average (t = {dn['t_stat']:.1f}, "
            f"{int(dn['n'])} episodes)."
        )
        st.markdown(
            ("Both averages are clearly different from zero and point the way the call does. "
             if both_sig else "At least one of these averages is not clearly different from zero. ")
            + "These are associations around the rating date, not proof that the analyst caused the move."
        )
        st.markdown(
            f"**Does the broker matter?** On calls with no earnings report nearby, the tests "
            f"{mean_test_verdict(min(p_up['anova'], p_dn['anova']), min(p_up['perm'], p_dn['perm']))} "
            f"(ANOVA {D.p_eq(p_up['anova'])} for upgrades and {D.pval(p_dn['anova'])} for downgrades). "
            "See the Broker leaderboard page."
        )

    c = st.columns(6)
    c[0].metric("Firms", f"{D.num(summ, 'n_firms', int)}", border=True,
                help=f"{D.num(summ, 'n_firms_with_rating_changes', int)} of them have at least one rating "
                     "change in the window.")
    c[1].metric("Rating changes", f"{D.num(summ, 'n_rating_changes', int):,}", border=True,
                help=f"{D.num(summ, 'n_upgrades', int):,} upgrades and {D.num(summ, 'n_downgrades', int):,} "
                     f"downgrades, {summ['sample_start']} to {summ['sample_end']}.")
    c[2].metric("Brokers", f"{D.num(summ, 'n_brokers', int)}", border=True,
                help=f"{D.num(summ, 'n_brokers_ranked', int)} have at least "
                     f"{D.num(summ, 'min_broker_calls', int)} calls in a direction and are ranked.")
    c[3].metric("Upgrade reaction", D.pct(up["mean_pct"]), border=True,
                help=f"Mean CAR[-1,+1], clean sample, 95% CI {D.ci(up['ci_lo_pct'], up['ci_hi_pct'])}.")
    c[4].metric("Downgrade reaction", D.pct(dn["mean_pct"]), border=True,
                help=f"Mean CAR[-1,+1], clean sample, 95% CI {D.ci(dn['ci_lo_pct'], dn['ci_hi_pct'])}.")
    c[5].metric("Near earnings", f"{100 * D.num(summ, 'share_near_earnings'):.0f}%", border=True,
                help="Share of rating changes within "
                     f"{summ.get('earnings_window_trading_days', '')} trading days of an earnings report.")

    ev = D.processed("events.csv")
    years = (ev.assign(year=pd.to_datetime(ev["day0"]).dt.year)
             .groupby(["year", "direction"]).size().rename("n").reset_index())
    col_chart, col_text = st.columns([3, 2], gap="large")
    with col_chart:
        C.show(C.yearly_counts(years), key="intro_years")
    with col_text:
        st.markdown("##### Rating changes per year")
        st.markdown(f"Upgrades and downgrades by the year of day 0. {summ['sample_end'][:4]} is a part year "
                    f"(the sample ends {summ['sample_end']}).")
        st.caption("Source: `data/processed/events.csv`. Use the menu on the left for the method, the full "
                   "results, the broker leaderboard, or to explore the rating changes yourself.")


# ---------------------------------------------------------------- 2. Methodology
def page_method():
    summ = D.summary()
    k = D.constants()
    tod = D.table("rating_time_of_day.csv")
    ws = D.table("window_summary.csv")
    paths = D.table("car_by_day.csv")
    est = D.parse_window(summ.get("market_model", ""), "estimation window")
    evw = D.parse_window(summ.get("market_model", ""), "event window")
    tmin, tmax = int(paths["t"].min()), int(paths["t"].max())
    ew = summ.get("earnings_window_trading_days", "")
    mkt = k.get("MKT", "SPY")
    if est is None:
        st.error("Could not read the estimation window from `outputs/tables/sample_summary.csv` "
                 "(row `market_model`). Run `python run_all.py` to rebuild it.")
        st.stop()
    evw = evw or (tmin, tmax)

    st.title("Methodology")
    st.markdown("An **event study**: line up every rating change on its own day 0, then measure how the stock "
                "did on the days around it after taking out what the market did.")

    windows = [(f"CAR{w}", *window_bounds(w)) for w in ws["window"].unique() if window_bounds(w)]
    col_chart, col_text = st.columns([3, 2], gap="large")
    with col_chart:
        C.show(C.timeline(est, evw, windows), key="me_timeline")
    with col_text:
        st.markdown(
            f"- **Expected return**: a market model, stock return = alpha + beta x {mkt} return, fitted on "
            f"days [{est[0]}, {est[1]}] (at least {k.get('MIN_EST_DAYS', 'n/a')} returns).\n"
            "- **Abnormal return (AR)** = actual return minus expected return.\n"
            f"- **CAR** adds up ARs over a window. Three windows inside [{evw[0]}, +{evw[1]}]: "
            + ", ".join(f"{window_label(w)}" for w in ws["window"].unique())
            + ". The headline is CAR[-1,+1]."
        )
        st.caption("Boundaries from `outputs/tables/sample_summary.csv` (row `market_model`) and "
                   "`outputs/tables/window_summary.csv`.")

    tab_time, tab_funnel, tab_cov, tab_def = st.tabs(
        ["Day 0 and timing", "Sample funnel", "Yahoo coverage", "Episodes and samples"])

    with tab_time:
        col_chart, col_text = st.columns([3, 2], gap="large")
        with col_chart:
            C.show(C.hour_bars(tod, open_h=clock_hours(k.get("MARKET_OPEN")),
                               close_h=clock_hours(k.get("MARKET_CLOSE"))), key="me_hours")
        with col_text:
            st.markdown(
                f"**Day 0** is the first trading day an investor could act on the call. Before the "
                f"{k.get('MARKET_OPEN', '')} open or during market hours: that day. At or after the "
                f"{k.get('MARKET_CLOSE', '')} close, or on a weekend or holiday: the next trading day."
            )
            st.markdown(
                f"{100 * D.num(summ, 'share_before_open'):.0f}% of calls are stamped before the open, "
                f"{100 * D.num(summ, 'share_during_market'):.0f}% during market hours and "
                f"{100 * D.num(summ, 'share_after_close'):.0f}% after the close."
            )
            st.caption("Timestamps are Yahoo's record and could not be checked against the brokers' own "
                       "release times. Source: `outputs/tables/rating_time_of_day.csv`.")

    with tab_funnel:
        n_up_ep, n_dn_ep = D.num(summ, "n_episodes_upgrade", int), D.num(summ, "n_episodes_downgrade", int)
        clean_n = ws[(ws["sample"] == "clean") & (ws["window"] == "[-1,+1]")].set_index("direction")["n"]
        members = D.num(summ, "n_sp500_members_2020", int)
        dropped = (D.num(summ, "n_members_no_yahoo_prices", int) + D.num(summ, "n_members_short_2020_history", int)
                   + D.num(summ, "n_extra_share_classes", int))
        firm_steps = [
            (f"S&P 500 members on {k.get('UNIVERSE_ASOF', '')}", members),
            ("Priced today, full history, one share class", members - dropped),
            (f"Top by {k.get('RANK_YEAR', '')} dollar volume", D.num(summ, "n_firms", int)),
            ("With at least one rating change", D.num(summ, "n_firms_with_rating_changes", int)),
        ]
        event_steps = [
            ("Rating changes", D.num(summ, "n_rating_changes", int)),
            ("Episodes (stock x day 0)", D.num(summ, "n_episodes", int)),
            ("Upgrade or downgrade episodes (mixed left out)", n_up_ep + n_dn_ep),
            ("Clean episodes (headline)", int(clean_n.sum())),
        ]
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("##### Firms")
            C.show(C.funnel(firm_steps), key="me_funnel_firms")
        with c2:
            st.markdown("##### Rating changes")
            C.show(C.funnel(event_steps, color=C.COLOR["upgrade"]), key="me_funnel_events")
        st.caption("Several brokers changing their rating on the same stock on the same day share one price move, "
                   "so they form one episode. Source: `outputs/tables/sample_summary.csv` and "
                   f"`window_summary.csv`. The second firm step is {members} members minus the {dropped} "
                   "dropped in the table below (no prices, short history, extra share classes).")
        with st.expander("Funnel as a table"):
            funnel = pd.DataFrame([
                ("S&P 500 members on " + str(k.get("UNIVERSE_ASOF", "")), members),
                ("Members with no Yahoo prices today (dropped)", D.num(summ, "n_members_no_yahoo_prices", int)),
                (f"Members with a short {k.get('RANK_YEAR', '')} price history (dropped)",
                 D.num(summ, "n_members_short_2020_history", int)),
                ("Extra share classes (dropped)", D.num(summ, "n_extra_share_classes", int)),
                ("Firms chosen: top by average daily dollar volume", D.num(summ, "n_firms", int)),
                ("Firms with at least one rating change", D.num(summ, "n_firms_with_rating_changes", int)),
                ("Rating changes (upgrades and downgrades)", D.num(summ, "n_rating_changes", int)),
                ("Episodes (stock x day 0)", D.num(summ, "n_episodes", int)),
                ("Mixed episodes left out", D.num(summ, "n_episodes_mixed_excluded", int)),
                ("Upgrade + downgrade episodes", n_up_ep + n_dn_ep),
                ("Clean episodes (headline)", int(clean_n.sum())),
            ], columns=["Step", "Count"])
            st.dataframe(funnel, hide_index=True, width="stretch")

    with tab_cov:
        cov = D.table("ratings_coverage_by_year.csv")
        uni = D.load("data/raw/universe.csv")
        start_year = int(str(summ["sample_start"])[:4])
        what = st.radio("Count", ["raw_rows", "rating_changes_kept"], horizontal=True, key="me_cov",
                        format_func={"raw_rows": "All Yahoo rows (any action, every year)",
                                     "rating_changes_kept": "Rating changes kept (sample years)"}.get)
        sub = cov if what == "raw_rows" else cov[cov["year"] >= start_year]
        pivot = sub.pivot(index="ticker", columns="year", values=what).fillna(0).astype(int)
        order = [t for t in uni.sort_values("rank")["ticker"] if t in pivot.index]
        pivot = pivot.loc[order + [t for t in pivot.index if t not in order]]
        C.show(C.coverage_heatmap(pivot, "rows" if what == "raw_rows" else "changes",
                                  start_year if what == "raw_rows" else None), key="me_coverage")
        st.caption("One row per firm (ordered by dollar-volume rank), one column per year. White cells are "
                   "years with nothing in Yahoo's list. Some firms have holes inside the sample (for example "
                   "META, C, GE, BRK-B). Source: `outputs/tables/ratings_coverage_by_year.csv`.")

    with tab_def:
        st.markdown(
            "- **Episode.** Calls by several brokers on the same stock and day 0 count as one episode. Days with "
            "both an upgrade and a downgrade (mixed) are left out.\n"
            f"- **Near earnings.** Day 0 within {ew} trading days of the firm's earnings day 0. The window leans "
            "forward because analysts often re-rate right after a report.\n"
            "- **Clean (headline).** Not near earnings, no other rating change on the same stock within 2 "
            "trading days, and not a mixed day.\n"
            f"- **Clean window.** Stricter: no earnings report anywhere in [{tmin},+{tmax}]; used only to read "
            "the long windows."
        )

    with st.expander("More detail on the method"):
        st.markdown(
            "- Rating changes come from Yahoo Finance (`yfinance`), filtered to explicit upgrades and "
            "downgrades. Initiations, reiterations and price-target changes are left out. Yahoo reports the "
            "brokerage firm, not the analyst. Broker name variants are merged with "
            "`data/raw/broker_aliases.csv`.\n"
            "- Firms are chosen with information available at the start: the S&P 500 members on the "
            f"as-of date, ranked by average daily dollar volume in {k.get('RANK_YEAR', '')}.\n"
            "- Means are reported with a t-statistic (mean divided by its standard error) and a 95% "
            "confidence interval (mean plus or minus 1.96 standard errors).\n"
            "- The broker leaderboard uses one row per rating change, not per episode, because the question "
            "is about each broker's calls.\n"
            "- All data were pulled once and committed, so the numbers can be reproduced with "
            f"`python run_all.py`. Pull date: {summ.get('data_pull_date', 'n/a')}."
        )

    with st.expander("The firms in the sample"):
        uni = D.load("data/raw/universe.csv")
        ev = D.processed("events.csv")
        counts = ev.groupby("ticker").size()
        firms = pd.DataFrame({
            "Rank": uni["rank"], "Ticker": uni["ticker"], "Company": uni["name"], "Sector": uni["sector"],
            "Rating changes": uni["ticker"].map(counts).fillna(0).astype(int)})
        st.dataframe(firms, hide_index=True, width="stretch")
        st.caption("Rank = position by average daily dollar trading volume in the ranking year. "
                   "Source: `data/raw/universe.csv` and `data/processed/events.csv`.")

    with st.expander("Limits of this study"):
        threats(summ)


def threats(summ):
    paths = D.table("car_by_day.csv")
    n_days = int(paths["t"].max()) - int(paths["t"].min()) + 1
    eq = D.table("broker_equality_test.csv")
    st.markdown(
        "- **Yahoo coverage gaps.** Yahoo's rating history has holes for some firms (META, C, GE, BRK-B), "
        "some of them inside the sample period. Yahoo's list is not a complete record of every call.\n"
        f"- **Earnings and other news.** {100 * D.num(summ, 'share_near_earnings'):.0f}% of rating changes "
        "come right around an earnings report. The clean sample leaves those out, but other news (guidance, "
        "mergers, market-wide days) is not filtered, and a broker may be reacting to news that already moved "
        "the price.\n"
        f"- **Earnings inside the long windows.** {100 * D.num(summ, 'share_episodes_earnings_in_window'):.0f}% "
        f"of episodes have an earnings report somewhere in the {n_days}-day event window, so the anticipation and "
        "drift windows can carry earnings news. The clean-window sample is the fair check for them.\n"
        "- **Daily data.** Daily returns cannot see the reaction within the day, and cannot separate the "
        "call from other news on the same day. Timestamps are the vendor's, not verified release times.\n"
        f"- **Survivorship.** The firm list uses membership at the start, but "
        f"{D.num(summ, 'n_members_no_yahoo_prices', int)} members could not be priced today (acquired or "
        "delisted), and all chosen firms still trade.\n"
        f"- **Shared and correlated events.** {D.num(summ, 'n_episodes_multi_broker', int)} episodes have "
        "several brokers on the same day; on the leaderboard those calls share one CAR. Calls on the same "
        "stock or day are not independent, so broker intervals are somewhat too narrow.\n"
        f"- **Many brokers, few calls each.** With {eq['n_brokers'].min()} to {eq['n_brokers'].max()} ranked "
        "brokers per list, some will look extreme by chance, which is why we report joint tests.\n"
        f"- **One period, large firms.** {summ['sample_start'][:4]} to {summ['sample_end'][:4]} and large, heavily followed U.S. stocks only. "
        "A single-factor market model; multi-factor models were not tried."
    )


# ---------------------------------------------------------------- 3. Results
def page_results():
    summ = D.summary()
    ws = D.table("window_summary.csv")
    cbd = D.table("car_by_day.csv")
    desc = sample_descriptions(summ)
    samples = [s for s in ["clean", "all", "no_earnings", "near_earnings", "clean_window"]
               if s in set(ws["sample"])]

    st.title("Results")
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        sample = st.selectbox("Sample", samples, index=0, key="res_sample",
                              format_func=lambda s: D.SAMPLE_LABELS.get(s, s))
    with c2:
        st.caption("Unit = one **episode** (one stock on one day 0). Market-model abnormal returns in percent. "
                   + desc.get(sample, ""))

    path, note = car_path_for(sample, cbd)
    tmax = int(path["t"].max())
    col_car, col_ar = st.columns([3, 2], gap="large")
    with col_car:
        st.markdown("##### Average CAR around the rating change")
        C.show(C.car_path(path), key="res_car")
        st.caption("Lines add up the average abnormal return from the first day shown; bands are 95% "
                   "confidence intervals; the grey strip marks days -1 to +1. " + note)
    with col_ar:
        st.markdown("##### Average abnormal return on each day")
        half = st.slider("Days either side of day 0", 1, tmax, min(5, tmax), key="res_ar_days")
        ar = C.daily_ar_from_path(path)
        if ar is None:
            st.info("The number of episodes changes from day to day in this sample, so daily averages cannot "
                    "be read off the CAR path.")
        else:
            C.show(C.ar_bars(ar[ar["t"].between(-half, half)]), key="res_ar")
            st.caption("Daily AR = change in the average CAR from one day to the next (the same episodes are "
                       "in every day, so this is the average AR that day). Most of the move is on days -1 and 0.")

    col_chart, col_table = st.columns([3, 2], gap="large")
    s = window_table(ws, sample)
    with col_chart:
        st.markdown("##### The three CAR windows")
        C.show(C.ci_bars(s, "label", ytitle="Mean CAR over the window (%)"), key="res_windows")
    with col_table:
        st.markdown("##### Event study summary")
        st.table(pd.DataFrame({
            "": s["direction"].str.capitalize(),
            "CAR window": [f"{w} {WINDOW_NAMES.get(w, '').lower()}" for w in s["window"]],
            "n": s["n"].astype(int).astype(str),
            "Mean": s["mean_pct"].map(D.pct),
            "t": s["t_stat"].map(lambda x: f"{x:.1f}"),
            "95% CI (%)": [f"{lo:+.2f} to {hi:+.2f}" for lo, hi in zip(s["ci_lo_pct"], s["ci_hi_pct"])],
        }), hide_index=True)
        st.caption("Error bars and CIs are mean plus or minus 1.96 standard errors. A |t| above about 2 means "
                   "the average is unlikely to be zero by chance. Source: `outputs/tables/window_summary.csv`. "
                   "These are associations around the rating date, not proof that the call caused the move.")

    st.divider()
    st.subheader("Do earnings reports change the picture?")
    ec = D.table("earnings_comparison.csv")
    reg = D.table("earnings_regression.csv")
    ew = summ.get("earnings_window_trading_days", "")
    st.caption(f"An episode overlaps earnings when the firm's earnings day 0 is within {ew} trading days of the "
               "rating change's day 0. These charts do not change with the sample selector.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("##### Mean CAR[-1,+1] with and without earnings nearby")
        C.show(C.ci_bars(ec, "earnings"), key="res_earn_bars")
        st.caption("Source: `outputs/tables/earnings_comparison.csv`.")
    with c2:
        st.markdown("##### CAR paths: near earnings (dashed) vs no earnings (solid)")
        if {"near_earnings", "no_earnings"} <= set(cbd["sample"]):
            C.show(C.car_paths_compare([("no earnings", "solid", cbd[cbd["sample"] == "no_earnings"]),
                                        ("near earnings", "dash", cbd[cbd["sample"] == "near_earnings"])]),
                   key="res_earn_paths")
            st.caption("Bands (95% CI) shown for the no-earnings lines. Source: `outputs/tables/car_by_day.csv`.")
        else:
            st.info("`car_by_day.csv` has no near_earnings / no_earnings rows.")

    models = list(dict.fromkeys(reg["model"]))
    c1, c2 = st.columns([3, 2], gap="large")
    with c2:
        model = st.radio("Regression", models, key="res_reg", index=next(
            (i for i, m in enumerate(models) if m.startswith("signed")), 0),
            format_func=lambda m: "Signed CAR (direction of the call)" if m.startswith("signed") else "Raw CAR")
        st.markdown(earnings_regression_text(reg))
    with c1:
        st.markdown("##### One regression with both effects: coefficients and 95% intervals")
        r = reg[reg["model"] == model]
        coefs = pd.DataFrame({"label": r["term"].map(lambda t: TERM_LABELS.get(t, t)), "coef": r["coef"],
                              "lo": r["coef"] - 1.96 * r["se"], "hi": r["coef"] + 1.96 * r["se"],
                              "p_value": r["p_value"]})
        C.show(C.coef_plot(coefs), key="res_coef")
        st.caption("Intervals are coefficient plus or minus 1.96 clustered standard errors. Source: "
                   "`outputs/tables/earnings_regression.csv`.")
    with st.expander("Earnings comparison as a table"):
        st.dataframe(pd.DataFrame({
            "Direction": ec["direction"].str.capitalize(), "Earnings": ec["earnings"], "n": ec["n"].astype(int),
            "Mean CAR[-1,+1]": ec["mean_pct"].map(D.pct), "t": ec["t_stat"].round(1),
            "95% CI": [D.ci(lo, hi) for lo, hi in zip(ec["ci_lo_pct"], ec["ci_hi_pct"])]}),
            hide_index=True, width="stretch")

    st.divider()
    st.subheader("Robustness: CAR[-1,+1] under other choices")
    rb = D.table("robustness.csv")
    rbc = rb.assign(ci_lo_pct=rb["mean_pct"] - 1.96 * rb["se_pct"], ci_hi_pct=rb["mean_pct"] + 1.96 * rb["se_pct"])
    C.show(C.forest(rbc), key="res_forest")
    st.caption("Each row changes one choice (benchmark, day-0 rule, sample, unit, or how standard errors are "
               "computed). Dots are means, lines are 95% intervals (mean plus or minus 1.96 SE). "
               "Source: `outputs/tables/robustness.csv`.")
    with st.expander("Robustness as a table"):
        st.dataframe(pd.DataFrame({
            "Specification": rb["spec"], "Direction": rb["direction"].str.capitalize(),
            "n": rb["n"].astype(int), "Mean CAR[-1,+1]": rb["mean_pct"].map(D.pct),
            "SE": rb["se_pct"].map(lambda x: f"{x:.2f}"), "t": rb["t_stat"].round(1)}),
            hide_index=True, width="stretch")


def earnings_regression_text(reg):
    sig = reg[reg["model"].str.startswith("signed")].set_index("term")
    if sig.empty or not {"const", "upgrade", "near_earnings", "upgrade_x_near_earnings"} <= set(sig.index):
        return "The signed regression rows are missing from `earnings_regression.csv`."
    b0, b1, b2, b3 = (sig.loc[t] for t in ["const", "upgrade", "near_earnings", "upgrade_x_near_earnings"])
    bigger = "bigger" if b3["coef"] > 0 else "smaller"
    amplify = ("Earnings make downgrade reactions larger than upgrade reactions."
               if b3["coef"] < 0 and b3["p_value"] < 0.05 else
               "Earnings make upgrade reactions larger than downgrade reactions."
               if b3["coef"] > 0 and b3["p_value"] < 0.05 else
               "We cannot say that earnings affect upgrades and downgrades differently.")
    return (
        f"**Signed model** ({int(b0['n']):,} episodes, standard errors clustered by stock, "
        f"{int(b0['n_clusters'])} stocks). Reactions are measured in the direction of the call. A downgrade not "
        f"near earnings moves the price {b0['coef']:.2f}% that way; an upgrade moves it "
        f"{abs(b1['coef']):.2f} points {'more' if b1['coef'] > 0 else 'less'} ({D.p_eq(b1['p_value'])}). Near "
        f"earnings adds {b2['coef']:.2f} points for downgrades ({D.p_eq(b2['p_value'])}), and that boost is "
        f"{abs(b3['coef']):.2f} points {bigger} for upgrades ({D.p_eq(b3['p_value'])}). {amplify}"
    )


# ---------------------------------------------------------------- 4. Broker leaderboard
def page_brokers():
    summ = D.summary()
    lb = D.table("broker_leaderboard.csv")
    eq = D.table("broker_equality_test.csv")
    desc = sample_descriptions(summ)
    min_calls = D.num(summ, "min_broker_calls", int)

    st.title("Broker leaderboard")
    st.markdown("Does it matter which broker makes the call? Here each **rating change** counts once "
                "(not each episode), and we compare brokers' average CAR[-1,+1].")

    c1, c2 = st.columns([1, 2])
    with c1:
        direction = st.radio("Direction", ["upgrade", "downgrade"], key="lb_dir", horizontal=True,
                             format_func=lambda d: C.LABEL[d])
    with c2:
        avail = list(dict.fromkeys(lb["sample"]))
        order = ["no_earnings"] + [s for s in avail if s != "no_earnings"]
        order = [s for s in order if s in avail]
        sample = st.selectbox("Sample", order, index=0, key="lb_sample",
                              format_func=lambda s: D.SAMPLE_LABELS.get(s, s)
                              + (" (headline)" if s == "no_earnings" else ""))
    st.caption(desc.get(sample, "") + (" This is the headline leaderboard: on all calls, brokers that often "
                                       "re-rate right after earnings get credit for the earnings move."
                                       if sample == "no_earnings" else ""))

    p = equality_pvalues(eq, sample, direction)
    verdict = mean_test_verdict(p["anova"], p["perm"])
    box = st.warning if min(p["anova"], p["perm"]) > 0.10 else st.info
    box(
        f"**Read this first.** The tests {verdict}. For {direction}s in this sample, a test of whether "
        f"all {p['n_brokers']} ranked brokers have the same average gives ANOVA {D.p_eq(p['anova'])} and "
        f"permutation {D.p_eq(p['perm'])}. "
        + ("So this is **not** a list of the best brokers: the tests cannot separate the order below from "
           "chance, and the intervals overlap heavily."
           if min(p["anova"], p["perm"]) > 0.10 else
           "Even so, this is **not** a list of the best brokers: single brokers' averages are noisy and "
           "many intervals overlap.")
    )

    sub = lb[(lb["sample"] == sample) & (lb["direction"] == direction)]
    ranked = sub[sub["meets_min_n"]].sort_values("rank")
    ref = (sub["n"] * sub["mean_pct"]).sum() / sub["n"].sum()   # call-weighted = mean over all calls
    se10 = D.num(summ, "se_of_broker_mean_at_n10_pp")

    tab_rank, tab_noise, tab_std = st.tabs(["Ranking", "Noise shrinks with more calls", "Raw vs scaled order"])
    with tab_rank:
        if ranked.empty:
            st.info("No broker meets the minimum number of calls in this sample and direction.")
        else:
            C.show(C.broker_dots(ranked, direction, ref_mean=ref), key="lb_dots")
        col_rule, col_text = st.columns(2, gap="large")
        with col_rule:
            st.markdown(
                f"**Minimum calls rule.** Only brokers with at least {min_calls} calls in a direction are ranked. "
                "Because small averages are noisy, the order uses a **shrunk mean** (diamonds) that pulls each "
                "broker toward the overall average; the less data a broker has, the more it is pulled."
            )
            if not ranked.empty:
                st.markdown(
                    f"{int(((ranked['ci_lo_pct'] <= ref) & (ranked['ci_hi_pct'] >= ref)).sum())} of {len(ranked)} "
                    "intervals include the dashed line (the average over all calls in this sample).")
        with col_text:
            st.markdown(
                f"A third test, Kruskal-Wallis, compares whole distributions (ranks), not averages. Here it gives "
                f"{D.p_eq(p['kw'])}. It can reject even when averages are equal, because returns have fat tails "
                "and brokers differ in spread (some cover volatile stocks, some call right after earnings). "
                f"The estimated spread of brokers' true averages (tau) is {p['tau']:.2f} percentage points, "
                f"{'small next to' if p['tau'] < se10 else 'compared with'} the noise in one broker's average at "
                f"n = 10 ({se10:.2f} points of standard error)."
            )
            st.caption("Dots: each broker's average CAR[-1,+1] with a 95% confidence interval. "
                       "Source: `outputs/tables/broker_leaderboard.csv`.")
    with tab_noise:
        col_chart, col_text = st.columns([3, 2], gap="large")
        with col_chart:
            C.show(C.broker_noise(sub, direction, min_calls, ref_mean=ref, sd_pct=se10 * np.sqrt(10)),
                   key="lb_noise")
        with col_text:
            st.markdown(
                "Each dot is one broker in this sample and direction, including those with too few calls to be "
                "ranked (grey). The most extreme averages come from brokers with only a few calls. With more "
                "calls, averages pull in toward the overall average (dashed line)."
            )
            st.caption(f"Dotted lines: the overall average plus or minus 1.96 x {se10 * np.sqrt(10):.2f} / "
                       "sqrt(calls), where "
                       f"{se10 * np.sqrt(10):.2f}% is the standard deviation of CAR[-1,+1] over all calls "
                       "(from `se_of_broker_mean_at_n10_pp` in `sample_summary.csv`, times sqrt(10)). A rough "
                       "guide to how far a broker's average can stray by chance.")
    with tab_std:
        sd = D.table("broker_leaderboard_standardized.csv")
        s_std = sd[(sd["sample"] == sample) & (sd["direction"] == direction) & sd["meets_min_n"]]
        both = ranked[["broker", "n", "rank"]].merge(s_std[["broker", "rank"]], on="broker",
                                                      suffixes=("_raw", "_std"))
        col_chart, col_text = st.columns([3, 2], gap="large")
        with col_chart:
            if both.empty:
                st.info("No ranked brokers to compare in this sample and direction.")
            else:
                C.show(C.rank_scatter(both, direction), key="lb_ranks")
        with col_text:
            st.markdown("Each CAR is divided by the stock's usual 3-day noise, so volatile stocks do not dominate. "
                        "Dots on the dotted line keep the same place in both orders.")
            rs = D.table("broker_rank_stability.csv")
            r = rs[(rs["sample"] == sample) & (rs["direction"] == direction)]
            if not r.empty:
                st.markdown(f"Rank correlation (Spearman) between the two orders: **{r['spearman_rho'].iloc[0]:.2f}**. "
                            f"Same broker first: {'yes' if bool(r['same_rank_1'].iloc[0]) else 'no'}.")
            st.caption("Source: `outputs/tables/broker_leaderboard.csv`, "
                       "`broker_leaderboard_standardized.csv` and `broker_rank_stability.csv`.")

    show_all = st.checkbox(f"Also list brokers with fewer than {min_calls} calls (not ranked)", key="lb_unranked")
    tbl = pd.concat([ranked, sub[~sub["meets_min_n"]].sort_values("n", ascending=False)]) if show_all else ranked
    st.dataframe(pd.DataFrame({
        "Order": tbl["rank"].astype("Int64"),
        "Broker": tbl["broker"], "Calls": tbl["n"].astype(int),
        "Mean CAR[-1,+1]": tbl["mean_pct"].map(D.pct),
        "95% CI": [D.ci(lo, hi) if not pd.isna(lo) else "n/a" for lo, hi in zip(tbl["ci_lo_pct"], tbl["ci_hi_pct"])],
        "Shrunk mean": tbl["shrunk_mean_pct"].map(D.pct),
        "Share near earnings": tbl["share_near_earnings_pct"].map(lambda x: f"{x:.0f}%"),
    }), hide_index=True, width="stretch")

    with st.expander("All equality tests"):
        st.dataframe(pd.DataFrame({
            "Sample": eq["sample"], "Direction": eq["direction"], "Test": eq["test"],
            "Brokers": eq["n_brokers"], "Calls": eq["n_obs"], "Statistic": eq["statistic"].round(2),
            "p-value": eq["p_value"].map(D.pval), "tau (pp)": eq["tau_pct"].round(2)}),
            hide_index=True, width="stretch")
        st.caption("Each test asks whether all ranked brokers have the same CAR[-1,+1]. "
                   "Source: `outputs/tables/broker_equality_test.csv`.")
    with st.expander("Scaled-CAR order as a table"):
        s = s_std.sort_values("rank")
        st.markdown("The value is in units of the stock's 3-day noise, not percent.")
        st.dataframe(pd.DataFrame({
            "Order": s["rank"].astype(int), "Broker": s["broker"], "Calls": s["n"].astype(int),
            "Mean scaled CAR": s["mean_scar"].round(2), "t": s["t_stat"].round(1)}),
            hide_index=True, width="stretch")
        st.caption("Source: `outputs/tables/broker_leaderboard_standardized.csv`.")
    with st.expander("How stable is the order? (all samples)"):
        rs = D.table("broker_rank_stability.csv")
        st.dataframe(pd.DataFrame({
            "Sample": rs["sample"], "Direction": rs["direction"], "Brokers": rs["n_brokers"],
            "Rank correlation (raw vs scaled)": rs["spearman_rho"].round(2),
            "Same broker first?": rs["same_rank_1"].map({True: "yes", False: "no"})}),
            hide_index=True, width="stretch")
        st.caption("Spearman correlation between the raw and the scaled order. "
                   "Source: `outputs/tables/broker_rank_stability.csv`.")
    with st.expander("Limits of this study"):
        threats(summ)


# ---------------------------------------------------------------- 5. Explore
def event_label(r):
    return (f"{r.day0.date()}  {r.ticker}  {r.broker}: {r.from_grade} to {r.to_grade} "
            f"({r.direction}, CAR[-1,+1] {100 * r.car_m1_p1:+.2f}%)")


def page_explore():
    summ = D.summary()
    ev = D.processed("events.csv")
    ev["day0"] = pd.to_datetime(ev["day0"])
    ev["year"] = ev["day0"].dt.year
    min_group = D.num(summ, "min_broker_calls", int)

    st.title("Explore the rating changes")
    st.caption(
        "Numbers here are **per rating change** (`data/processed/events.csv`), not per episode, so they can "
        "differ from the headline: calls on a day when several brokers moved the same stock share one CAR and "
        "count more than once, and the clean-sample rules are not applied (the earnings filter covers part of them)."
    )

    with st.container(border=True):
        c1, c2 = st.columns(2)
        firms = c1.multiselect("Company (empty = all)", sorted(ev["ticker"].unique()), key="ex_firms")
        brokers = c2.multiselect("Broker (empty = all)", sorted(ev["broker"].unique()), key="ex_brokers")
        c1, c2, c3 = st.columns(3)
        direction = c1.radio("Direction", ["both", "upgrade", "downgrade"], horizontal=True, key="ex_dir",
                             format_func=lambda d: "Both" if d == "both" else C.LABEL[d])
        earn = c2.selectbox("Earnings overlap", ["all", "no", "yes"], key="ex_earn",
                            format_func={"all": "All rating changes", "no": "Not near earnings",
                                         "yes": "Near earnings"}.get)
        y0, y1 = int(ev["year"].min()), int(ev["year"].max())
        years = c3.slider("Year of day 0", y0, y1, (y0, y1), key="ex_years") if y1 > y0 else (y0, y1)

    f = ev
    if firms:
        f = f[f["ticker"].isin(firms)]
    if brokers:
        f = f[f["broker"].isin(brokers)]
    if direction != "both":
        f = f[f["direction"] == direction]
    if earn != "all":
        f = f[f["near_earnings"] == (earn == "yes")]
    f = f[f["year"].between(years[0], years[1])]

    dirs = [d for d in ["upgrade", "downgrade"] if (f["direction"] == d).any()]
    cols = st.columns(1 + max(len(dirs), 1))
    cols[0].metric("Matching rating changes", f"{len(f):,}", border=True)
    if f.empty:
        st.info("No rating changes match these filters. Try removing a company or broker, or widening the years.")
        return
    for col, d in zip(cols[1:], dirs):
        r = D.mean_stats(f.loc[f["direction"] == d, "car_m1_p1"])
        with col:
            col.metric(f"{C.LABEL[d]}: mean CAR[-1,+1]", D.pct(r["mean_pct"]), border=True)
            if r["n"] >= EXPLORE_MIN_N:
                st.caption(f"n = {r['n']}, t = {r['t_stat']:.1f}, 95% CI {D.ci(r['ci_lo_pct'], r['ci_hi_pct'])}")
            else:
                st.caption(f"n = {r['n']}. Too few to say: with fewer than {EXPLORE_MIN_N} rating changes we "
                           "do not report a t-stat or interval; the average can swing a lot with one call.")

    plot = f.assign(car_pct=100 * f["car_m1_p1"])
    t_dist, t_time, t_firm, t_broker, t_one = st.tabs(
        ["Distribution", "Over time", "By company", "By broker", "Single event"])
    with t_dist:
        C.show(C.histogram(plot), key="ex_hist")
        st.caption("Upgrades and downgrades are shown separately because averaging them together would cancel out.")
    with t_time:
        C.show(C.event_scatter(plot), key="ex_scatter")
        st.caption("Each dot is one rating change. Hover for the ticker, broker and grades.")
    for tab, by, title, key in [(t_firm, "ticker", "Company", "ex_by_firm"),
                                (t_broker, "broker", "Broker", "ex_by_broker")]:
        with tab:
            g = D.group_means(f, by, min_group)
            if g.empty:
                st.info(f"No {title.lower()} has {min_group} or more matching calls in one direction.")
            else:
                C.show(C.group_bars(g, title), key=key)
            st.caption(f"Mean CAR[-1,+1] per {title.lower()} and direction, only where there are at least "
                       f"{min_group} matching calls (the leaderboard's minimum, from `sample_summary.csv`). "
                       "Hover for n.")
    with t_one:
        pick = f.sort_values(["day0", "event_id"], ascending=[False, True])
        labels = {r.event_id: event_label(r) for r in pick.itertuples()}
        eid = st.selectbox("Rating change (from the current filter, newest first)", list(labels), key="ex_event",
                           format_func=labels.get)
        row = pick[pick["event_id"] == eid].iloc[0]
        pan = D.event_panel()
        one = pan[pan["event_id"] == eid]
        if one.empty:
            st.info("This rating change has no rows in `data/processed/event_panel.csv`.")
        else:
            st.markdown(f"##### {row['ticker']}, {row['broker']}, day 0 {row['day0'].date()}")
            C.show(C.single_event(one, row["direction"]), key="ex_single")
            st.caption("Grey bars: the stock's abnormal return each day. Line: those added up from the first "
                       f"day shown. CAR[-1,+1] for this call is {100 * row['car_m1_p1']:+.2f}%. "
                       "Source: `data/processed/event_panel.csv`.")

    show = pd.DataFrame({
        "Day 0": f["day0"].dt.date, "Ticker": f["ticker"], "Broker": f["broker"],
        "Direction": f["direction"], "From": f["from_grade"], "To": f["to_grade"],
        "Timing": f["timing"], "Near earnings": f["near_earnings"],
        "Brokers that day": f["n_same_day_calls"],
        "CAR[-1,+1] (%)": (100 * f["car_m1_p1"]).round(2),
        "CAR[-20,-2] (%)": (100 * f["car_m20_m2"]).round(2),
        "CAR[+2,+20] (%)": (100 * f["car_p2_p20"]).round(2),
    }).sort_values("Day 0", ascending=False)
    with st.expander("The matching rating changes as a table", expanded=False):
        st.dataframe(show, hide_index=True, width="stretch", height=380)
        st.download_button("Download these rows (CSV)", show.to_csv(index=False).encode("utf-8"),
                           file_name="rating_changes_filtered.csv", mime="text/csv", key="ex_download")
        st.caption("Click a column header to sort. CAR columns are in percent.")
