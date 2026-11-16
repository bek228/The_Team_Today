# Status memo (Checkpoint 1)

**What we picked and why.** We chose Seed 7: do analyst upgrades and downgrades move stock prices, and does the broker matter? We picked it because we hear about rating changes from the big banks all the time and wanted to know whether they are useful for our own investing, or whether the market has already priced them in by the time they are public. The data is free (Yahoo Finance through `yfinance`), and the method is the event study from HW6, so we could build on something we had already done.

**What the proof of concept got, and what broke.** Our first version covered five companies (AAPL, MSFT, AMZN, JPM, NVDA) from 2021 on: 138 upgrades and downgrades, grouped into 121 stock-day episodes. Measured against SPY over the three days around each call, upgrades averaged about +2.4% and downgrades about −1.7%. Several things broke or were missing. The script imported a notebook-only package, so it failed on a fresh machine. Every run downloaded the data again, so the numbers changed from run to run. Our earnings comparison averaged upgrades and downgrades together, which made it meaningless. And with only five companies, most brokers had one or two calls, so we could not say anything about whether the broker matters. The prototype is kept in `dev/`.

**Questions for Professor Bowen.**

1. Yahoo's rating history has holes for some companies (for example, no Meta records at all for 2025). Is disclosing the gaps enough, or should we drop those companies?
2. For "does the broker matter", we rank only brokers with at least 10 calls and our tests find no detectable difference between them. Is "we cannot tell brokers apart" an acceptable main finding, or should we look for a larger sample?
3. Our earnings flag covers one day before to two days after an earnings announcement. Is that the right width, or would you use something else?
