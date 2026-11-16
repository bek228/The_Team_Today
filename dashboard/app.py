"""Streamlit dashboard for the analyst-rating event study (FIN331, The Team Today).

Run from the repository root:
    streamlit run dashboard/app.py

The dashboard reads only committed pipeline outputs (outputs/tables/*.csv, data/processed/*.csv,
data/raw/universe.csv, and constants from src/_common.py). It never downloads data and never
reruns the study. Rebuild the inputs with `python run_all.py`.
"""
import sys
from pathlib import Path

import streamlit as st

# make the helper modules next to this file importable however Streamlit is launched
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ui_data as D  # noqa: E402
import ui_pages as P  # noqa: E402

st.set_page_config(page_title="Analyst Rating Event Study", layout="wide")

PAGES = {
    "Introduction": P.page_intro,
    "Methodology": P.page_method,
    "Results": P.page_results,
    "Broker leaderboard": P.page_brokers,
    "Explore": P.page_explore,
}

with st.sidebar:
    st.markdown("## Analyst Rating Event Study")
    st.divider()
    page = st.radio("Go to", list(PAGES), key="page", label_visibility="collapsed")
    st.divider()
    summ = D.summary()
    k = D.constants()
    st.caption(
        f"{D.num(summ, 'n_firms', int)} large U.S. firms. Rating changes from {summ['sample_start']} "
        f"to {summ['sample_end']}. Market benchmark: {k.get('MKT', 'n/a')}. Data: Yahoo Finance, "
        f"pulled {summ.get('data_pull_date', 'n/a')}."
    )
    st.caption("Event-window associations, not proof that analysts cause the moves.")

PAGES[page]()
