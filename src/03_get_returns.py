"""Step 3: daily returns for the 50 firms and the market (SPY), one batched download.

Prices: auto_adjust=True closes (splits and dividends), PRICE_START to PRICE_END (both fixed).
Output: data/raw/prices.csv (adjusted closes, as downloaded), data/processed/returns.csv
"""
import pandas as pd
import yfinance as yf
from _common import RAW, PROC, REFRESH, MKT, PRICE_START, PRICE_END, SAMPLE_END, firms, log_manifest

FIRMS = firms()
px_path = RAW / 'prices.csv'

if px_path.exists() and not REFRESH:
    print(f'{px_path.name} exists, skipping download')
else:
    px = yf.download(FIRMS + [MKT], start=PRICE_START, end=PRICE_END, auto_adjust=True, progress=False)['Close']
    px.index.name = 'date'
    # stop BEFORE writing if any ticker came back empty (failed download), so no bad file is cached
    failed = [t for t in FIRMS + [MKT] if t not in px.columns or px[t].notna().sum() == 0]
    if failed:
        raise SystemExit(f'ERROR: price download failed for {failed}; prices.csv not written. Rerun later.')
    px.to_csv(px_path)
    log_manifest(px_path, f'yfinance yf.download(50 firms + {MKT}, {PRICE_START} to {PRICE_END}, auto_adjust=True) Close', len(px))

px = pd.read_csv(px_path, index_col='date', parse_dates=True)
rets = px.pct_change(fill_method=None).iloc[1:]

# checks
assert rets.index.is_unique and rets.index.is_monotonic_increasing
assert set(FIRMS + [MKT]) <= set(rets.columns), 'a ticker is missing from the price download'
assert rets[MKT].notna().all(), 'SPY must have a return on every trading day'
assert rets.index.max() >= pd.Timestamp(SAMPLE_END) + pd.Timedelta(days=28), 'prices end too early'
print(rets.shape, rets.index.min().date(), rets.index.max().date())
print('missing returns per ticker (should be ~0):')
print(rets.isna().sum().sort_values(ascending=False).head())
print('biggest daily moves (do these look like real news days, or data errors?):')
print(rets.stack().abs().sort_values(ascending=False).head(5))

rets.to_csv(PROC / 'returns.csv', float_format='%.10g')
