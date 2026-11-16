"""The five dashboard pages. Every number on screen is read from a committed file at runtime."""
import numpy as np
import pandas as pd
import streamlit as st

import ui_charts as C
import ui_data as D

WINDOW_NAMES = {"[-20,-2]": "Anticipation", "[-1,+1]": "Reaction", "[+2,+20]": "Drift"}
ANOVA, KW = "one-way ANOVA F", "Kruskal-Wallis H"
EXPLORE_MIN_N = 30   # dashboard display rule: below this many rating changes we do not report a t-stat


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


# ---------------------------------------------------------------- 1. Introduction
def page_intro():
    summ = D.summary()
    ws = D.table("window_summary.csv")
    eq = D.table("broker_equality_test.csv")

    st.title("Analyst Rating Changes: Do Upgrades Move Stock Prices?")
    st.markdown("#### Do analyst upgrades and downgrades move stock prices, and does the broker matter?")
    st.markdown(
        "Brokerage firms publish rating changes on stocks every day, for example moving a stock from "
        "Hold to Buy. Investors and the media treat these calls as news. This project checks two things. "
        "First, does the stock price move when a rating changes, beyond what the overall market did? "
        "Second, do some brokers' calls move prices more than others?"
    )
    st.markdown(
        "This matters because if calls carry new information, prices should react on the day they come "
        "out. If prices only react to news that was already public, such as an earnings report, the calls "
        "add little."
    )

    st.subheader("The sample")
    c = st.columns(3)
    c[0].metric("Firms", f"{D.num(summ, 'n_firms', int)}", border=True,
                help=f"{D.num(summ, 'n_firms_with_rating_changes', int)} of them have at least one rating change in the window.")
    c[1].metric("Rating changes", f"{D.num(summ, 'n_rating_changes', int):,}", border=True)
    c[2].metric("Brokers", f"{D.num(summ, 'n_brokers', int)}", border=True)
    c = st.columns(3)
    c[0].metric("Upgrades", f"{D.num(summ, 'n_upgrades', int):,}", border=True)
    c[1].metric("Downgrades", f"{D.num(summ, 'n_downgrades', int):,}", border=True)
    c[2].metric("Years covered", f"{summ['sample_start'][:4]} to {summ['sample_end'][:4]}", border=True,
                help=f"From {summ['sample_start']} to {summ['sample_end']}. Day 0 runs from "
                     f"{summ['first_day0']} to {summ['last_day0']}.")

    st.subheader("The short answer")
    r = ws[(ws["sample"] == "clean") & (ws["window"] == "[-1,+1]")].set_index("direction")
    up, dn = r.loc["upgrade"], r.loc["downgrade"]
    both_sig = abs(up["t_stat"]) > 1.96 and abs(dn["t_stat"]) > 1.96
    st.markdown(
        f"**Clean sample, CAR[-1,+1]** (the abnormal return from the day before to the day after the "
        f"rating change, in rating-change episodes with no earnings report nearby and no other call on the "
        f"stock at the same time):\n\n"
        f"- Upgrades: **{D.pct(up['mean_pct'])}** on average (t = {up['t_stat']:.1f}, "
        f"{int(up['n'])} episodes).\n"
        f"- Downgrades: **{D.pct(dn['mean_pct'])}** on average (t = {dn['t_stat']:.1f}, "
        f"{int(dn['n'])} episodes)."
    )
    st.markdown(
        ("Both averages are clearly different from zero, and they point the way the call does. "
         if both_sig else "At least one of these averages is not clearly different from zero. ")
        + "These are associations around the rating date, not proof that the analyst caused the move."
    )
    p_up, p_dn = equality_pvalues(eq, "no_earnings", "upgrade"), equality_pvalues(eq, "no_earnings", "downgrade")
    st.markdown(
        f"**Does the broker matter?** On calls with no earnings report nearby, the statistical tests "
        f"{mean_test_verdict(min(p_up['anova'], p_dn['anova']), min(p_up['perm'], p_dn['perm']))} "
        f"(ANOVA {D.p_eq(p_up['anova'])} for upgrades and {D.pval(p_dn['anova'])} for downgrades). "
        "See the Broker leaderboard page."
    )
    st.caption("Use the menu on the left to read the method, the full results, the broker leaderboard, "
               "or to explore the rating changes yourself.")


# ---------------------------------------------------------------- 2. Methodology
def page_method():
    summ = D.summary()
    k = D.constants()
    tod = D.table("rating_time_of_day.csv")
    ws = D.table("window_summary.csv")
    paths = D.table("car_by_day.csv")
    est = D.parse_window(summ.get("market_model", ""), "estimation window")
    tmin, tmax = int(paths["t"].min()), int(paths["t"].max())
    ew = summ.get("earnings_window_trading_days", "")
    mkt = k.get("MKT", "SPY")

    st.title("Methodology")
    st.markdown(
        "We run an **event study**: line up every rating change on its own day 0, then look at how the "
        "stock did on the days around it, after taking out what the market did."
    )

    st.subheader("Day 0: when could investors trade on the call?")
    st.markdown(
        f"Yahoo gives each rating change a timestamp, which we convert to U.S. Eastern time. "
        f"**Day 0** is the first trading day on which an investor could act on the news:\n\n"
        f"- Before the {k.get('MARKET_OPEN', '')} open: that trading day.\n"
        f"- During market hours: that same trading day.\n"
        f"- At or after the {k.get('MARKET_CLOSE', '')} close: the next trading day.\n"
        f"- Weekends and holidays: the next trading day.\n\n"
        f"{100 * D.num(summ, 'share_before_open'):.0f}% of rating changes are stamped before the open, "
        f"{100 * D.num(summ, 'share_during_market'):.0f}% during market hours and "
        f"{100 * D.num(summ, 'share_after_close'):.0f}% after the close. The timestamps are the vendor's "
        "record and could not be checked against the brokers' own release times."
    )
    C.hour_bars(tod, open_h=clock_hours(k.get("MARKET_OPEN")), close_h=clock_hours(k.get("MARKET_CLOSE")))

    st.subheader("Abnormal returns and CAR")
    if est is None:
        st.error("Could not read the estimation window from `outputs/tables/sample_summary.csv` "
                 "(row `market_model`). Run `python run_all.py` to rebuild it.")
        st.stop()
    st.markdown(
        f"- **Expected return.** For each event we fit a market model, stock return = alpha + beta x "
        f"{mkt} return, on trading days [{est[0]}, {est[1]}] before day 0 "
        f"(at least {k.get('MIN_EST_DAYS', 'n/a')} daily returns required).\n"
        "- **Abnormal return** = the stock's actual return minus that expected return. It is the part of "
        "the move the market does not explain.\n"
        f"- **CAR** (cumulative abnormal return) adds up abnormal returns over a window of days. We use "
        f"three windows inside the event window [{tmin}, +{tmax}]:\n"
        + "\n".join(f"    - **CAR{w}** ({WINDOW_NAMES.get(w, '').lower()})" for w in ws["window"].unique())
        + "\n\nThe headline is CAR[-1,+1], the reaction from the day before to the day after day 0."
    )

    st.subheader("Episodes, earnings and the clean sample")
    st.markdown(
        "- **Episode.** When several brokers change their rating on the same stock on the same day, they "
        "share one price move, so they count as one episode. Days with both an upgrade and a downgrade "
        "(mixed) are left out.\n"
        f"- **Near earnings.** A rating change is near earnings when its day 0 is within {ew} trading days "
        "of the same firm's earnings day 0. The window leans forward because analysts often re-rate right "
        "after a report.\n"
        f"- **Clean (headline).** Not near earnings, no other rating change on the same stock within 2 "
        "trading days, and not a mixed day.\n"
        f"- **Clean window.** A stricter sample with no earnings report anywhere in [{tmin},+{tmax}], used "
        "only to read the long windows."
    )

    st.subheader("Sample funnel")
    n_up_ep, n_dn_ep = D.num(summ, "n_episodes_upgrade", int), D.num(summ, "n_episodes_downgrade", int)
    clean_n = ws[(ws["sample"] == "clean") & (ws["window"] == "[-1,+1]")].set_index("direction")["n"]
    funnel = pd.DataFrame([
        ("S&P 500 members on " + str(k.get("UNIVERSE_ASOF", "")), D.num(summ, "n_sp500_members_2020", int)),
        ("Members with no Yahoo prices today (dropped)", D.num(summ, "n_members_no_yahoo_prices", int)),
        (f"Members with a short {k.get('RANK_YEAR', '')} price history (dropped)", D.num(summ, "n_members_short_2020_history", int)),
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
    st.markdown("Unit = one **episode** (one stock on one day 0). Returns are market-model abnormal returns "
                "in percent.")
    sample = st.selectbox("Sample", samples, index=0, key="res_sample",
                          format_func=lambda s: D.SAMPLE_LABELS.get(s, s))
    st.caption(desc.get(sample, ""))

    col_chart, col_table = st.columns([11, 9], gap="medium")
    with col_chart:
        st.markdown("##### Average CAR around the rating change")
        if sample in set(cbd["sample"]):
            path = cbd[cbd["sample"] == sample]
            note = "Source: `outputs/tables/car_by_day.csv`."
        else:
            path = D.panel_car_paths()
            path = path[path["sample"] == sample]
            note = ("`car_by_day.csv` does not include this sample, so this path is computed here from "
                    "`data/processed/event_panel.csv` with the same method. That method reproduces "
                    "`car_by_day.csv` exactly for the samples the file does contain.")
        C.car_path(path)
        st.caption("Lines are the average CAR added up from the first day shown; shaded bands are 95% "
                   "confidence intervals. The grey strip marks days -1 to +1. " + note)
    with col_table:
        st.markdown("##### Event study summary")
        s = ws[ws["sample"] == sample].copy()
        s["window"] = pd.Categorical(s["window"], list(WINDOW_NAMES), ordered=True)
        s = s.sort_values(["direction", "window"], ascending=[False, True])
        show = pd.DataFrame({
            "": s["direction"].str.capitalize(),
            "CAR window": [f"{w} {WINDOW_NAMES.get(w, '').lower()}" for w in s["window"]],
            "n": s["n"].astype(int).astype(str),
            "Mean": s["mean_pct"].map(D.pct),
            "t": s["t_stat"].map(lambda x: f"{x:.1f}"),
            "95% CI (%)": [f"{lo:+.2f} to {hi:+.2f}" for lo, hi in zip(s["ci_lo_pct"], s["ci_hi_pct"])],
        })
        st.table(show, hide_index=True)
        st.caption("t = mean / standard error. A |t| above about 2 means the average is unlikely to be "
                   "zero by chance. Source: `outputs/tables/window_summary.csv`.")
        st.caption("These are associations around the rating date, not proof that the call caused the move.")

    st.divider()
    st.subheader("Do earnings reports change the picture?")
    ec = D.table("earnings_comparison.csv")
    reg = D.table("earnings_regression.csv")
    ew = summ.get("earnings_window_trading_days", "")
    st.markdown(f"An episode overlaps earnings when the firm's earnings day 0 is within {ew} trading days of "
                "the rating change's day 0.")
    show = pd.DataFrame({
        "Direction": ec["direction"].str.capitalize(), "Earnings": ec["earnings"], "n": ec["n"].astype(int),
        "Mean CAR[-1,+1]": ec["mean_pct"].map(D.pct), "t": ec["t_stat"].round(1),
        "95% CI": [D.ci(lo, hi) for lo, hi in zip(ec["ci_lo_pct"], ec["ci_hi_pct"])]})
    st.dataframe(show, hide_index=True, width="stretch")
    st.markdown(earnings_regression_text(reg))
    st.caption("Source: `outputs/tables/earnings_comparison.csv` and `outputs/tables/earnings_regression.csv`.")

    with st.expander("Robustness: the CAR[-1,+1] answer under other choices"):
        rb = D.table("robustness.csv")
        st.dataframe(pd.DataFrame({
            "Specification": rb["spec"], "Direction": rb["direction"].str.capitalize(),
            "n": rb["n"].astype(int), "Mean CAR[-1,+1]": rb["mean_pct"].map(D.pct),
            "SE": rb["se_pct"].map(lambda x: f"{x:.2f}"), "t": rb["t_stat"].round(1)}),
            hide_index=True, width="stretch")
        st.caption("Each row changes one choice (benchmark, day-0 rule, sample, unit, or how standard errors "
                   "are computed). Source: `outputs/tables/robustness.csv`.")


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
        f"**One regression with both effects** ({int(b0['n']):,} episodes, standard errors clustered by stock, "
        f"{int(b0['n_clusters'])} stocks). We measure the reaction in the direction of the call (upgrades as "
        f"is, downgrades with the sign flipped). A downgrade not near earnings moves the price by "
        f"{b0['coef']:.2f}% in the direction of the call. An upgrade not near earnings moves it "
        f"{abs(b1['coef']):.2f} points {'more' if b1['coef'] > 0 else 'less'} ({D.p_eq(b1['p_value'])}). Being near earnings adds "
        f"{b2['coef']:.2f} points for downgrades ({D.p_eq(b2['p_value'])}), and that earnings boost is "
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
    st.markdown(
        f"A third test, Kruskal-Wallis, compares whole distributions (ranks), not averages. Here it gives "
        f"{D.p_eq(p['kw'])}. It can reject even when averages are equal, because returns have fat tails "
        "and brokers differ in spread (some cover volatile stocks, some call right after earnings). "
        f"The estimated spread of brokers' true averages (tau) is {p['tau']:.2f} percentage points, "
        f"{'small next to' if p['tau'] < D.num(summ, 'se_of_broker_mean_at_n10_pp') else 'compared with'} the noise in one broker's average at n = 10 ({D.num(summ, 'se_of_broker_mean_at_n10_pp'):.2f} "
        "points of standard error)."
    )
    st.markdown(
        f"**Minimum calls rule.** Only brokers with at least {min_calls} calls in a direction are ranked. "
        "Because small averages are noisy, the order uses a **shrunk mean** that pulls each broker toward "
        "the overall average; the less data a broker has, the more it is pulled."
    )

    sub = lb[(lb["sample"] == sample) & (lb["direction"] == direction)]
    ranked = sub[sub["meets_min_n"]].sort_values("rank")
    ref = (sub["n"] * sub["mean_pct"]).sum() / sub["n"].sum()   # call-weighted = mean over all calls
    if ranked.empty:
        st.info("No broker meets the minimum number of calls in this sample and direction.")
    else:
        C.broker_dots(ranked, direction, ref_mean=ref)
        st.caption("Dots are each broker's average CAR[-1,+1] with a 95% confidence interval; diamonds are "
                   f"the shrunk means used for the order. "
                   f"{int(((ranked['ci_lo_pct'] <= ref) & (ranked['ci_hi_pct'] >= ref)).sum())} of {len(ranked)} "
                   "intervals include the dashed line (the average over all calls in this sample). "
                   "Source: `outputs/tables/broker_leaderboard.csv`.")

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
    with st.expander("Robustness: CAR scaled by each stock's own noise"):
        sd = D.table("broker_leaderboard_standardized.csv")
        s = sd[(sd["sample"] == sample) & (sd["direction"] == direction) & sd["meets_min_n"]].sort_values("rank")
        st.markdown("Each CAR is divided by the stock's usual 3-day noise, so volatile stocks do not dominate. "
                    "The value is in units of that noise, not percent.")
        st.dataframe(pd.DataFrame({
            "Order": s["rank"].astype(int), "Broker": s["broker"], "Calls": s["n"].astype(int),
            "Mean scaled CAR": s["mean_scar"].round(2), "t": s["t_stat"].round(1)}),
            hide_index=True, width="stretch")
        st.caption("Source: `outputs/tables/broker_leaderboard_standardized.csv`.")
    with st.expander("How stable is the order?"):
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
def page_explore():
    ev = D.processed("events.csv")
    ev["day0"] = pd.to_datetime(ev["day0"])
    ev["year"] = ev["day0"].dt.year

    st.title("Explore the rating changes")
    st.markdown(
        "Filter the individual rating changes. Numbers here are **per rating change** (from "
        "`data/processed/events.csv`), not per episode, so they can differ from the headline: calls on a "
        "day when several brokers moved the same stock share one CAR and count more than once here, and "
        "this page does not apply the clean-sample rules (the earnings filter below covers only part of them)."
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

    st.metric("Matching rating changes", f"{len(f):,}")
    if f.empty:
        st.info("No rating changes match these filters. Try removing a company or broker, or widening the years.")
        return

    dirs = [d for d in ["upgrade", "downgrade"] if (f["direction"] == d).any()]
    cols = st.columns(len(dirs))
    for col, d in zip(cols, dirs):
        r = D.mean_stats(f.loc[f["direction"] == d, "car_m1_p1"])
        with col:
            col.metric(f"{C.LABEL[d]}: mean CAR[-1,+1]", D.pct(r["mean_pct"]), border=True)
            if r["n"] >= EXPLORE_MIN_N:
                st.caption(f"n = {r['n']}, t = {r['t_stat']:.1f}, 95% CI {D.ci(r['ci_lo_pct'], r['ci_hi_pct'])}")
            else:
                st.caption(f"n = {r['n']}. Too few to say: with fewer than {EXPLORE_MIN_N} rating changes we "
                           "do not report a t-stat or interval; the average can swing a lot with one call.")
    st.caption("Upgrades and downgrades are shown separately because averaging them together would cancel out.")

    show = pd.DataFrame({
        "Day 0": f["day0"].dt.date, "Ticker": f["ticker"], "Broker": f["broker"],
        "Direction": f["direction"], "From": f["from_grade"], "To": f["to_grade"],
        "Timing": f["timing"], "Near earnings": f["near_earnings"],
        "Brokers that day": f["n_same_day_calls"],
        "CAR[-1,+1] (%)": (100 * f["car_m1_p1"]).round(2),
        "CAR[-20,-2] (%)": (100 * f["car_m20_m2"]).round(2),
        "CAR[+2,+20] (%)": (100 * f["car_p2_p20"]).round(2),
    }).sort_values("Day 0", ascending=False)

    C.histogram(show.rename(columns={"Direction": "direction"}), "CAR[-1,+1] (%)")
    st.dataframe(show, hide_index=True, width="stretch", height=380)
    st.download_button("Download these rows (CSV)", show.to_csv(index=False).encode("utf-8"),
                       file_name="rating_changes_filtered.csv", mime="text/csv", key="ex_download")
    st.caption("Click a column header to sort. CAR columns are in percent.")
