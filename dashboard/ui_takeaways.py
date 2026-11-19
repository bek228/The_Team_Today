"""Plain-language "Show takeaway" boxes for a reader without a finance background.

All box wording lives in TEXT below, so it can be edited in one place. The {names} in braces are
filled in by the page with numbers it reads from the committed tables, so no number is typed here.
Each box is a collapsed st.expander, so the page looks the same until the reader opens it.
"""
import streamlit as st

LABEL = "Show takeaway: what this means"

TEXT = {
    # ---- Introduction
    "intro": (
        "**In plain words.** When an analyst upgrades one of these stocks, the stock beats the market by "
        "about {up} on average over three days (the day before, the day of and the day after the call). After "
        "a downgrade it trails the market by about {dn}. That move beyond the market is the *abnormal return*; "
        "added up over the three days it is the *CAR[-1,+1]* shown in the chart. These numbers use the *clean "
        "sample*: calls with no earnings report and no other analyst call on the stock nearby, so the move is "
        "not someone else's news.\n\n"
        "**How sure are we?** The averages stay far from zero even with a stricter way of measuring the "
        "uncertainty (t = {t_up} and {t_dn}; a t-stat beyond about 2 means the average is unlikely to be luck). "
        "**Caveats:** this shows that prices move around the call, not that the analyst caused the move, and "
        "the tests cannot tell the brokers apart."
    ),
    # ---- Methodology
    "method": (
        "**In plain words.** To see whether a call moved a stock, we first estimate how the stock normally "
        "moves with the market ({mkt}), using trading days {est0} to {est1} before the call, well before any "
        "news about it. The *abnormal return* is what the stock actually did minus that normal move. Adding "
        "the abnormal returns over a few days gives the *CAR*. The headline window is days -1 to +1 around "
        "day 0, the first day an investor could trade on the call."
    ),
    "method_timing": (
        "**Why this matters.** If day 0 were put on the wrong day, the price reaction would fall outside the "
        "window we measure. {before} of calls are stamped before the open, so day 0 is usually the same day "
        "as the call. **Caveat:** Yahoo's clock times come without a time zone. Reading them as UTC is our "
        "assumption, not a checked fact. Reading them as Eastern instead moves day 0 for {moves} of {n_calls} "
        "rating changes, and the clean result barely changes ({up_e} for upgrades, {dn_e} for downgrades)."
    ),
    "method_samples": (
        "**Why there are several samples.** Analysts often change a rating right after an earnings report, "
        "and then most of the price move is the earnings news, not the analyst. The *clean* sample drops "
        "calls within {ew} trading days of an earnings report, calls with another rating change on the same "
        "stock within 2 trading days, and mixed days. That leaves {n_clean:,} of {n_ep:,} episodes. "
        "**Caveat:** these rules look one or two days past day 0, so the clean sample is a measuring tool, "
        "not a filter an investor could have used on the day."
    ),
    # ---- Results
    "results": (
        "**What you are looking at** (sample: {label}). The lines show how far, on average, the stock moved "
        "beyond the market in the days around the call. Over days -1 to +1, upgrades averaged {up} "
        "(t = {t_up}, {n_up} episodes) and downgrades {dn} (t = {t_dn}, {n_dn} episodes). After the call "
        "(CAR[+2,+20]) upgrades average {post_up} (t = {tp_up}) and downgrades {post_dn} (t = {tp_dn}): "
        "{drift}{extra}"
    ),
    "results_earnings": (
        "**In plain words.** Calls made within {ew} trading days of an earnings report come with much bigger "
        "moves: {up_near} for upgrades and {dn_near} for downgrades, against {up_no} and {dn_no} when no report "
        "is nearby. Most of that gap is the earnings news itself, not the analyst, which is why the headline "
        "leaves these calls out. The regression below asks both questions at once (is it an upgrade? is "
        "earnings nearby?) and gives each its own estimate."
    ),
    "results_robust": (
        "**In plain words.** Each row redoes the headline with one choice changed: a different market "
        "benchmark, a different day-0 rule, a different sample or a different way to measure the uncertainty. "
        "If the dots stay on the same side of zero, the result does not hinge on that choice. {sign_text} "
        "With the strictest error measure (clustered by stock and by day) the clean t-stats are {t_up} and "
        "{t_dn}. **Caveat:** the row that keeps only episodes with no other rating change in the estimation "
        "window has just {n_small} episodes, so it is much noisier."
    ),
    # ---- Broker leaderboard
    "brokers": (
        "**In plain words.** This page asks whether some brokers' {direction}s move prices more than "
        "others'. For {direction}s in this sample ({label}), the tests give {p_anova} (ANOVA) and {p_perm} "
        "(permutation). A p-value is the chance of seeing differences at least this large if all brokers were really "
        "the same; {p_meaning} Most brokers make only a few calls (median {median} per broker and direction), "
        "so one broker's average is very noisy. {caveat}"
    ),
    "brokers_rank": (
        "**About the diamonds and the third test.** A broker with few calls can look great or awful by luck, "
        "so the *shrunk mean* pulls each average toward the overall average, more strongly when a broker has "
        "fewer calls. Only brokers with at least {min_calls} calls in a direction are ranked, which keeps the "
        "noisiest averages off the list. Kruskal-Wallis compares the whole spread of returns, not only the "
        "average, so it can flag differences even when averages are alike. A plausible reason is that brokers "
        "cover stocks of different volatility or call at different times; that explanation was not tested."
    ),
    # ---- Explore
    "explore": (
        "**What this page is for.** It lets you slice the individual rating changes yourself. Each call "
        "counts once here, so with no filters upgrades average {up} and downgrades {dn} over days -1 to +1. "
        "That is larger than the headline because calls near earnings and days when several brokers moved "
        "the same stock are included. Small groups are noisy: below {min_n} calls the page shows no t-stat, "
        "and one big move can swing the average. A striking number for one company or broker is a reason "
        "to look closer, not a finding."
    ),
}

# Pieces of the Results box that depend on the page's controls or on the numbers.
DRIFT = {
    True: "neither is clearly different from zero, so there is no clear further drift after the call.",
    False: "at least one is clearly different from zero. For the before and after windows the fair check is "
           "the clean-window sample, which has no earnings report anywhere in the event window.",
}
SAMPLE_NOTE = {
    "all": " This sample includes calls near earnings reports, which come with much bigger moves.",
    "near_earnings": " These calls come right around an earnings report, so much of the move is the "
                     "earnings news itself, not the analyst.",
    "clean_window": " This sample has no earnings report anywhere in the window, so it is the fair check "
                    "for the before and after windows, but it has fewer episodes.",
}

# Pieces of the Broker leaderboard box, keyed by the wording of mean_test_verdict() in ui_pages.py.
BROKER_VERDICT = {
    "cannot reliably tell the brokers apart": (
        "here both are above 0.10, so the differences between brokers look like what luck alone would produce.",
        "*Cannot tell brokers apart* means there is not enough data to see a difference, not proof that all "
        "brokers are equal."),
    "give only weak evidence that average reactions differ across brokers": (
        "here they fall around 0.05 to 0.10, which is weak evidence at best.",
        "So any one broker's place in the order is uncertain."),
    "find that average reactions do differ across brokers": (
        "here both are below 0.05, so the averages likely do differ across brokers.",
        "Even so, any one broker's place in the order is uncertain."),
}


def show(key, **values):
    """A collapsed 'Show takeaway' box with the text TEXT[key], filled in with the page's numbers."""
    with st.expander(LABEL):
        st.markdown(TEXT[key].format(**values))
