"""
Reproducible analyst-rating event study pipeline.

This script preserves the workflow in notebooks/HW8_Data.ipynb.
Run from the repository root with: python run_all.py
"""

from IPython.display import display



# ================== NOTEBOOK CELL 2 ==================
from pathlib import Path
from datetime import date, timedelta
import re
import time

import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = ["AAPL", "MSFT", "AMZN", "JPM", "NVDA"]
BENCHMARK = "SPY"
START_DATE = "2021-01-01"

# Yahoo's history() end date is exclusive. Add one day to include today's data.
END_DATE = (date.today() + timedelta(days=1)).isoformat()

ROOT = Path(".")
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

print("yfinance version:", yf.__version__)
print("Sample:", TICKERS)
print("Dates:", START_DATE, "through", date.today().isoformat())

# ================== NOTEBOOK CELL 4 ==================
rating_frames = []

for symbol in TICKERS:
    print(f"Downloading ratings: {symbol}")
    try:
        tkr = yf.Ticker(symbol)
        df = tkr.upgrades_downgrades.copy()

        if df is None or df.empty:
            print(f"  WARNING: no rating history returned for {symbol}")
            continue

        df = df.reset_index()
        # yfinance versions may name the date index differently.
        date_col = next((c for c in df.columns if str(c).lower() in
                         ["gradedate", "date", "index"]), df.columns[0])
        df = df.rename(columns={date_col: "grade_datetime"})
        df["ticker"] = symbol
        rating_frames.append(df)
        print(f"  {len(df):,} records")
        time.sleep(0.25)

    except Exception as exc:
        print(f"  ERROR for {symbol}: {type(exc).__name__}: {exc}")

if not rating_frames:
    raise RuntimeError("No rating records were downloaded. Check the yfinance connection/API response.")

ratings_raw = pd.concat(rating_frames, ignore_index=True, sort=False)
ratings_raw.to_csv(RAW_DIR / "ratings_raw.csv", index=False)

print("\nRaw rows:", len(ratings_raw))
print("Columns:", ratings_raw.columns.tolist())
display(ratings_raw.head(10))

# ================== NOTEBOOK CELL 6 ==================
price_frames = []

# Include a short buffer before the first event date for event-window calculations.
PRICE_START = (pd.Timestamp(START_DATE) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")

for symbol in TICKERS + [BENCHMARK]:
    print(f"Downloading prices: {symbol}")
    hist = yf.Ticker(symbol).history(
        start=PRICE_START,
        end=END_DATE,
        interval="1d",
        auto_adjust=True
    )

    if hist is None or hist.empty:
        print(f"  WARNING: no prices returned for {symbol}")
        continue

    tmp = hist.reset_index()
    date_col = next((c for c in tmp.columns if str(c).lower() in ["date", "datetime"]), tmp.columns[0])
    tmp = tmp.rename(columns={date_col: "date", "Close": "adjusted_close"})
    tmp["date"] = pd.to_datetime(tmp["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
    tmp["ticker"] = symbol
    price_frames.append(tmp[["date", "ticker", "adjusted_close"]])
    print(f"  {len(tmp):,} daily prices")
    time.sleep(0.25)

if not price_frames:
    raise RuntimeError("No price data downloaded.")

prices_raw = pd.concat(price_frames, ignore_index=True)
prices_raw = prices_raw.drop_duplicates(["ticker", "date"]).sort_values(["ticker", "date"])
prices_raw.to_csv(RAW_DIR / "prices_raw.csv", index=False)

display(prices_raw.head())
print("Price date range:", prices_raw.date.min(), "to", prices_raw.date.max())

# ================== NOTEBOOK CELL 8 ==================
earnings_frames = []

for symbol in TICKERS:
    print(f"Downloading earnings dates: {symbol}")
    try:
        tkr = yf.Ticker(symbol)
        ed = tkr.get_earnings_dates(limit=100)

        if ed is None or ed.empty:
            print(f"  WARNING: no earnings dates returned for {symbol}")
            continue

        ed = ed.reset_index()
        date_col = next(
            (c for c in ed.columns if "earnings" in str(c).lower() or str(c).lower() in ["index", "date"]),
            ed.columns[0]
        )
        ed = ed.rename(columns={date_col: "earnings_datetime"})
        ed["ticker"] = symbol
        earnings_frames.append(ed)
        print(f"  {len(ed):,} earnings records")
        time.sleep(0.25)

    except Exception as exc:
        print(f"  ERROR for {symbol}: {type(exc).__name__}: {exc}")

if earnings_frames:
    earnings_raw = pd.concat(earnings_frames, ignore_index=True, sort=False)
else:
    earnings_raw = pd.DataFrame(columns=["earnings_datetime", "ticker"])

earnings_raw.to_csv(RAW_DIR / "earnings_dates_raw.csv", index=False)

print("\nRaw earnings-date records:", len(earnings_raw))
print("Tickers with earnings-date coverage:", earnings_raw["ticker"].nunique() if not earnings_raw.empty else 0)
display(earnings_raw.head(10))

# ================== NOTEBOOK CELL 10 ==================
# Normalize expected source columns while retaining the raw file unchanged.
required_source_cols = ["ticker", "grade_datetime", "Firm", "ToGrade", "FromGrade", "Action"]
missing = [c for c in required_source_cols if c not in ratings_raw.columns]
if missing:
    raise ValueError(
        f"Expected columns not found: {missing}. Actual columns: {ratings_raw.columns.tolist()}. "
        "Inspect ratings_raw and update the mapping before proceeding."
    )

ratings = ratings_raw.copy()

# Yahoo's rating timestamps are treated as UTC, then converted to US Eastern.
ratings["grade_datetime"] = pd.to_datetime(ratings["grade_datetime"], errors="coerce", utc=True)
ratings["event_datetime_et"] = ratings["grade_datetime"].dt.tz_convert("America/New_York")
ratings["event_date"] = (
    ratings["event_datetime_et"].dt.tz_localize(None).dt.normalize()
)
ratings["event_time_et"] = ratings["event_datetime_et"].dt.strftime("%H:%M:%S")

ratings["action_clean"] = ratings["Action"].astype(str).str.strip().str.lower()

def classify_action(action):
    if re.search(r"\b(up|upgrade|upgraded)\b", action):
        return "Upgrade"
    if re.search(r"\b(down|downgrade|downgraded)\b", action):
        return "Downgrade"
    return np.nan

ratings["event_type"] = ratings["action_clean"].apply(classify_action)

events = ratings.loc[ratings["event_type"].notna()].copy()
events = events.loc[events["event_date"] >= pd.Timestamp(START_DATE)].copy()

events = events.rename(columns={
    "Firm": "broker",
    "FromGrade": "from_grade",
    "ToGrade": "to_grade",
    "Action": "source_action"
})

events["broker"] = events["broker"].astype(str).str.strip()
events["from_grade"] = events["from_grade"].astype(str).str.strip()
events["to_grade"] = events["to_grade"].astype(str).str.strip()

key_cols = ["ticker", "event_date", "broker", "from_grade", "to_grade", "event_type"]
events["duplicate_n"] = events.groupby(key_cols, dropna=False).cumcount() + 1
events["event_id"] = (
    events["ticker"].astype(str) + "_" +
    events["event_date"].dt.strftime("%Y%m%d") + "_" +
    events["broker"].str.replace(r"[^A-Za-z0-9]+", "", regex=True) + "_" +
    events["duplicate_n"].astype(str)
)

events = events[[
    "event_id", "ticker", "event_date", "grade_datetime", "event_datetime_et",
    "event_time_et", "broker", "from_grade", "to_grade", "event_type",
    "source_action", "duplicate_n"
]].sort_values(["event_date", "ticker", "broker"]).reset_index(drop=True)

print("All raw rating records:", len(ratings_raw))
print("Qualifying upgrades/downgrades:", len(events))
print("Upgrades:", (events.event_type == "Upgrade").sum())
print("Downgrades:", (events.event_type == "Downgrade").sum())
print("Tickers represented:", events.ticker.nunique())
display(events.head(15))

# ================== NOTEBOOK CELL 12 ==================

# ============================================================
# CELL 12: EARNINGS MATCHING + EVENT TRADING-DATE ASSIGNMENT
# ============================================================

# 0. Make the cell safe to rerun
# Remove duplicate column names and previously calculated fields.

events = events.loc[:, ~events.columns.duplicated()].copy()

derived_columns = [
    "event_trade_date",
    "nearest_earnings_date",
    "days_from_earnings",
    "earnings_overlap",
    "earnings_data_available"
]

events = events.drop(
    columns=derived_columns,
    errors="ignore"
)


# ------------------------------------------------------------
# 1. Build trading calendars
# ------------------------------------------------------------

trading_dates = {
    ticker: pd.DatetimeIndex(
        prices_raw.loc[
            prices_raw.ticker == ticker, "date"
        ].dropna().sort_values().unique()
    )
    for ticker in TICKERS
}


# ------------------------------------------------------------
# 2. Timestamp conversion and trading-session assignment
# ------------------------------------------------------------

def eastern_timestamp(value):
    """Convert timestamp to US Eastern time."""

    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    else:
        ts = ts.tz_convert("America/New_York")

    return ts


def assign_announcement_session(timestamp, ticker):
    """
    Assign announcement to the appropriate trading session.

    Before 9:30 AM ET: same trading day.
    At/after 9:30 AM ET: next trading day.
    Weekends and holidays: next available trading session.
    """

    ts = eastern_timestamp(timestamp)

    target_date = (
        ts.tz_localize(None).normalize()
    )

    if ts.time() >= pd.Timestamp("09:30:00").time():
        target_date += pd.Timedelta(days=1)

    dates = trading_dates.get(
        ticker, pd.DatetimeIndex([])
    )

    pos = dates.searchsorted(
        target_date, side="left"
    )

    if pos >= len(dates):
        return pd.NaT

    return dates[pos]


# ------------------------------------------------------------
# 3. Clean historical earnings announcements
# ------------------------------------------------------------

if not earnings_raw.empty:

    earnings = earnings_raw.copy()

    # Locate reported EPS column.
    reported_eps_col = next(
        (
            c for c in earnings.columns
            if str(c).strip().lower()
            in ["reported eps", "reported_eps"]
        ),
        None
    )

    if reported_eps_col is None:

        print("WARNING: Reported EPS column unavailable.")

        earnings = pd.DataFrame(
            columns=[
                "ticker",
                "earnings_datetime",
                "earnings_trade_date"
            ]
        )

    else:

        # Keep only announcements with reported EPS.
        # This excludes future estimates.
        earnings = earnings.loc[
            earnings[reported_eps_col].notna()
        ].copy()

        # Preserve original timestamps in UTC.
        earnings["earnings_datetime"] = pd.to_datetime(
            earnings["earnings_datetime"],
            errors="coerce",
            utc=True
        )

        # Assign announcements to trading sessions.
        earnings["earnings_trade_date"] = earnings.apply(
            lambda row: assign_announcement_session(
                row["earnings_datetime"],
                row["ticker"]
            ),
            axis=1
        )

        earnings = earnings.dropna(
            subset=["earnings_trade_date"]
        )

        earnings = earnings[
            [
                "ticker",
                "earnings_datetime",
                "earnings_trade_date"
            ]
        ].drop_duplicates()

else:

    earnings = pd.DataFrame(
        columns=[
            "ticker",
            "earnings_datetime",
            "earnings_trade_date"
        ]
    )


# Save cleaned earnings dataset.
earnings.to_csv(
    PROCESSED_DIR / "earnings_dates.csv",
    index=False
)


# ------------------------------------------------------------
# 4. Build earnings calendars by ticker
# ------------------------------------------------------------

earnings_trading_dates = {}
earnings_coverage = {}

for ticker in TICKERS:

    ticker_earnings = earnings.loc[
        earnings.ticker == ticker,
        "earnings_trade_date"
    ].dropna()

    earnings_trading_dates[ticker] = pd.DatetimeIndex(
        sorted(ticker_earnings.unique())
    )

    earnings_coverage[ticker] = (
        len(earnings_trading_dates[ticker]) > 0
    )


print("Historical earnings coverage:")

for ticker in TICKERS:
    print(
        ticker,
        len(earnings_trading_dates[ticker]),
        "announcements"
    )


# ------------------------------------------------------------
# 5. Assign analyst rating changes to trading sessions
# ------------------------------------------------------------

events["event_trade_date"] = events.apply(
    lambda row: assign_announcement_session(
        row["event_datetime_et"],
        row["ticker"]
    ),
    axis=1
)


# ------------------------------------------------------------
# 6. Match each rating change to nearest earnings date
# ------------------------------------------------------------

def nearest_earnings_match(row):

    ticker = row.ticker

    dates = trading_dates.get(
        ticker, pd.DatetimeIndex([])
    )

    earnings_dates = earnings_trading_dates.get(
        ticker, pd.DatetimeIndex([])
    )

    has_coverage = earnings_coverage.get(
        ticker, False
    )

    # Separate earnings-data availability from
    # whether an event has an assigned trading date.

    if (
        pd.isna(row.event_trade_date)
        or len(earnings_dates) == 0
        or len(dates) == 0
    ):

        return pd.Series({
            "nearest_earnings_date": pd.NaT,
            "days_from_earnings": np.nan,
            "earnings_overlap": pd.NA,
            "earnings_data_available": has_coverage
        })

    event_pos = dates.get_indexer(
        [pd.Timestamp(row.event_trade_date)]
    )[0]

    candidates = []

    for earnings_date in earnings_dates:

        earnings_pos = dates.get_indexer(
            [pd.Timestamp(earnings_date)]
        )[0]

        if earnings_pos >= 0:

            # Positive = rating change AFTER earnings.
            # Negative = rating change BEFORE earnings.

            distance = event_pos - earnings_pos

            candidates.append((
                abs(distance),
                distance,
                earnings_date
            ))

    if not candidates:

        return pd.Series({
            "nearest_earnings_date": pd.NaT,
            "days_from_earnings": np.nan,
            "earnings_overlap": pd.NA,
            "earnings_data_available": has_coverage
        })

    _, signed_distance, nearest_date = min(
        candidates,
        key=lambda x: (x[0], x[2])
    )

    return pd.Series({
        "nearest_earnings_date": nearest_date,
        "days_from_earnings": signed_distance,
        "earnings_overlap": abs(signed_distance) <= 1,
        "earnings_data_available": has_coverage
    })


# Calculate earnings matches.
earnings_matches = events.apply(
    nearest_earnings_match,
    axis=1
)

# Attach exactly one copy of each calculated column.
events = pd.concat(
    [events, earnings_matches],
    axis=1
)

events["earnings_overlap"] = (
    events["earnings_overlap"].astype("boolean")
)


# ------------------------------------------------------------
# 7. Review results
# ------------------------------------------------------------

print("\nEvent trading-date coverage:")

print(
    events["event_trade_date"].notna().sum(),
    "/",
    len(events)
)


print("\nEarnings-data coverage:")

print(
    events["earnings_data_available"].sum(),
    "/",
    len(events)
)


print("\nEarnings overlap:")

covered_events = events.loc[
    events["earnings_data_available"] == True
]

print(
    covered_events["earnings_overlap"]
    .value_counts(dropna=False)
)


print("\nEvents by ticker:")

display(
    events.groupby("ticker").agg(
        total_events=("event_id", "count"),
        earnings_coverage=(
            "earnings_data_available", "sum"
        ),
        earnings_overlaps=(
            "earnings_overlap",
            lambda x: int(x.fillna(False).sum())
        )
    )
)


print("\nSample event matches:")

display(
    events[[
        "ticker",
        "event_date",
        "event_time_et",
        "event_trade_date",
        "nearest_earnings_date",
        "days_from_earnings",
        "earnings_overlap",
        "earnings_data_available"
    ]].head(20)
)

# ================== NOTEBOOK CELL 14 ==================
# Daily returns for each stock and SPY.
prices = prices_raw.copy()
prices = prices.sort_values(["ticker", "date"])
prices["daily_return"] = prices.groupby("ticker")["adjusted_close"].pct_change()

spy = (
    prices.loc[prices.ticker == BENCHMARK, ["date", "daily_return"]]
    .rename(columns={"daily_return": "market_return"})
    .dropna()
)

stock_returns = prices.loc[prices.ticker.isin(TICKERS), ["ticker", "date", "daily_return"]].copy()
returns = stock_returns.merge(spy, on="date", how="left", validate="many_to_one")
returns["abnormal_return"] = returns["daily_return"] - returns["market_return"]

trading_dates = {
    ticker: pd.DatetimeIndex(
        returns.loc[returns.ticker == ticker, "date"].dropna().sort_values().unique()
    )
    for ticker in TICKERS
}

panel_rows = []
unmatched_events = []

for row in events.itertuples(index=False):
    dates = trading_dates.get(row.ticker, pd.DatetimeIndex([]))
    if len(dates) == 0 or pd.isna(row.event_trade_date):
        unmatched_events.append((row.event_id, "no assigned event trading date"))
        continue

    event_pos = dates.get_indexer([pd.Timestamp(row.event_trade_date)])[0]
    if event_pos < 0:
        unmatched_events.append((row.event_id, "event trading date absent from price calendar"))
        continue

    for rel_day in range(-3, 4):
        p = event_pos + rel_day
        if p < 0 or p >= len(dates):
            continue

        obs_date = dates[p]
        match = returns.loc[
            (returns.ticker == row.ticker) & (returns.date == obs_date)
        ]
        if match.empty:
            continue

        m = match.iloc[0]
        panel_rows.append({
            "event_id": row.event_id,
            "ticker": row.ticker,
            "broker": row.broker,
            "event_date": row.event_date,
            "event_datetime_et": row.event_datetime_et,
            "event_trade_date": row.event_trade_date,
            "event_type": row.event_type,
            "from_grade": row.from_grade,
            "to_grade": row.to_grade,
            "nearest_earnings_date": row.nearest_earnings_date,
            "days_from_earnings": row.days_from_earnings,
            "earnings_overlap": row.earnings_overlap,
            "relative_day": rel_day,
            "observation_date": obs_date,
            "stock_return": m["daily_return"],
            "market_return": m["market_return"],
            "abnormal_return": m["abnormal_return"]
        })

event_day_panel = pd.DataFrame(panel_rows)
if event_day_panel.empty:
    raise RuntimeError("The event-day panel is empty. Check event timing and price downloads.")

event_day_panel.to_csv(PROCESSED_DIR / "event_day_panel.csv", index=False)

print("Event-day panel rows:", len(event_day_panel))
print("Events represented:", event_day_panel.event_id.nunique())
print("Unmatched events:", len(unmatched_events))
display(event_day_panel.head(14))

# ================== NOTEBOOK CELL 16 ==================
def window_car(group, start_day, end_day):
    window = group.loc[
        group.relative_day.between(start_day, end_day)
    ].sort_values("relative_day")

    expected_n = end_day - start_day + 1
    if len(window) != expected_n or window["abnormal_return"].isna().any():
        return np.nan
    return window["abnormal_return"].sum()

car_records = []
for event_id, group in event_day_panel.groupby("event_id"):
    car_records.append({
        "event_id": event_id,
        "AR_0": window_car(group, 0, 0),
        "CAR_m1_p1": window_car(group, -1, 1),
        "CAR_0_p1": window_car(group, 0, 1)
    })

cars = pd.DataFrame(car_records)
events = events.drop(columns=["AR_0", "CAR_m1_p1", "CAR_0_p1"], errors="ignore")
events = events.merge(cars, on="event_id", how="left", validate="one_to_one")

events.to_csv(PROCESSED_DIR / "events.csv", index=False)

print("Event-level rows:", len(events))
print("Unique events:", events.event_id.nunique())
print("Missing CAR[-1,+1]:", events.CAR_m1_p1.isna().sum())
display(events.head(15))

# ================== NOTEBOOK CELL 18 ==================
# Core integrity checks
assert events["event_id"].is_unique, "event_id must be unique in the event-level file"
assert set(events["event_type"].dropna().unique()).issubset({"Upgrade", "Downgrade"})
assert event_day_panel["relative_day"].between(-3, 3).all()
mapped_event_ids = set(events.loc[events["event_trade_date"].notna(), "event_id"])
assert event_day_panel["event_id"].nunique() == len(mapped_event_ids)

print("Event date range:", events.event_date.min(), "to", events.event_date.max())
print("Events assigned to a trading date:", events.event_trade_date.notna().sum(), "/", len(events))
print("Assigned event trading-date range:", events.event_trade_date.min(), "to", events.event_trade_date.max())

print("\\nEvents by ticker:")
display(events.groupby("ticker").size().rename("n_events").to_frame())

print("\\nEvents by type:")
display(events.groupby("event_type").size().rename("n_events").to_frame())

print("\\nEvents awaiting a future trading session:", events.event_trade_date.isna().sum())
print("\\nEarnings overlap coverage:")
display(events.groupby("ticker").agg(
    n_events=("event_id", "count"),
    earnings_dates_available=("earnings_data_available", "sum"),
    earnings_overlap_events=("earnings_overlap", lambda x: int(x.fillna(False).sum()))
))

print("\\nEvents by earnings overlap:")
display(events.groupby("earnings_overlap", dropna=False).agg(
    n_events=("event_id", "count"),
    mean_AR_0=("AR_0", "mean"),
    mean_CAR_m1_p1=("CAR_m1_p1", "mean")
))

print("\\nBroker coverage (top 20):")
display(events.groupby("broker").agg(
    n_events=("event_id", "count"),
    avg_AR_0=("AR_0", "mean"),
    avg_CAR_m1_p1=("CAR_m1_p1", "mean"),
    median_CAR_m1_p1=("CAR_m1_p1", "median")
).sort_values("n_events", ascending=False).head(20))

print("\\nMissingness:")
display(events[["AR_0", "CAR_m1_p1", "CAR_0_p1", "earnings_overlap"]].isna().mean().rename("missing_share").to_frame())

print("\\nSaved files:")
for path in [RAW_DIR / "ratings_raw.csv", RAW_DIR / "prices_raw.csv",
             RAW_DIR / "earnings_dates_raw.csv", PROCESSED_DIR / "earnings_dates.csv",
             PROCESSED_DIR / "events.csv", PROCESSED_DIR / "event_day_panel.csv"]:
    print(path, f"({path.stat().st_size:,} bytes)" if path.exists() else "MISSING")

# ================== NOTEBOOK CELL 22 ==================

# ============================================================
# CELL 20: STATISTICAL ANALYSIS AND OUTPUT GENERATION
# ============================================================

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# Create output directories
OUTPUT_TABLES = Path("outputs/tables")
OUTPUT_FIGURES = Path("outputs/figures")

OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
OUTPUT_FIGURES.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 1. Consolidate simultaneous analyst calls
# ------------------------------------------------------------

analysis_events = events.loc[
    events["event_trade_date"].notna()
].copy()

def classify_episode(series):
    types = set(series.dropna())

    if len(types) == 1:
        return list(types)[0]

    return "Mixed"

def combine_earnings_overlap(series):
    values = series.dropna()

    if len(values) == 0:
        return pd.NA

    return bool(values.any())

episodes = (
    analysis_events
    .groupby(["ticker", "event_trade_date"])
    .agg(
        event_type=("event_type", classify_episode),
        earnings_overlap=(
            "earnings_overlap", combine_earnings_overlap
        ),
        n_rating_calls=("event_id", "nunique"),
        n_brokers=("broker", "nunique"),
        AR_0=("AR_0", "mean"),
        CAR_m1_p1=("CAR_m1_p1", "mean"),
        CAR_0_p1=("CAR_0_p1", "mean")
    )
    .reset_index()
)

episodes["earnings_overlap"] = (
    episodes["earnings_overlap"].astype("boolean")
)

print("Original analyst calls:", len(analysis_events))
print("Unique market-reaction episodes:", len(episodes))
print(
    "Simultaneous calls consolidated:",
    len(analysis_events) - len(episodes)
)

display(episodes.head(10))


# ------------------------------------------------------------
# 2. Calculate descriptive statistics and 95% CIs
# ------------------------------------------------------------

def summarize_returns(data, group_name, metric):

    values = pd.to_numeric(
        data[metric], errors="coerce"
    ).dropna()

    n = len(values)

    if n == 0:
        return {
            "group": group_name,
            "n": 0,
            "mean": np.nan,
            "median": np.nan,
            "std": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan
        }

    mean = values.mean()
    median = values.median()
    std = values.std(ddof=1) if n > 1 else np.nan

    if n > 1:
        se = std / np.sqrt(n)
        critical_value = stats.t.ppf(
            0.975, df=n - 1
        )

        ci_lower = mean - critical_value * se
        ci_upper = mean + critical_value * se

    else:
        ci_lower = np.nan
        ci_upper = np.nan

    return {
        "group": group_name,
        "n": n,
        "mean": mean,
        "median": median,
        "std": std,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper
    }


# ------------------------------------------------------------
# 3. Upgrade versus downgrade comparison
# ------------------------------------------------------------

type_results = []

for event_type in ["Upgrade", "Downgrade", "Mixed"]:

    subset = episodes.loc[
        episodes.event_type == event_type
    ]

    for metric in ["AR_0", "CAR_m1_p1", "CAR_0_p1"]:

        result = summarize_returns(
            subset,
            event_type,
            metric
        )

        result["metric"] = metric
        type_results.append(result)

type_summary = pd.DataFrame(type_results)

type_summary.to_csv(
    OUTPUT_TABLES / "upgrade_downgrade_summary.csv",
    index=False
)

print("\nUPGRADE VS DOWNGRADE RESULTS")

display(
    type_summary.pivot(
        index="group",
        columns="metric",
        values=["n", "mean", "ci_lower", "ci_upper"]
    )
)


# ------------------------------------------------------------
# 4. Earnings versus non-earnings comparison
# ------------------------------------------------------------

earnings_results = []

for overlap in [False, True]:

    subset = episodes.loc[
        episodes.earnings_overlap == overlap
    ]

    label = (
        "Earnings overlap"
        if overlap
        else "No earnings overlap"
    )

    for metric in ["AR_0", "CAR_m1_p1", "CAR_0_p1"]:

        result = summarize_returns(
            subset,
            label,
            metric
        )

        result["metric"] = metric
        earnings_results.append(result)

earnings_summary = pd.DataFrame(earnings_results)

earnings_summary.to_csv(
    OUTPUT_TABLES / "earnings_comparison.csv",
    index=False
)

print("\nEARNINGS COMPARISON")

display(
    earnings_summary.pivot(
        index="group",
        columns="metric",
        values=["n", "mean", "ci_lower", "ci_upper"]
    )
)



# ------------------------------------------------------------
# 5. Event-study plot: average abnormal returns
# ------------------------------------------------------------

# Consolidate simultaneous calls so each ticker/date/day
# contributes only one market-reaction observation.

episode_types = episodes[
    ["ticker", "event_trade_date", "event_type"]
].drop_duplicates()

plot_data = event_day_panel.drop_duplicates(
    subset=[
        "ticker",
        "event_trade_date",
        "relative_day"
    ]
).copy()

# Remove the original event_type before merging the
# consolidated episode classification.
plot_data = plot_data.drop(
    columns=["event_type"],
    errors="ignore"
)

plot_data = plot_data.merge(
    episode_types,
    on=["ticker", "event_trade_date"],
    how="left",
    validate="many_to_one"
)

plot_data = plot_data.dropna(
    subset=["abnormal_return", "event_type"]
)

plot_results = []

fig, ax = plt.subplots(figsize=(10, 6))

for event_type in ["Upgrade", "Downgrade", "Mixed"]:

    subset = plot_data.loc[
        plot_data["event_type"] == event_type
    ]

    if subset.empty:
        continue

    grouped = subset.groupby("relative_day")[
        "abnormal_return"
    ]

    stats_frame = grouped.agg(
        ["mean", "count", "std"]
    ).reset_index()

    stats_frame["se"] = (
        stats_frame["std"] /
        np.sqrt(stats_frame["count"])
    )

    stats_frame["critical"] = stats_frame["count"].apply(
        lambda n: stats.t.ppf(
            0.975, n - 1
        ) if n > 1 else np.nan
    )

    stats_frame["ci_lower"] = (
        stats_frame["mean"] -
        stats_frame["critical"] * stats_frame["se"]
    )

    stats_frame["ci_upper"] = (
        stats_frame["mean"] +
        stats_frame["critical"] * stats_frame["se"]
    )

    stats_frame["event_type"] = event_type

    plot_results.append(stats_frame)

    ax.errorbar(
        stats_frame["relative_day"],
        stats_frame["mean"] * 100,
        yerr=(
            stats_frame["ci_upper"] -
            stats_frame["mean"]
        ) * 100,
        marker="o",
        capsize=3,
        linewidth=2,
        label=event_type
    )

ax.axhline(0, linestyle="--", linewidth=1)
ax.axvline(0, linestyle=":", linewidth=1)

ax.set_title(
    "Market Reaction Around Analyst Rating Changes"
)

ax.set_xlabel("Trading Days Relative to Rating Change")
ax.set_ylabel("Average Abnormal Return (%)")

ax.set_xticks(range(-3, 4))
ax.legend()
ax.grid(alpha=0.25)

plt.tight_layout()

plt.savefig(
    OUTPUT_FIGURES / "event_study.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

event_study_results = pd.concat(
    plot_results,
    ignore_index=True
)

event_study_results.to_csv(
    OUTPUT_TABLES / "event_study_results.csv",
    index=False
)

print("Event-study chart successfully generated.")
display(event_study_results)


# ------------------------------------------------------------
# 6. Save consolidated event-level dataset
# ------------------------------------------------------------

episodes.to_csv(
    OUTPUT_TABLES / "event_reaction_episodes.csv",
    index=False
)


# ------------------------------------------------------------
# 7. Final output review
# ------------------------------------------------------------

print("\nANALYSIS COMPLETE")

print("\nGenerated files:")

for folder in [OUTPUT_TABLES, OUTPUT_FIGURES]:

    for file in sorted(folder.glob("*")):

        print(
            file,
            f"({file.stat().st_size:,} bytes)"
        )

print("\nFinal episode counts:")

display(
    episodes.groupby("event_type").agg(
        episodes=("ticker", "count"),
        analyst_calls=("n_rating_calls", "sum"),
        average_CAR=("CAR_m1_p1", "mean")
    )
)