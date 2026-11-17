"""Shared settings for the analyst-rating event study. Every script imports this file.

Run the whole pipeline from the repo root with `python run_all.py` (uses the committed raw
snapshot) or `python run_all.py --refresh` (re-downloads everything from Yahoo / Wikipedia).
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
PROC = ROOT / 'data' / 'processed'
TABLES = ROOT / 'outputs' / 'tables'
FIGS = ROOT / 'outputs' / 'figures'
RATINGS_DIR = RAW / 'ratings'      # one raw file per ticker, as downloaded
EARNINGS_DIR = RAW / 'earnings'    # one raw file per ticker, as downloaded
for d in [RAW, PROC, TABLES, FIGS, RATINGS_DIR, EARNINGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --refresh on the command line (python run_all.py --refresh) re-downloads; otherwise use the cache
REFRESH = '--refresh' in sys.argv

# ---- universe: 50 large firms chosen from 2020 membership and 2020 volume (survivors only) ----
UNIVERSE_ASOF = '2021-01-01'     # S&P 500 membership on this date
RANK_YEAR = 2020                 # rank members by average daily dollar volume in this year
N_FIRMS = 50
MKT = 'SPY'

# ---- sample window (fixed, so reruns do not drift) ----
SAMPLE_START = '2021-01-01'      # first rating change (Eastern date)
SAMPLE_END = '2026-10-09'        # last rating change; every event still has 20 trading days after it
PRICE_START = '2019-10-01'       # ~450 calendar days before SAMPLE_START, for the estimation window
PRICE_END = '2026-11-14'         # yfinance `end` is exclusive: last price day is Fri 2026-11-13

# ---- event-study design (same as the HW6 worked example) ----
EST_WINDOW = (-250, -30)         # estimation window, trading days relative to day 0
EVENT_WINDOW = (-20, 20)         # event window, trading days relative to day 0 (41 rows per event)
MIN_EST_DAYS = 150               # need at least this many estimation-window returns
MARKET_OPEN, MARKET_CLOSE = '09:30', '16:00'  # US/Eastern

# a rating change is "near earnings" if its day 0 is within these trading days of an earnings day 0
# (analysts typically re-rate in the day or two AFTER the report, so the window leans forward)
EARNINGS_WINDOW = (-1, 2)

# brokers with fewer calls than this (in one direction) are shown but not ranked; see 05_results.py
MIN_BROKER_CALLS = 10

WINDOWS = {'[-20,-2]': (-20, -2), '[-1,+1]': (-1, 1), '[+2,+20]': (2, 20)}


def firms():
    """The 50 tickers chosen by 00_universe.py, in rank order."""
    return pd.read_csv(RAW / 'universe.csv')['ticker'].tolist()


def find_day0(tdays, announce_date, timing, during='same_day'):
    """Position (in tdays) of the first trading day investors could trade on the news.

    before_open   -> that trading day (or the next one, if the date is a weekend/holiday)
    during_market -> that same trading day (the news is tradable before the close)
                     during='next_day' gives the teammates' prototype rule (sensitivity only)
    after_close   -> the next trading day
    Returns len(tdays) if day 0 is after the last price date.
    """
    if timing == 'after_close' or (timing == 'during_market' and during == 'next_day'):
        return tdays.searchsorted(announce_date, side='right')  # first trading day AFTER the date
    return tdays.searchsorted(announce_date, side='left')       # that day (or the next trading day)


def timing_label(et_times):
    """before_open / during_market / after_close from Eastern-time timestamps."""
    clock = et_times.dt.strftime('%H:%M')
    out = pd.Series('during_market', index=et_times.index)
    out[clock < MARKET_OPEN] = 'before_open'
    out[clock >= MARKET_CLOSE] = 'after_close'
    return out


def download_with_retry(fetch, label, errors, retries=3, wait=2.0):
    """Call fetch() up to 1 + retries times, waiting longer (x1.5) each time.

    An empty result counts as a failure. Failures go into the `errors` dict (never silent).
    """
    for attempt in range(retries + 1):
        try:
            out = fetch()
            if out is None or len(out) == 0:
                raise ValueError('empty result')
            return out
        except Exception as exc:
            if attempt == retries:
                errors[label] = f'{type(exc).__name__}: {exc}'
                return None
            print(f'  {label}: attempt {attempt + 1} failed ({type(exc).__name__}), retrying in {wait:.1f}s')
            time.sleep(wait)
            wait *= 1.5


def log_manifest(path, source, rows):
    """Record a downloaded raw file in data/raw/MANIFEST.csv (one row per file, latest pull wins)."""
    import yfinance as yf
    man_path = RAW / 'MANIFEST.csv'
    row = pd.DataFrame([{'file': Path(path).relative_to(ROOT).as_posix(), 'source': source,
                         'pulled_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                         'rows': rows, 'yfinance_version': yf.__version__}])
    if man_path.exists():
        man = pd.read_csv(man_path)
        man = man[man['file'] != row['file'].item()]
        row = pd.concat([man, row], ignore_index=True)
    row.sort_values('file').to_csv(man_path, index=False)


def load_broker_aliases():
    """raw Yahoo 'Firm' name -> one broker name (data/raw/broker_aliases.csv, built by inspection)."""
    al = pd.read_csv(RAW / 'broker_aliases.csv')
    assert al['raw_name'].is_unique, 'a raw broker name is mapped twice'
    return dict(zip(al['raw_name'], al['broker']))
