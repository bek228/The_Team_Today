"""
Streamlit dashboard for the analyst-rating event study.
Run from the repository root:
    streamlit run dashboard/app.py
"""

from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "figures"
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(
    page_title="Analyst Rating Changes | Event Study",
    page_icon="📈",
    layout="wide",
)

@st.cache_data
def load_csv(path):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()

summary = load_csv(TABLES / "upgrade_downgrade_summary.csv")
earnings = load_csv(TABLES / "earnings_comparison.csv")
event_study = load_csv(TABLES / "event_study_results.csv")
episodes = load_csv(TABLES / "event_reaction_episodes.csv")
events = load_csv(PROCESSED / "events.csv")

def pct(value):
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "—"

def metric_rows(frame, group_name, metric="CAR_m1_p1"):
    if frame.empty or not {"group", "metric", "mean"}.issubset(frame.columns):
        return pd.DataFrame()
    result = frame.loc[
        (frame["group"].astype(str) == group_name)
        & (frame["metric"].astype(str) == metric)
    ]
    return result

def show_missing_files():
    expected = [
        TABLES / "upgrade_downgrade_summary.csv",
        TABLES / "earnings_comparison.csv",
        TABLES / "event_study_results.csv",
        TABLES / "event_reaction_episodes.csv",
        FIGURES / "event_study.png",
    ]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    if missing:
        st.warning(
            "Some project outputs are not present yet: "
            + ", ".join(missing)
            + ". Upload or regenerate these files, then refresh the app."
        )

st.sidebar.title("Analyst Rating Event Study")
page = st.sidebar.radio(
    "Navigate",
    ["Introduction", "Methodology", "Results", "Explore"],
)
st.sidebar.caption("HW8 prototype · Five-company sample")
show_missing_files()

if page == "Introduction":
    st.title("Do Analyst Upgrades Move Stock Prices?")
    st.subheader("And does the broker matter?")
    st.write(
        "This project examines how stock prices behave around analyst rating "
        "upgrades and downgrades, and explores whether observed reactions differ "
        "when recommendations coincide with earnings announcements."
    )
    st.markdown("### Research design")
    col1, col2, col3 = st.columns(3)
    col1.metric("Companies", "5")
    col2.metric("Study start", "January 2021")
    col3.metric("Benchmark", "SPY")
    st.write("**Sample:** AAPL, MSFT, AMZN, JPM, and NVDA.")
    st.write(
        "The current HW8 version is an exploratory five-stock study. "
        "It is not the expanded final-project sample."
    )
    st.info(
        "The analysis measures event-window associations. It does not establish "
        "that analyst actions caused the observed price movements."
    )

elif page == "Methodology":
    st.title("Methodology")
    st.markdown("### Data")
    st.write(
        "Analyst rating histories, adjusted daily prices, and historical earnings "
        "dates are retrieved from Yahoo Finance for five companies. SPY is used "
        "as the market benchmark."
    )
    st.markdown("### Event classification and timing")
    st.write(
        "Rating actions are classified as upgrades or downgrades. Timestamps "
        "are converted to U.S. Eastern time. Recommendations before 9:30 a.m. "
        "Eastern are assigned to that trading session; recommendations at or "
        "after 9:30 a.m. are assigned to the next available trading session. "
        "Weekend and holiday events are assigned to the next available session."
    )
    st.markdown("### Earnings overlap")
    st.write(
        "Events are flagged when an earnings announcement falls within one "
        "trading day before or after the assigned analyst event date. Earnings "
        "announcements are assigned to the next session when released at or "
        "after 9:30 a.m. Eastern."
    )
    st.markdown("### Return measurement")
    st.write(
        "The analysis calculates abnormal returns relative to SPY and cumulative "
        "abnormal returns over event windows, including CAR[-1,+1]. "
        "Multiple analyst calls for the same ticker and event date are consolidated "
        "into one market-reaction episode for the episode-level comparisons."
    )
    st.caption(
        "Daily data cannot isolate intraday price reactions. Timestamp accuracy "
        "and the limited five-company sample are important constraints."
    )

elif page == "Results":
    st.title("Results")
    st.write(
        "The figures below summarize the exploratory event-study results. "
        "Returns are shown as decimal values converted to percentages."
    )

    if not summary.empty and {"group", "metric", "mean"}.issubset(summary.columns):
        st.markdown("### Average CAR[-1,+1] by event type")
        chosen = summary.loc[summary["metric"].astype(str) == "CAR_m1_p1"].copy()
        if not chosen.empty:
            display = chosen.copy()
            display["Average CAR"] = display["mean"].map(pct)
            if "n" in display.columns:
                display = display.rename(columns={"n": "Episodes"})
            keep = [c for c in ["group", "Episodes", "Average CAR", "ci_lower", "ci_upper"] if c in display.columns]
            st.dataframe(display[keep], use_container_width=True, hide_index=True)
        else:
            st.dataframe(summary, use_container_width=True, hide_index=True)
    else:
        st.info("The upgrade/downgrade summary table will appear here once uploaded.")

    chart = FIGURES / "event_study.png"
    if chart.exists():
        st.markdown("### Event-study chart")
        st.image(str(chart), use_container_width=True)
    else:
        st.info("Upload outputs/figures/event_study.png to display the event-study chart.")

    with st.expander("Earnings comparison"):
        if not earnings.empty:
            st.dataframe(earnings, use_container_width=True, hide_index=True)
        else:
            st.info("The earnings comparison table is not available yet.")

    with st.expander("Event-study estimates"):
        if not event_study.empty:
            st.dataframe(event_study, use_container_width=True, hide_index=True)
        else:
            st.info("The event-study results table is not available yet.")

elif page == "Explore":
    st.title("Explore the Events")
    data = episodes.copy() if not episodes.empty else events.copy()
    if data.empty:
        st.warning(
            "No event-level data found. Make sure "
            "outputs/tables/event_reaction_episodes.csv or "
            "data/processed/events.csv is in the repository."
        )
    else:
        if "ticker" in data.columns:
            tickers = sorted(data["ticker"].dropna().astype(str).unique())
            selected_tickers = st.multiselect("Filter by ticker", tickers, default=tickers)
            data = data[data["ticker"].astype(str).isin(selected_tickers)]

        type_col = "event_type" if "event_type" in data.columns else None
        if type_col:
            types = sorted(data[type_col].dropna().astype(str).unique())
            selected_types = st.multiselect("Filter by event type", types, default=types)
            data = data[data[type_col].astype(str).isin(selected_types)]

        if "earnings_overlap" in data.columns:
            earnings_filter = st.selectbox(
                "Earnings overlap",
                ["All", "Yes", "No"],
            )
            if earnings_filter != "All":
                target = earnings_filter == "Yes"
                data = data[
                    data["earnings_overlap"].astype(str).str.lower().isin(
                        ["true", "1"] if target else ["false", "0"]
                    )
                ]

        st.caption(f"{len(data):,} rows match the selected filters.")
        st.dataframe(data, use_container_width=True, hide_index=True)

        numeric_columns = [
            c for c in ["AR_0", "CAR_m1_p1", "CAR_0_p1"] if c in data.columns
        ]
        if numeric_columns:
            st.markdown("### Return distribution in the selected sample")
            st.bar_chart(data[numeric_columns].mean().to_frame("Mean return"))

st.sidebar.divider()
st.sidebar.caption("Source: Yahoo Finance · Exploratory academic project")
