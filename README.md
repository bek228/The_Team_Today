# Analyst Rating Changes: Do Upgrades Move Stock Prices?

**[Launch the Live Interactive Dashboard](https://theteamtoday-8gqhfahmohefpa7weqnw9k.streamlit.app/)**

## 1. Project Overview

This project examines whether analyst rating upgrades and downgrades are associated with subsequent stock-price movements, and explores whether the broker issuing the recommendation matters.

The analysis uses historical analyst recommendations, adjusted daily stock prices, and earnings announcement dates to conduct an event study around analyst rating changes.

This repository contains the HW8 working prototype. The current analysis deliberately focuses on five companies; expanding the sample to 50 firms is reserved for the later final-project stage.

## 2. Research Sample

- **Companies:** Apple (AAPL), Microsoft (MSFT), Amazon (AMZN), JPMorgan Chase (JPM), and NVIDIA (NVDA).
- **Time period:** January 1, 2021 through the latest available data at the time of the run.
- **Market benchmark:** SPDR S&P 500 ETF (SPY).
- **Data source:** Yahoo Finance.

## 3. Methodology

### Analyst Rating Changes
Historical analyst rating records are collected and filtered to identify explicit upgrades and downgrades. Initiations and reiterations are excluded from the qualifying event sample.

### Event Timing
Yahoo Finance timestamps are converted from UTC to U.S. Eastern Time.

- Recommendations before 9:30 a.m. ET are assigned to that trading day, if the market is open.
- Recommendations at or after 9:30 a.m. ET are assigned to the next available trading session.
- Weekend and holiday events are assigned to the next available trading session.

This convention is intended to avoid attributing a full daily return to a recommendation that may have occurred after trading began. Vendor timestamps are not independently verified publication times.

### Earnings Announcements
Each analyst event is matched to the nearest reported earnings date for the same company. An event is flagged for earnings overlap when the announcement falls within one trading day before or after the assigned event date.

Missing earnings-date coverage is retained as missing rather than automatically classified as having no earnings overlap.

### Abnormal Returns and CAR
Market-adjusted abnormal returns are calculated as:

**Abnormal Return = Stock Daily Return − SPY Daily Return**

Cumulative abnormal returns (CAR) are calculated by summing abnormal returns over the relevant event window. The primary comparison uses CAR[-1,+1], covering the trading day before, the event day, and the trading day after the recommendation.

Simultaneous analyst recommendations for the same ticker and assigned trading date are consolidated into a single market-reaction episode for the episode-level analysis.

### Statistical Analysis
The project compares average abnormal returns across upgrades, downgrades, and mixed episodes. It also examines differences between events with and without nearby earnings announcements.

Descriptive statistics and 95% t-confidence intervals are calculated for the return measures.

## 4. Preliminary Results

The current exploratory analysis reports the following average CAR[-1,+1] estimates:

| Event Type | Episodes | Average CAR |
|---|---:|---:|
| Upgrades | 62 | +2.37% |
| Downgrades | 56 | -1.67% |
| Mixed | 2 | -3.29% |

The preliminary results show a positive average market-adjusted return around upgrades and a negative average around downgrades.

These findings are descriptive and should not be interpreted as evidence of causation. The mixed category contains only two episodes and is not suitable for strong conclusions.

## 5. Repository Structure

```text
The_Team_Today/
│
├── audits/                  # Project self-audit materials
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── data/
│   ├── raw/                 # Original downloaded datasets
│   └── processed/           # Cleaned event-level datasets
├── notebooks/
│   └── HW8_Data.ipynb       # Original analysis notebook
├── outputs/
│   ├── figures/             # Event-study visualizations
│   └── tables/              # Statistical results
├── src/
│   └── pipeline.py          # Reproducible analysis pipeline
├── run_all.py               # Main execution script
├── requirements.txt         # Python dependencies
└── README.md
```

## 6. Running the Project

Clone the repository:

```bash
git clone https://github.com/bek228/The_Team_Today.git
cd The_Team_Today
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the complete data collection and analysis pipeline:

```bash
python run_all.py
```

The pipeline downloads the required data, processes analyst events, calculates returns, and generates the statistical tables and event-study figure.

To launch the interactive dashboard locally:

```bash
streamlit run dashboard/app.py
```

The live dashboard is also available here:

https://theteamtoday-8gqhfahmohefpa7weqnw9k.streamlit.app/

## 7. Limitations

- **Limited sample:** The current analysis covers only five companies and should be treated as an initial prototype.
- **Timestamp accuracy:** Yahoo Finance timestamps are vendor-provided and are not independently verified as the exact time recommendations became public.
- **Daily price data:** Daily observations cannot isolate intraday price reactions.
- **Earnings coverage:** Historical earnings-date data may be incomplete for certain companies.
- **Overlapping events:** Multiple recommendations can occur close together, making it difficult to isolate the market reaction to an individual analyst.
- **Broker analysis:** The current sample is too small to draw strong conclusions about individual broker performance.
- **Statistical inference:** The reported confidence intervals are descriptive t-intervals and do not fully account for dependence across observations.

The project is intended to establish a reproducible research framework that can be expanded and refined in the final project.

## 8. Project Outputs

The repository includes:

- Raw analyst rating history.
- Adjusted daily stock and benchmark prices.
- Historical earnings announcement dates.
- Processed analyst event datasets.
- Event-day abnormal return panels.
- Upgrade and downgrade summary statistics.
- Earnings-overlap comparisons.
- Event-study visualizations.

