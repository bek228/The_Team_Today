# Research Proposal: Do Analyst Rating Changes Move Stock Prices?

### The Team Today

**Benjamin Katz, Landon Krane, Jason Thomas, and Benjamin Moldovsky**

## Research Question

We became interested in this topic because we wanted to see whether analyst recommendations could actually be useful in our own investing. Investors regularly hear about upgrades and downgrades from major banks, but it is not always clear how much these recommendations matter or whether there is an opportunity to act on them.

Our general question is:

**Can investors use analyst rating changes to make better investment decisions?**

Some questions we specifically would like to answer include:

- Do stocks typically increase in price following an analyst upgrade and decrease following a downgrade?
- How quickly does the market react to these recommendations?
- Does the brokerage firm issuing the recommendation matter? For example, do upgrades from Goldman Sachs or Morgan Stanley have a different impact than recommendations from smaller firms?
- Are some analysts or brokerage firms more accurate than others?
- Is there an opportunity for an individual investor to benefit from following analyst recommendations, or has the market already priced in the information by the time the recommendation becomes public?
- Do recommendations have different effects when they occur around earnings announcements?

Our goal is to determine whether analyst recommendations contain information that could actually be useful when making investment decisions, rather than simply looking at whether stocks move after an upgrade or downgrade.

## Needed Data

### What will our final dataset look like?

Our current prototype uses five companies: AAPL, MSFT, AMZN, JPM, and NVDA. For the final project, we would like to expand this to approximately 50 companies.

We will use SPY as our market benchmark so that we can distinguish movements in individual stocks from broader market movements.

Our main dataset will consist of individual analyst rating changes. Each observation will include:

- Company ticker
- Analyst and brokerage firm
- Previous and new recommendation
- Whether the recommendation was an upgrade or downgrade
- Date and time of the recommendation
- Stock returns around the recommendation
- Abnormal returns compared with SPY
- Whether the recommendation occurred near an earnings announcement

### What is the observation?

Our primary observation is an individual analyst rating change for a particular company.

We will also consolidate recommendations for the same company that occur on the same trading date into one event episode when measuring the market reaction. This will prevent us from treating several recommendations issued on the same day as completely separate stock-price reactions.

### What data do we have and what data do we need?

We currently have three raw datasets:

1. Historical analyst recommendations from Yahoo Finance.
2. Daily adjusted stock prices for our five companies and SPY.
3. Historical earnings announcement dates.

We will need to expand the number of companies and determine whether we can consistently collect brokerage and analyst information across the larger sample.

Brokerage information is especially important because we want to see whether certain firms' recommendations have a greater impact on stock prices.

## Resources

We currently use Yahoo Finance to collect analyst recommendations, daily stock prices, and earnings dates.

Our raw datasets are saved as CSV files in our GitHub repository. We also have Python scripts that process the data and generate the event-study results.

If Yahoo Finance does not provide enough historical information for our expanded sample, we will look into alternative sources for analyst recommendations and brokerage information.

## Process

We want to build a dataset that allows us to examine what happens to a stock after an analyst changes its rating.

Our process will be:

1. Collect historical analyst recommendations for our selected companies.
2. Download daily adjusted stock prices for each company and SPY.
3. Identify upgrades and downgrades and record the brokerage firm responsible.
4. Assign each recommendation to the appropriate trading date based on when it was released.
5. Calculate daily stock returns and compare them with SPY to measure abnormal returns.
6. Examine returns over several trading days surrounding each recommendation.
7. Identify recommendations that occurred near earnings announcements and compare those results separately.
8. Compare results across brokerage firms to see whether some firms' recommendations appear to have a stronger impact than others.

One issue we want to pay particular attention to is timing. If an analyst releases an upgrade after the market has opened, an investor may not have been able to act on it before that day's price movement. We therefore need to account for when recommendations become available rather than simply looking at the date.

We also want to distinguish between a stock moving after a recommendation and an investor actually being able to earn a return by following it. This will be an important part of determining whether the results have practical investment value.

## Outputs

We plan to present our results through an interactive dashboard.

The dashboard will have four main sections:

1. **Introduction:** Overview of the research question and companies included.
2. **Methodology:** Explanation of the data and how we calculate returns around analyst recommendations.
3. **Results:** Comparisons of upgrades and downgrades, including average abnormal returns and cumulative abnormal returns.
4. **Explore:** Ability to filter results by company, recommendation type, and brokerage firm.

We would also like to include:

- A comparison of average returns following upgrades and downgrades.
- A chart showing stock-price reactions over the trading days surrounding recommendations.
- A comparison of brokerage firms and their historical recommendations.
- An analysis of whether earnings announcements affect the results.
- An exploration of whether following certain analyst recommendations could produce an investment strategy.

Our current five-company prototype and dashboard provide a starting point. We hope to expand the sample and determine whether the patterns we observe are consistent across a larger group of companies.

**Live dashboard:** [The Team Today — Analyst Rating Event Study](https://theteamtoday-8gqhfahmohefpa7weqnw9k.streamlit.app/)
