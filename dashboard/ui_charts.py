"""Plotly charts for the dashboard. One colour per direction, one shared look.

Every chart is a Plotly figure shown with st.plotly_chart. Plotly figures go to the browser as
JSON, so they do not depend on Streamlit's media endpoint (static image charts do, and that
endpoint fails on Streamlit Community Cloud). Do not add image-based charts to the dashboard.

Inputs: tables in percent unless a function says otherwise.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

# colour-blind-safe pair: teal for upgrades, orange for downgrades (matches .streamlit/config.toml)
COLOR = {"upgrade": "#0f8b6f", "downgrade": "#d55e00"}
BAND = {"upgrade": "rgba(15,139,111,0.16)", "downgrade": "rgba(213,94,0,0.16)"}
LABEL = {"upgrade": "Upgrades", "downgrade": "Downgrades"}
DIRS = ["upgrade", "downgrade"]
INK = "#1b2437"      # textColor in config.toml
MUTED = "#6b7280"
GRID = "#e5e7eb"
STRIP = "#f3f5f9"    # secondaryBackgroundColor in config.toml
NAVY = "#14213d"     # sidebar colour, used for neutral marks (shrunk means, time-of-day bars)
LIGHT = "#b8c0cc"    # de-emphasised marks
FONT = "'Source Sans', 'Source Sans Pro', 'Segoe UI', Arial, sans-serif"   # quoted names: an unquoted "Source Sans 3" is invalid CSS and the browser drops the whole list

pio.templates["fin331"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, size=13, color=INK),
    paper_bgcolor="white", plot_bgcolor="white",
    margin=dict(l=10, r=10, t=36, b=10),
    hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, size=12, color=INK)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
                font=dict(size=12)),
    xaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="outside",
               tickcolor=GRID, title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    yaxis=dict(showgrid=True, gridcolor=GRID, zeroline=False, linecolor=GRID, ticks="outside",
               tickcolor=GRID, title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    bargap=0.25, bargroupgap=0.08,
))
TEMPLATE = "fin331"
CONFIG = {"displayModeBar": False, "displaylogo": False, "scrollZoom": False}


def show(fig, key=None):
    """Render a figure full width with the clean config. theme=None keeps the shared template.

    Background and font are also set at the top level of the layout: the Streamlit frontend fills in
    its own plot background and font when they are only in the template."""
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", font=dict(family=FONT, size=13, color=INK))
    st.plotly_chart(fig, width="stretch", config=CONFIG, theme=None, key=key)


def _base(height):
    """Empty figure with the shared look. Titles go in st.markdown above the chart, not in the figure,
    so a legend that wraps on a narrow screen never runs into a title."""
    fig = go.Figure()
    fig.update_layout(template=TEMPLATE, height=height)
    return fig


def _zero(fig, axis="y"):
    if axis == "y":
        fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    else:
        fig.add_vline(x=0, line=dict(color=MUTED, width=1))


def _day0(fig):
    fig.add_vline(x=0, line=dict(color=MUTED, width=1, dash="dot"))


# ---------------------------------------------------------------- CAR paths
def _band_trace(s, color, name):
    return go.Scatter(x=list(s["t"]) + list(s["t"][::-1]), y=list(s["ci_hi_pct"]) + list(s["ci_lo_pct"][::-1]),
                      fill="toself", fillcolor=color, line=dict(width=0), hoverinfo="skip",
                      showlegend=False, name=name)


def _path_trace(s, d, name, dash="solid"):
    return go.Scatter(
        x=s["t"], y=s["mean_pct"], mode="lines", name=name, line=dict(color=COLOR[d], width=2.4, dash=dash),
        customdata=np.column_stack([s["ci_lo_pct"], s["ci_hi_pct"], s["n"]]),
        hovertemplate=("<b>" + name + "</b><br>day %{x}<br>mean CAR %{y:+.2f}%<br>"
                       "95% CI %{customdata[0]:+.2f}% to %{customdata[1]:+.2f}%<br>n = %{customdata[2]:,.0f}"
                       "<extra></extra>"))


def _path_axes(fig, tmin, tmax):
    fig.add_vrect(x0=-1, x1=1, fillcolor=STRIP, line_width=0, layer="below")
    _zero(fig)
    _day0(fig)
    fig.update_xaxes(title_text="Trading days relative to the rating change (day 0)", dtick=5,
                     range=[tmin - 0.5, tmax + 0.5])
    fig.update_yaxes(title_text=f"Average CAR since day {tmin} (%)", ticksuffix="%")
    fig.update_layout(hovermode="x unified")


def car_path(df, height=420):
    """Mean CAR path by day with 95% bands. df: direction, t, n, mean_pct, ci_lo_pct, ci_hi_pct."""
    fig = _base(height)
    for d in DIRS:
        s = df[df["direction"] == d].sort_values("t")
        if s.empty:
            continue
        fig.add_trace(_band_trace(s, BAND[d], LABEL[d]))
        fig.add_trace(_path_trace(s, d, f"{LABEL[d]} (n = {int(s['n'].iloc[0]):,})"))
    _path_axes(fig, int(df["t"].min()), int(df["t"].max()))
    return fig


def car_paths_compare(paths, height=420):
    """Several samples on one chart. paths: list of (label, dash, df). Bands only for the solid lines."""
    fig = _base(height)
    tmin, tmax = 0, 0
    for label, dash, df in paths:
        tmin, tmax = min(tmin, int(df["t"].min())), max(tmax, int(df["t"].max()))
        for d in DIRS:
            s = df[df["direction"] == d].sort_values("t")
            if s.empty:
                continue
            if dash == "solid":
                fig.add_trace(_band_trace(s, BAND[d], label))
            fig.add_trace(_path_trace(s, d, f"{LABEL[d]}, {label} (n = {int(s['n'].iloc[0]):,})", dash))
    _path_axes(fig, tmin, tmax)
    return fig


def ar_bars(df, height=420):
    """Average abnormal return per event day. df: direction, t, ar_pct, n."""
    fig = _base(height)
    for d in DIRS:
        s = df[df["direction"] == d].sort_values("t")
        if s.empty:
            continue
        fig.add_trace(go.Bar(
            x=s["t"], y=s["ar_pct"], name=LABEL[d], marker=dict(color=COLOR[d], cornerradius=3),
            customdata=s["n"],
            hovertemplate=f"<b>{LABEL[d]}</b><br>day %{{x}}<br>mean AR %{{y:+.3f}}%<br>n = %{{customdata:,}}"
                          "<extra></extra>"))
    _zero(fig)
    fig.update_xaxes(title_text="Trading days relative to the rating change (day 0)", dtick=1 if
                     df["t"].nunique() <= 15 else 5)
    fig.update_yaxes(title_text="Average abnormal return that day (%)", ticksuffix="%")
    fig.update_layout(barmode="group", hovermode="x unified")
    return fig


# ---------------------------------------------------------------- bars with intervals
def ci_bars(df, xcol, height=380, xtitle=None, ytitle="Mean CAR[-1,+1] (%)"):
    """Grouped bars with 95% CI error bars. df: direction, xcol, n, mean_pct, ci_lo_pct, ci_hi_pct, t_stat."""
    fig = _base(height)
    for d in DIRS:
        s = df[df["direction"] == d]
        if s.empty:
            continue
        fig.add_trace(go.Bar(
            x=s[xcol], y=s["mean_pct"], name=LABEL[d], marker=dict(color=COLOR[d], cornerradius=3),
            error_y=dict(type="data", symmetric=False, array=s["ci_hi_pct"] - s["mean_pct"],
                         arrayminus=s["mean_pct"] - s["ci_lo_pct"], color=INK, thickness=1.2, width=5),
            customdata=np.column_stack([s["ci_lo_pct"], s["ci_hi_pct"], s["n"], s["t_stat"]]),
            hovertemplate=(f"<b>{LABEL[d]}</b><br>%{{x}}<br>mean %{{y:+.2f}}%<br>95% CI %{{customdata[0]:+.2f}}% "
                           "to %{customdata[1]:+.2f}%<br>t = %{customdata[3]:.1f}, n = %{customdata[2]:,.0f}"
                           "<extra></extra>")))
    _zero(fig)
    fig.update_xaxes(title_text=xtitle, showgrid=False)
    fig.update_yaxes(title_text=ytitle, ticksuffix="%")
    fig.update_layout(barmode="group")
    return fig


def coef_plot(df, height=300):
    """Regression coefficients as dots with 95% intervals. df: label, coef, lo, hi, p_value."""
    s = df.iloc[::-1]
    fig = _base(height)
    fig.add_trace(go.Scatter(
        x=s["coef"], y=s["label"], mode="markers", marker=dict(color=NAVY, size=10), showlegend=False,
        error_x=dict(type="data", symmetric=False, array=s["hi"] - s["coef"], arrayminus=s["coef"] - s["lo"],
                     color=NAVY, thickness=1.6, width=6),
        customdata=np.column_stack([s["lo"], s["hi"], s["p_value"]]),
        hovertemplate=("<b>%{y}</b><br>coefficient %{x:+.2f} points<br>95% CI %{customdata[0]:+.2f} to "
                       "%{customdata[1]:+.2f}<br>p = %{customdata[2]:.3f}<extra></extra>")))
    _zero(fig, "x")
    fig.update_xaxes(title_text="Coefficient (percentage points of CAR[-1,+1])")
    fig.update_yaxes(showgrid=False)
    return fig


def forest(df, height=None):
    """Robustness forest plot. df: spec, direction, n, mean_pct, ci_lo_pct, ci_hi_pct, t_stat.

    One row per specification; upgrades and downgrades side by side in two panels."""
    specs = list(dict.fromkeys(df["spec"]))
    height = height or 90 + 34 * len(specs)
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=[LABEL[d] for d in DIRS])
    for i, d in enumerate(DIRS, start=1):
        s = df[df["direction"] == d]
        fig.add_trace(go.Scatter(
            x=s["mean_pct"], y=s["spec"], mode="markers", name=LABEL[d], marker=dict(color=COLOR[d], size=9),
            error_x=dict(type="data", symmetric=False, array=s["ci_hi_pct"] - s["mean_pct"],
                         arrayminus=s["mean_pct"] - s["ci_lo_pct"], color=COLOR[d], thickness=1.6, width=5),
            customdata=np.column_stack([s["ci_lo_pct"], s["ci_hi_pct"], s["n"], s["t_stat"]]),
            hovertemplate=(f"<b>{LABEL[d]}</b><br>%{{y}}<br>mean %{{x:+.2f}}%<br>95% CI %{{customdata[0]:+.2f}}% "
                           "to %{customdata[1]:+.2f}%<br>t = %{customdata[3]:.1f}, n = %{customdata[2]:,.0f}"
                           "<extra></extra>"), showlegend=False), row=1, col=i)
        fig.add_vline(x=0, line=dict(color=MUTED, width=1), row=1, col=i)
        fig.update_xaxes(title_text="CAR[-1,+1] (%)", ticksuffix="%", row=1, col=i)
    fig.update_yaxes(categoryorder="array", categoryarray=specs[::-1], showgrid=False)
    fig.update_layout(template=TEMPLATE, height=height)
    return fig


# ---------------------------------------------------------------- broker charts
def broker_dots(df, direction, ref_mean=None):
    """Ranked brokers: mean CAR[-1,+1] with 95% CI and the shrunk mean. Rank 1 at the top."""
    s = df.sort_values("rank")
    labels = [f"{int(r)}. {b} (n = {n})" for r, b, n in zip(s["rank"], s["broker"], s["n"])]
    fig = _base(110 + 24 * len(s))
    cd = np.column_stack([s["broker"], s["n"], s["ci_lo_pct"], s["ci_hi_pct"], s["shrunk_mean_pct"],
                          s["share_near_earnings_pct"], s["mean_pct"]])
    hover = ("<b>%{customdata[0]}</b><br>calls %{customdata[1]}<br>mean %{customdata[6]:+.2f}%<br>"
             "95% CI %{customdata[2]:+.2f}% to %{customdata[3]:+.2f}%<br>shrunk mean %{customdata[4]:+.2f}%<br>"
             "near earnings %{customdata[5]:.0f}% of calls<extra></extra>")
    fig.add_trace(go.Scatter(
        x=s["mean_pct"], y=labels, mode="markers", name="broker mean, 95% CI",
        marker=dict(color=COLOR[direction], size=9),
        error_x=dict(type="data", symmetric=False, array=s["ci_hi_pct"] - s["mean_pct"],
                     arrayminus=s["mean_pct"] - s["ci_lo_pct"], color=COLOR[direction], thickness=1.4, width=4),
        customdata=cd, hovertemplate=hover))
    fig.add_trace(go.Scatter(x=s["shrunk_mean_pct"], y=labels, mode="markers",
                             name="shrunk mean (used for the order)",
                             marker=dict(color=NAVY, size=8, symbol="diamond"), customdata=cd, hovertemplate=hover))
    _zero(fig, "x")
    if ref_mean is not None:
        fig.add_vline(x=ref_mean, line=dict(color=MUTED, width=1.4, dash="dash"),
                      annotation_text=f"average of all calls: {ref_mean:+.2f}%", annotation_position="top",
                      annotation_font=dict(size=11, color=MUTED))
    fig.update_yaxes(categoryorder="array", categoryarray=labels[::-1], showgrid=False, tickfont=dict(size=12))
    fig.update_xaxes(title_text="CAR[-1,+1] per rating change (%)", ticksuffix="%", side="bottom")
    fig.update_layout(margin=dict(t=60))
    return fig


def broker_noise(df, direction, min_calls, ref_mean=None, sd_pct=None):
    """Each broker's mean CAR[-1,+1] against its number of calls (linear axes). Ranked brokers in colour.

    sd_pct, if given, draws a rough noise band ref +- 1.96 sd / sqrt(n)."""
    fig = _base(440)
    for ranked, name, color, size in [(False, f"fewer than {min_calls} calls (not ranked)", LIGHT, 8),
                                      (True, f"ranked ({min_calls}+ calls)", COLOR[direction], 10)]:
        s = df[df["meets_min_n"] == ranked]
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s["n"], y=s["mean_pct"], mode="markers", name=name,
            marker=dict(color=color, size=size, line=dict(color="white", width=1)),
            customdata=np.column_stack([s["broker"]]),
            hovertemplate="<b>%{customdata[0]}</b><br>calls %{x}<br>mean %{y:+.2f}%<extra></extra>"))
    nmax = int(df["n"].max())
    if ref_mean is not None and sd_pct is not None:
        n = np.linspace(1, nmax + 2, 300)
        for sign in (1, -1):
            fig.add_trace(go.Scatter(x=n, y=ref_mean + sign * 1.96 * sd_pct / np.sqrt(n), mode="lines",
                                     line=dict(color=MUTED, width=1, dash="dot"), hoverinfo="skip",
                                     name="rough noise band", showlegend=sign == 1))
    _zero(fig)
    if ref_mean is not None:
        fig.add_hline(y=ref_mean, line=dict(color=MUTED, width=1.4, dash="dash"))
    fig.add_vline(x=min_calls, line=dict(color=INK, width=1, dash="dash"),
                  annotation_text=f"minimum to be ranked: {min_calls}", annotation_position="top right",
                  annotation_font=dict(size=11, color=MUTED))
    lo, hi = float(df["mean_pct"].min()), float(df["mean_pct"].max())
    pad = 0.15 * (hi - lo) + 0.5
    fig.update_xaxes(title_text="Number of calls by the broker in this sample", range=[0, nmax + 2])
    fig.update_yaxes(title_text="Broker's mean CAR[-1,+1] (%)", ticksuffix="%",
                     range=[min(lo, 0) - pad, max(hi, 0) + pad])
    return fig


def rank_scatter(df, direction):
    """Raw order vs standardized order. df: broker, n, rank_raw, rank_std."""
    fig = _base(440)
    m = int(max(df["rank_raw"].max(), df["rank_std"].max()))
    fig.add_trace(go.Scatter(x=[1, m], y=[1, m], mode="lines", line=dict(color=LIGHT, dash="dot"),
                             hoverinfo="skip", name="same order"))
    fig.add_trace(go.Scatter(
        x=df["rank_raw"], y=df["rank_std"], mode="markers", name="broker",
        marker=dict(color=COLOR[direction], size=10, line=dict(color="white", width=1)),
        customdata=np.column_stack([df["broker"], df["n"]]),
        hovertemplate=("<b>%{customdata[0]}</b><br>calls %{customdata[1]}<br>raw order %{x}<br>"
                       "scaled order %{y}<extra></extra>")))
    # reversed ranges so rank 1 sits at the top right
    fig.update_xaxes(title_text="Order by shrunk mean CAR (1 = top)", range=[m + 1, 0], dtick=5)
    fig.update_yaxes(title_text="Order by scaled CAR (1 = top)", range=[m + 1, 0], dtick=5)
    return fig


# ---------------------------------------------------------------- methodology charts
def timeline(est, event, windows, height=380):
    """Design timeline drawn with shapes.

    est: (start, end) of the estimation window; event: (start, end) of the event window;
    windows: list of (label, start, end) CAR windows inside the event window."""
    fig = make_subplots(rows=2, cols=1, vertical_spacing=0.22,
                        subplot_titles=["Full design (trading days relative to day 0)",
                                        "Close-up of the event window"])
    gap = (est[1] + 1, event[0] - 1)

    def box(row, x0, x1, y0, y1, color, text, line=None, font_color="white", inside=True):
        xref, yref = ("x", "y") if row == 1 else ("x2", "y2")
        fig.add_shape(type="rect", x0=x0 - 0.5, x1=x1 + 0.5, y0=y0, y1=y1, xref=xref, yref=yref,
                      fillcolor=color, line=line or dict(width=0), layer="below")
        # label inside a wide box, below a narrow one
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2 if inside else y0, xref=xref, yref=yref, text=text,
                           showarrow=False, yanchor="middle" if inside else "top",
                           font=dict(size=12, color=font_color if inside else INK))
        # invisible point so hover explains the box
        fig.add_trace(go.Scatter(x=[(x0 + x1) / 2], y=[(y0 + y1) / 2], mode="markers",
                                 marker=dict(size=30, opacity=0), showlegend=False,
                                 hovertemplate=f"{text}: days {x0} to {x1}<extra></extra>"), row=row, col=1)

    box(1, est[0], est[1], 0.3, 0.8, NAVY, f"Estimation window [{est[0]}, {est[1]}]")
    if gap[1] >= gap[0]:
        box(1, gap[0], gap[1], 0.3, 0.8, "white", f"gap [{gap[0]}, {gap[1]}]", line=dict(color=LIGHT, dash="dot"),
            inside=False)
    box(1, event[0], event[1], 0.3, 0.8, "#0b6b56", "Event", inside=(event[1] - event[0]) >= 30)
    colors = ["#7d8aa3", COLOR["upgrade"], "#7d8aa3"]
    fig.add_shape(type="rect", x0=event[0] - 0.5, x1=event[1] + 0.5, y0=0.72, y1=0.98, xref="x2", yref="y2",
                  fillcolor=STRIP, line=dict(width=0), layer="below")
    fig.add_annotation(x=event[0], y=0.85, xref="x2", yref="y2", text=f"Event window [{event[0]}, +{event[1]}]",
                       showarrow=False, xanchor="left", font=dict(size=12, color=INK))
    for i, (label, a, b) in enumerate(windows):
        box(2, a, b, 0.32, 0.6, colors[i % len(colors)], label, inside=(b - a) >= 8)
    for row in (1, 2):
        fig.add_vline(x=0, line=dict(color=INK, width=1.5, dash="dot"), row=row, col=1)
    fig.add_annotation(x=0, y=0.66, xref="x2", yref="y2", text="day 0", showarrow=False, xanchor="left",
                       xshift=4, font=dict(size=11, color=INK))
    fig.update_yaxes(visible=False, range=[0, 1.02], fixedrange=True)
    fig.update_xaxes(range=[est[0] - 5, event[1] + 5], row=1, col=1, dtick=50, showgrid=False)
    fig.update_xaxes(range=[event[0] - 1.5, event[1] + 1.5], row=2, col=1, dtick=5, showgrid=False)
    fig.update_xaxes(fixedrange=True)
    fig.update_annotations(selector=dict(text="Full design (trading days relative to day 0)"),
                           font=dict(size=13, color=MUTED))
    fig.update_annotations(selector=dict(text="Close-up of the event window"), font=dict(size=13, color=MUTED))
    fig.update_layout(template=TEMPLATE, height=height, margin=dict(t=30, b=10), hovermode="closest")
    return fig


def hour_bars(df, open_h=None, close_h=None, height=300):
    """Rating timestamps by hour of day (Eastern). Each bar spans one clock hour."""
    fig = _base(height)
    labels = [f"{h}:00 to {h}:59" for h in df["hour_et"]]
    fig.add_trace(go.Bar(x=df["hour_et"] + 0.5, y=100 * df["share"], width=0.85, marker=dict(color=NAVY,
                         cornerradius=3), customdata=np.column_stack([labels, df["n"]]), showlegend=False,
                         hovertemplate="%{customdata[0]} ET<br>%{y:.1f}% of rating changes "
                                       "(%{customdata[1]})<extra></extra>"))
    for h, lab in [(open_h, "open"), (close_h, "close")]:
        if h is not None:
            fig.add_vline(x=h, line=dict(color=COLOR["downgrade"], width=1.5, dash="dash"),
                          annotation_text=f"market {lab}", annotation_position="top right",
                          annotation_font=dict(size=11, color=MUTED))
    ticks = list(range(int(df["hour_et"].min()), int(df["hour_et"].max()) + 2))
    fig.update_xaxes(title_text="Hour of the Yahoo timestamp (U.S. Eastern time)", tickvals=ticks,
                     ticktext=[f"{h}:00" for h in ticks], showgrid=False)
    fig.update_yaxes(title_text="Share of rating changes (%)", ticksuffix="%")
    return fig


def funnel(steps, height=300, color=NAVY):
    """steps: list of (label, count)."""
    fig = _base(height)
    fig.add_trace(go.Funnel(y=[s[0] for s in steps], x=[s[1] for s in steps], textinfo="value+percent initial",
                            marker=dict(color=color), connector=dict(fillcolor=STRIP),
                            hovertemplate="%{y}<br>%{x:,}<extra></extra>"))
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(t=10))
    return fig


def coverage_heatmap(pivot, colorbar_title, start_year=None):
    """Firm x year counts. pivot: index = ticker (top row first), columns = year."""
    fig = _base(max(380, 16 * len(pivot) + 120))
    fig.add_trace(go.Heatmap(
        z=pivot.values, x=[str(c) for c in pivot.columns], y=list(pivot.index), xgap=1, ygap=1,
        colorscale=[[0, "#ffffff"], [0.001, "#e6f2ee"], [0.25, "#8cc7b6"], [1, "#0b5a48"]],
        colorbar=dict(title=dict(text=colorbar_title, side="right"), thickness=12),
        hovertemplate="%{y}, %{x}: %{z}<extra></extra>"))
    if start_year is not None and str(start_year) in [str(c) for c in pivot.columns]:
        fig.add_vline(x=list(map(str, pivot.columns)).index(str(start_year)) - 0.5,
                      line=dict(color=COLOR["downgrade"], width=2, dash="dash"),
                      annotation_text="sample starts", annotation_position="bottom right",
                      annotation_font=dict(size=11, color=MUTED))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=10), dtick=1)
    fig.update_xaxes(showgrid=False, side="top", title_text=None, type="category")
    fig.update_layout(plot_bgcolor="white")
    return fig


def yearly_counts(df, height=320):
    """Stacked bars of rating changes per year. df: year, direction, n."""
    fig = _base(height)
    for d in DIRS:
        s = df[df["direction"] == d]
        fig.add_trace(go.Bar(x=s["year"].astype(str), y=s["n"], name=LABEL[d], marker=dict(color=COLOR[d]),
                             hovertemplate=f"{LABEL[d]}, %{{x}}: %{{y:,}}<extra></extra>"))
    fig.update_layout(barmode="stack", hovermode="x unified", legend=dict(traceorder="normal"))
    fig.update_xaxes(title_text="Year of day 0", showgrid=False, type="category")
    fig.update_yaxes(title_text="Rating changes")
    return fig


# ---------------------------------------------------------------- explore charts
def histogram(df, col="car_pct"):
    """Overlaid histograms of a percent column, one colour per direction present."""
    fig = _base(360)
    vals = df[col].dropna()
    lo, hi = np.nanpercentile(vals, [0.5, 99.5]) if len(vals) > 20 else (vals.min(), vals.max())
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    size = (hi - lo) / 40
    for d in DIRS:
        x = df.loc[df["direction"] == d, col].dropna().clip(lo, hi)
        if len(x):
            fig.add_trace(go.Histogram(x=x, name=f"{LABEL[d]} (n = {len(x):,})", marker=dict(color=COLOR[d]),
                                       opacity=0.6, xbins=dict(start=lo, end=hi + size, size=size),
                                       hovertemplate="CAR %{x}<br>%{y} rating changes<extra></extra>"))
    _zero(fig, "x")
    fig.update_layout(barmode="overlay", bargap=0.03)
    fig.update_xaxes(title_text="CAR[-1,+1] (%). The outer 1% of values is pinned to the edges.", ticksuffix="%")
    fig.update_yaxes(title_text="Number of rating changes")
    return fig


def event_scatter(df):
    """Every rating change over time. df: day0, car_pct, direction, ticker, broker, from_grade, to_grade."""
    fig = _base(400)
    for d in DIRS:
        s = df[df["direction"] == d]
        if s.empty:
            continue
        fig.add_trace(go.Scattergl(
            x=s["day0"], y=s["car_pct"], mode="markers", name=f"{LABEL[d]} (n = {len(s):,})",
            marker=dict(color=COLOR[d], size=7, opacity=0.7, line=dict(color="white", width=0.5)),
            customdata=np.column_stack([s["ticker"], s["broker"], s["from_grade"].fillna(""),
                                        s["to_grade"].fillna(""), s["day0"].dt.strftime("%Y-%m-%d")]),
            hovertemplate=("<b>%{customdata[0]}</b>, %{customdata[4]}<br>%{customdata[1]}: %{customdata[2]} to "
                           "%{customdata[3]}<br>CAR[-1,+1] %{y:+.2f}%<extra></extra>")))
    _zero(fig)
    fig.update_xaxes(title_text="Day 0")
    fig.update_yaxes(title_text="CAR[-1,+1] (%)", ticksuffix="%")
    return fig


def group_bars(df, group_title):
    """Mean CAR[-1,+1] by group and direction. df: group, direction, n, mean_pct (only groups shown)."""
    groups = (df.groupby("group")["mean_pct"].apply(lambda x: x.abs().max()).sort_values().index.tolist())
    fig = _base(max(300, 70 + 22 * len(groups)))
    for d in DIRS:
        s = df[df["direction"] == d]
        if s.empty:
            continue
        fig.add_trace(go.Bar(
            y=s["group"], x=s["mean_pct"], orientation="h", name=LABEL[d],
            marker=dict(color=COLOR[d], cornerradius=3), customdata=s["n"],
            hovertemplate=f"<b>%{{y}}</b><br>{LABEL[d]}: mean %{{x:+.2f}}%<br>n = %{{customdata}}<extra></extra>"))
    _zero(fig, "x")
    fig.update_yaxes(categoryorder="array", categoryarray=groups, showgrid=False, title_text=group_title)
    fig.update_xaxes(title_text="Mean CAR[-1,+1] per rating change (%)", ticksuffix="%")
    fig.update_layout(barmode="group")
    return fig


def single_event(pan, direction):
    """One rating change: daily AR bars and the CAR line. pan: t, AR, CAR (decimals)."""
    pan = pan.sort_values("t")
    fig = _base(400)
    fig.add_vrect(x0=-1, x1=1, fillcolor=STRIP, line_width=0, layer="below")
    fig.add_trace(go.Bar(x=pan["t"], y=100 * pan["AR"], name="abnormal return that day",
                         marker=dict(color=LIGHT), hovertemplate="day %{x}<br>AR %{y:+.2f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=pan["t"], y=100 * pan["CAR"], mode="lines+markers",
                             name=f"cumulative abnormal return since day {int(pan['t'].min())}",
                             line=dict(color=COLOR.get(direction, NAVY), width=2.4), marker=dict(size=5),
                             hovertemplate="day %{x}<br>CAR %{y:+.2f}%<extra></extra>"))
    _zero(fig)
    _day0(fig)
    fig.update_xaxes(title_text="Trading days relative to day 0", dtick=5)
    fig.update_yaxes(title_text="Abnormal return (%)", ticksuffix="%")
    fig.update_layout(hovermode="x unified")
    return fig


def daily_ar_from_path(path):
    """Mean AR per day from a mean-CAR path: AR(t) = CAR(t) - CAR(t-1), AR(first day) = CAR(first day).

    This equals the mean daily AR only when the same events are in every day (n constant), so it
    returns None if n varies within a direction."""
    out = []
    for d, s in path.groupby("direction"):
        s = s.sort_values("t")
        if s["n"].nunique() != 1:
            return None
        ar = s["mean_pct"].diff()
        ar.iloc[0] = s["mean_pct"].iloc[0]
        out.append(pd.DataFrame({"direction": d, "t": s["t"], "n": s["n"], "ar_pct": ar}))
    return pd.concat(out, ignore_index=True) if out else None
