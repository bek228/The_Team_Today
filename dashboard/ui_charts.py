"""Matplotlib charts for the dashboard. One colour per direction, used everywhere."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

# colour-blind-safe pair: teal for upgrades, orange for downgrades
COLOR = {"upgrade": "#0f8b6f", "downgrade": "#d55e00"}
LABEL = {"upgrade": "Upgrades", "downgrade": "Downgrades"}
INK = "#1b2437"
MUTED = "#6b7280"
GRID = "#e5e7eb"
SHRUNK = "#14213d"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white", "legend.frameon": False,
})


def show(fig, width="stretch"):
    """Render in Streamlit, then close the figure so memory does not pile up."""
    st.pyplot(fig, width=width)
    plt.close(fig)


def car_path(df, title=None):
    """Mean CAR path by day with 95% bands. df: direction, t, n, mean_pct, ci_lo_pct, ci_hi_pct."""
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.axvspan(-1, 1, color=GRID, alpha=0.6, lw=0)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvline(0, color=MUTED, lw=0.8, ls=":")
    for d in ["upgrade", "downgrade"]:
        s = df[df["direction"] == d].sort_values("t")
        if s.empty:
            continue
        ax.fill_between(s["t"], s["ci_lo_pct"], s["ci_hi_pct"], color=COLOR[d], alpha=0.16, lw=0)
        ax.plot(s["t"], s["mean_pct"], color=COLOR[d], lw=2, label=f"{LABEL[d]} (n = {int(s['n'].iloc[0])})")
        last = s.iloc[-1]
        ax.annotate(LABEL[d], (last["t"], last["mean_pct"]), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    tmin, tmax = int(df["t"].min()), int(df["t"].max())
    ax.set_xlim(tmin, tmax + 4)
    ax.set_xticks(range(tmin, tmax + 1, 5))
    ax.set_xlabel("Trading days relative to the rating change (day 0)")
    ax.set_ylabel(f"Average CAR since day {tmin} (%)")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.legend(loc="upper left", fontsize=9)
    if title:
        ax.set_title(title, fontsize=10, loc="left")
    fig.tight_layout()
    show(fig)


def broker_dots(df, direction, ref_mean=None):
    """Ranked brokers: mean CAR[-1,+1] with 95% CI and the shrunk mean. Rank 1 at the top."""
    s = df.sort_values("rank", ascending=False)
    y = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(7.6, 0.27 * len(s) + 1.4))
    ax.axvline(0, color=MUTED, lw=0.8)
    if ref_mean is not None:
        ax.axvline(ref_mean, color=MUTED, lw=1, ls="--",
                   label=f"average of all calls in this sample: {ref_mean:+.2f}%")
    ax.errorbar(s["mean_pct"], y, xerr=[s["mean_pct"] - s["ci_lo_pct"], s["ci_hi_pct"] - s["mean_pct"]],
                fmt="o", color=COLOR[direction], ms=5, lw=1.2, capsize=2, label="broker mean, 95% CI")
    if "shrunk_mean_pct" in s:
        ax.plot(s["shrunk_mean_pct"], y, "D", color=SHRUNK, ms=4, label="shrunk mean (used for the order)")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{int(r)}. {b} (n = {n})" for r, b, n in zip(s["rank"], s["broker"], s["n"])],
                       fontsize=8)
    ax.set_ylim(-0.7, len(s) - 0.3)
    ax.set_xlabel("CAR[-1,+1] per rating change (%)")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.9 / (0.27 * len(s) + 1.4)), ncol=2, fontsize=8)
    fig.tight_layout()
    show(fig, width="content")   # natural size, so a long list does not get huge on wide screens


def histogram(df, col):
    """Histogram of a percent column, one colour per direction present."""
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    vals = df[col].dropna()
    lo, hi = np.nanpercentile(vals, [0.5, 99.5]) if len(vals) > 20 else (vals.min(), vals.max())
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    bins = np.linspace(lo, hi, 41)
    for d in ["upgrade", "downgrade"]:
        x = df.loc[df["direction"] == d, col].dropna().clip(lo, hi)
        if len(x):
            ax.hist(x, bins=bins, color=COLOR[d], alpha=0.55, label=f"{LABEL[d]} (n = {len(x)})",
                    edgecolor="white", linewidth=0.5)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_xlabel("CAR[-1,+1] (%)  (the outer 1% of values is pinned to the edges)")
    ax.set_ylabel("Number of rating changes")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.legend(fontsize=9)
    fig.tight_layout()
    show(fig, width="content")


def hour_bars(df, open_h=None, close_h=None):
    """Rating timestamps by hour of day (Eastern). Bars span each clock hour; dotted lines mark the open and close (decimal hours)."""
    fig, ax = plt.subplots(figsize=(7.6, 2.8))
    ax.bar(df["hour_et"] + 0.5, 100 * df["share"], color=SHRUNK, width=0.85)
    for h, lab in [(open_h, "open"), (close_h, "close")]:
        if h is not None:
            ax.axvline(h, color=MUTED, ls=":", lw=1)
            ax.annotate(lab, (h, 1), xycoords=("data", "axes fraction"), xytext=(3, -10),
                        textcoords="offset points", fontsize=8, color=MUTED)
    ticks = list(range(int(df["hour_et"].min()), int(df["hour_et"].max()) + 2))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{h}:00" for h in ticks], fontsize=8)
    ax.set_xlabel("Hour of the Yahoo timestamp (U.S. Eastern time)")
    ax.set_ylabel("Share of rating changes (%)")
    ax.grid(axis="y", color=GRID, lw=0.8)
    fig.tight_layout()
    show(fig)
