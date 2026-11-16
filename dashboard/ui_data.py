"""File loading and small formatting helpers for the dashboard.

The dashboard only reads files that run_all.py writes and that are committed to git.
It never downloads anything and never reruns the study.

Units: tables in outputs/tables/ are in PERCENT (1.25 means 1.25%).
Event-level files in data/processed/ (events.csv, episodes.csv, event_panel.csv) are DECIMALS
(0.0125 means 1.25%).
"""
import ast
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
COMMON = ROOT / "src" / "_common.py"

DIRS = ["upgrade", "downgrade"]

# Plain descriptions of the samples used in the pipeline (keys match the 'sample' column).
SAMPLE_LABELS = {
    "clean": "Clean episodes (headline)",
    "all": "All episodes",
    "no_earnings": "No earnings nearby",
    "near_earnings": "Near earnings",
    "clean_window": "Clean window (no earnings anywhere in the event window)",
    "single_call_days": "Single-call days only",
}


def missing_file(rel_path):
    """Stop the page with a clear message naming the missing file."""
    st.error(
        f"Missing file: `{rel_path}`. The dashboard only reads the pipeline's committed outputs. "
        "Run `python run_all.py` from the repository root to rebuild them, then reload this page."
    )
    st.stop()


@st.cache_data(show_spinner=False)
def _read_csv(path_str, mtime):
    """Cached read. mtime is part of the cache key, so a rerun of the pipeline is picked up."""
    return pd.read_csv(path_str)


def load(rel_path):
    """Read a committed CSV by its path relative to the repo root, or stop with an error."""
    path = ROOT / rel_path
    if not path.exists():
        missing_file(rel_path)
    return _read_csv(str(path), path.stat().st_mtime).copy()


def table(name):
    return load(f"outputs/tables/{name}")


def processed(name):
    return load(f"data/processed/{name}")


@st.cache_data(show_spinner=False)
def _read_constants(path_str, mtime):
    """Simple literal constants (NAME = 10, NAME = (-1, 2), ...) from src/_common.py.

    Parsed with ast, not imported, so nothing in the pipeline runs.
    """
    tree = ast.parse(Path(path_str).read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value
                elif isinstance(target, ast.Tuple) and isinstance(value, tuple):
                    for t, v in zip(target.elts, value):
                        if isinstance(t, ast.Name):
                            out[t.id] = v
    return out


def constants():
    if not COMMON.exists():
        missing_file("src/_common.py")
    return _read_constants(str(COMMON), COMMON.stat().st_mtime)


def summary():
    """sample_summary.csv as a dict metric -> value (values are strings; use num())."""
    s = table("sample_summary.csv")
    return dict(zip(s["metric"], s["value"]))


def num(summ, key, kind=float):
    """A numeric value from the summary dict, or stop with an error if the row is missing."""
    if key not in summ:
        st.error(f"Row `{key}` is missing from `outputs/tables/sample_summary.csv`. "
                 "Run `python run_all.py` to rebuild it.")
        st.stop()
    return kind(float(summ[key]))


def parse_window(text, label):
    """'(-250, -30)' style tuple after `label` in a string, e.g. the market_model row."""
    m = re.search(re.escape(label) + r"\s*\((-?\d+),\s*(-?\d+)\)", str(text))
    return (int(m.group(1)), int(m.group(2))) if m else None


# ---- formatting ----
def pct(x, signed=True, digits=2):
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:+.{digits}f}%" if signed else f"{x:.{digits}f}%"


def pval(p):
    if p is None or pd.isna(p):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def p_eq(p):
    """'p = 0.053' or 'p < 0.001', for use inside sentences."""
    text = pval(p)
    return f"p {text}" if text.startswith("<") else f"p = {text}"


def ci(lo, hi):
    return f"[{lo:+.2f}%, {hi:+.2f}%]"


def mean_stats(x):
    """n, mean, SE, t, 95% CI for a series of decimals; returned in percent.

    Same formula as mean_se() in src/05_results.py: SE = sd / sqrt(n), CI = mean +- 1.96 SE.
    """
    x = pd.Series(x, dtype=float).dropna()
    n = len(x)
    m = x.mean() if n else np.nan
    se = x.std() / np.sqrt(n) if n > 1 else np.nan
    return dict(n=n, mean_pct=100 * m, se_pct=100 * se,
                t_stat=m / se if n > 1 and se > 0 else np.nan,
                ci_lo_pct=100 * (m - 1.96 * se), ci_hi_pct=100 * (m + 1.96 * se))


# ---- the CAR path for a sample that car_by_day.csv does not contain ----
def _pick(df, sample):
    """Same sample rules as pick() in src/05_results.py."""
    if sample == "clean":
        return df[~df["near_earnings"] & ~df["other_call_in_window"]]
    if sample == "no_earnings":
        return df[~df["near_earnings"]]
    if sample == "near_earnings":
        return df[df["near_earnings"]]
    if sample == "clean_window":
        return df[~df["earnings_in_window"]]
    return df


@st.cache_data(show_spinner="Building the CAR path from event_panel.csv ...")
def _panel_paths(ev_path, ep_path, pan_path, mtimes):
    ev = pd.read_csv(ev_path, usecols=["event_id", "ticker", "day0"])
    ep = pd.read_csv(ep_path, usecols=["ticker", "day0", "direction", "near_earnings",
                                       "other_call_in_window", "earnings_in_window"])
    pan = pd.read_csv(pan_path, usecols=["event_id", "t", "CAR"])
    ep = ep[ep["direction"].isin(DIRS)]
    # one episode = the panel rows of its first call (as in src/05_results.py)
    first = ev.sort_values("event_id").groupby(["ticker", "day0"])["event_id"].first().reset_index()
    key = ep.merge(first, on=["ticker", "day0"], how="left", validate="1:1")
    pan = pan.merge(key.drop(columns=["ticker", "day0"]), on="event_id", how="inner", validate="m:1")
    rows = []
    for sample in ["all", "no_earnings", "near_earnings", "clean", "clean_window"]:
        g = _pick(pan, sample).groupby(["direction", "t"])["CAR"]
        out = pd.DataFrame({"n": g.size(), "mean": g.mean(), "sd": g.std()}).reset_index()
        se = out["sd"] / np.sqrt(out["n"])
        out = pd.DataFrame({"sample": sample, "direction": out["direction"], "t": out["t"], "n": out["n"],
                            "mean_pct": 100 * out["mean"], "ci_lo_pct": 100 * (out["mean"] - 1.96 * se),
                            "ci_hi_pct": 100 * (out["mean"] + 1.96 * se)})
        rows.append(out)
    return pd.concat(rows, ignore_index=True).round(4)


def panel_car_paths():
    """CAR paths recomputed from the event panel, for every sample (percent, rounded like the file)."""
    paths = ["data/processed/events.csv", "data/processed/episodes.csv", "data/processed/event_panel.csv"]
    for p in paths:
        if not (ROOT / p).exists():
            missing_file(p)
    full = [str(ROOT / p) for p in paths]
    return _panel_paths(*full, tuple(Path(p).stat().st_mtime for p in full)).copy()
