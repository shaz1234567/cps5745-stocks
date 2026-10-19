"""
CPS*5745 Interactive Stock Comparison Dashboard
Author: Shazab Ali
Stack: Dash + Plotly + yfinance + pandas
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from functools import lru_cache
from typing import Iterable

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Input, Output, dcc, html

# --- Tickers (liquid US large-caps) ---
# AAPL: consumer tech / iPhone ecosystem benchmark
# MSFT: enterprise software & cloud (Azure) peer
# GOOGL: digital advertising & search peer in Big Tech
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL"]
TICKER_LABELS = {
    "AAPL": "Apple (AAPL)",
    "MSFT": "Microsoft (MSFT)",
    "GOOGL": "Alphabet (GOOGL)",
    "AMZN": "Amazon (AMZN)",
    "NVDA": "NVIDIA (NVDA)",
    "META": "Meta (META)",
}
AVAILABLE_TICKERS = list(TICKER_LABELS.keys())

# Institutional blue/teal palette (Kean-inspired, stock-specific assignment)
TICKER_COLORS = {
    "AAPL": "#1E3A5F",
    "MSFT": "#4472C4",
    "GOOGL": "#2A9D8F",
    "AMZN": "#5B9BD5",
    "NVDA": "#70AD47",
    "META": "#ED7D31",
}

LAYOUT_BASE = dict(
    font=dict(family="Segoe UI, Helvetica Neue, Arial, sans-serif", size=12, color="#404040"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=55, r=28, t=48, b=42),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified",
)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="CPS*5745 Stock Comparison | Shazab Ali",
    suppress_callback_exceptions=True,
)
server = app.server


def _default_date_range() -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=365)
    return start, end


@lru_cache(maxsize=32)
def _download_history(tickers_key: str, start: str, end: str) -> pd.DataFrame:
    """Download OHLCV for comma-joined tickers; cache by args."""
    tickers = [t for t in tickers_key.split(",") if t]
    if not tickers:
        return pd.DataFrame()

    # yfinance end is exclusive for daily bars; bump by one day
    end_exclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end_exclusive,
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    if len(tickers) == 1:
        t = tickers[0]
        part = raw.copy()
        part["Ticker"] = t
        part = part.reset_index().rename(columns={"Date": "Date"})
        frames.append(part)
    else:
        for t in tickers:
            if t not in raw.columns.get_level_values(0):
                continue
            part = raw[t].copy()
            part["Ticker"] = t
            part = part.reset_index()
            frames.append(part)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.dropna(subset=["Close"]).sort_values(["Ticker", "Date"])
    return df


def load_filtered(tickers: Iterable[str], start: str, end: str) -> pd.DataFrame:
    cleaned = sorted({t.strip().upper() for t in tickers if t})
    if not cleaned or not start or not end:
        return pd.DataFrame()
    key = ",".join(cleaned)
    return _download_history(key, start, end).copy()


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["DailyReturn"] = out.groupby("Ticker")["Close"].pct_change()
    out["Indexed"] = out.groupby("Ticker")["Close"].transform(
        lambda s: (s / s.iloc[0]) * 100.0 if len(s) and s.iloc[0] else np.nan
    )
    out["CumulativeReturn"] = out.groupby("Ticker")["DailyReturn"].transform(
        lambda s: (1 + s.fillna(0)).cumprod() - 1
    )
    out["RollingVol20"] = out.groupby("Ticker")["DailyReturn"].transform(
        lambda s: s.rolling(20, min_periods=10).std() * np.sqrt(252) * 100
    )
    return out


def empty_fig(title: str, y_title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text=title, x=0.01, xanchor="left"),
        xaxis_title="Date",
        yaxis_title=y_title,
        annotations=[
            dict(
                text="Select companies and a date range to load charts",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(color="#808080", size=13),
            )
        ],
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E5E5E5", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#E5E5E5", zeroline=False)
    return fig


def style_fig(fig: go.Figure, title: str, y_title: str, y_tickformat: str | None = None) -> go.Figure:
    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=15, color="#1E3A5F")),
        xaxis_title="Date",
        yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#E5E5E5", zeroline=False)
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E5E5E5",
        zeroline=False,
        tickformat=y_tickformat,
    )
    return fig


def fig_indexed(df: pd.DataFrame) -> go.Figure:
    title = "Indexed Price (start of range = 100)"
    y = "Indexed price (start = 100)"
    if df.empty:
        return empty_fig(title, y)
    fig = go.Figure()
    for t, g in df.groupby("Ticker"):
        fig.add_trace(
            go.Scatter(
                x=g["Date"],
                y=g["Indexed"],
                mode="lines",
                name=t,
                line=dict(color=TICKER_COLORS.get(t, "#4472C4"), width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:.2f}<extra></extra>",
            )
        )
    return style_fig(fig, title, y, ".2f")


def fig_daily_returns(df: pd.DataFrame) -> go.Figure:
    title = "Daily Percentage Returns"
    y = "Daily return (%)"
    if df.empty:
        return empty_fig(title, y)
    fig = go.Figure()
    for t, g in df.groupby("Ticker"):
        fig.add_trace(
            go.Scatter(
                x=g["Date"],
                y=g["DailyReturn"] * 100.0,
                mode="lines",
                name=t,
                line=dict(color=TICKER_COLORS.get(t, "#4472C4"), width=1.4),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:.2f}%<extra></extra>",
            )
        )
    return style_fig(fig, title, y, ".2f")


def fig_cumulative(df: pd.DataFrame) -> go.Figure:
    title = "Cumulative Returns over Selected Range"
    y = "Cumulative return (%)"
    if df.empty:
        return empty_fig(title, y)
    fig = go.Figure()
    for t, g in df.groupby("Ticker"):
        fig.add_trace(
            go.Scatter(
                x=g["Date"],
                y=g["CumulativeReturn"] * 100.0,
                mode="lines",
                name=t,
                line=dict(color=TICKER_COLORS.get(t, "#4472C4"), width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:.2f}%<extra></extra>",
            )
        )
    return style_fig(fig, title, y, ".2f")


def fig_volume(df: pd.DataFrame) -> go.Figure:
    title = "Trading Volume"
    y = "Volume (shares)"
    if df.empty:
        return empty_fig(title, y)
    fig = go.Figure()
    for t, g in df.groupby("Ticker"):
        fig.add_trace(
            go.Bar(
                x=g["Date"],
                y=g["Volume"],
                name=t,
                marker=dict(color=TICKER_COLORS.get(t, "#4472C4"), opacity=0.75),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:,.0f} shares<extra></extra>",
            )
        )
    fig.update_layout(barmode="group")
    return style_fig(fig, title, y, ",.0s")


def fig_volatility(df: pd.DataFrame) -> go.Figure:
    title = "Rolling 20-Day Volatility (annualized)"
    y = "Annualized volatility (%)"
    if df.empty:
        return empty_fig(title, y)
    fig = go.Figure()
    for t, g in df.groupby("Ticker"):
        fig.add_trace(
            go.Scatter(
                x=g["Date"],
                y=g["RollingVol20"],
                mode="lines",
                name=t,
                line=dict(color=TICKER_COLORS.get(t, "#4472C4"), width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:.2f}%<extra></extra>",
            )
        )
    return style_fig(fig, title, y, ".2f")


def build_insight(df: pd.DataFrame, tickers: list[str], start: str, end: str) -> str:
    if df.empty or not tickers:
        return (
            "Select at least one company and a valid date range. Charts update together from the "
            "same filtered market data so comparisons stay aligned."
        )

    last_rows = df.sort_values("Date").groupby("Ticker").tail(1)
    cum = {
        row.Ticker: float(row.CumulativeReturn) * 100.0
        for _, row in last_rows.iterrows()
        if pd.notna(row.CumulativeReturn)
    }
    vol = (
        df.groupby("Ticker")["RollingVol20"]
        .apply(lambda s: float(s.dropna().iloc[-1]) if s.dropna().size else np.nan)
        .dropna()
        .to_dict()
    )
    avg_vol = (
        df.groupby("Ticker")["Volume"]
        .mean()
        .dropna()
        .to_dict()
    )

    if not cum:
        return "Data loaded, but returns could not be computed for the selected window."

    leader = max(cum, key=cum.get)
    laggard = min(cum, key=cum.get)
    most_vol = max(vol, key=vol.get) if vol else leader
    least_vol = min(vol, key=vol.get) if vol else laggard
    vol_leader = max(avg_vol, key=avg_vol.get) if avg_vol else leader

    ticker_why = {
        "AAPL": "Apple anchors consumer-electronics demand",
        "MSFT": "Microsoft reflects enterprise software and cloud spend",
        "GOOGL": "Alphabet tracks advertising and search cycles",
        "AMZN": "Amazon mixes retail and AWS cloud exposure",
        "NVDA": "NVIDIA is a high-beta AI hardware proxy",
        "META": "Meta concentrates social-ad platform risk",
    }
    why_bits = "; ".join(f"{t}: {ticker_why.get(t, 'liquid large-cap peer')}" for t in tickers)

    return (
        f"Over {start} to {end}, {leader} led on cumulative return ({cum[leader]:+.1f}%), "
        f"while {laggard} trailed ({cum[laggard]:+.1f}%). "
        f"Indexed prices (start = 100) make that gap easier to see than raw dollar prices. "
        f"On risk, {most_vol} shows the highest recent annualized 20-day volatility "
        f"({vol.get(most_vol, float('nan')):.1f}%), versus {least_vol} at "
        f"{vol.get(least_vol, float('nan')):.1f}%. "
        f"Average daily share volume is highest for {vol_leader} "
        f"({avg_vol.get(vol_leader, float('nan')):,.0f} shares), which often means tighter liquidity "
        f"for comparisons. Tickers chosen — {why_bits}."
    )


start_default, end_default = _default_date_range()

app.layout = html.Div(
    [
        html.Header(
            className="header-bar",
            children=[
                html.Div(
                    className="header-brand",
                    children=[
                        html.H1("Stock Comparison Dashboard", className="header-title"),
                        html.P(
                            "Interactive multi-company market view · latest available daily data",
                            className="header-subtitle",
                        ),
                    ],
                ),
                html.Div(
                    className="header-meta",
                    children=[
                        html.Strong("Shazab Ali"),
                        html.Span("Developed for CPS*5745"),
                    ],
                ),
            ],
        ),
        html.Div(
            className="page-shell",
            children=[
                html.Div(
                    className="filter-bar",
                    children=[
                        html.Div(
                            [
                                html.Label("Companies", className="filter-label"),
                                dcc.Dropdown(
                                    id="ticker-select",
                                    options=[
                                        {"label": TICKER_LABELS[t], "value": t}
                                        for t in AVAILABLE_TICKERS
                                    ],
                                    value=DEFAULT_TICKERS,
                                    multi=True,
                                    placeholder="Select companies…",
                                    clearable=False,
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Date range", className="filter-label"),
                                dcc.DatePickerRange(
                                    id="date-range",
                                    min_date_allowed=date(2015, 1, 1),
                                    max_date_allowed=date.today() + timedelta(days=1),
                                    start_date=start_default,
                                    end_date=end_default,
                                    display_format="YYYY-MM-DD",
                                    clearable=False,
                                ),
                            ]
                        ),
                        html.Div(
                            "Filters drive every chart below.",
                            className="filter-hint",
                        ),
                    ],
                ),
                html.P(id="status-line", className="status-line"),
                html.Div(
                    className="chart-grid",
                    children=[
                        html.Div(dcc.Graph(id="chart-indexed", config={"displayModeBar": False}), className="chart-panel wide"),
                        html.Div(dcc.Graph(id="chart-daily", config={"displayModeBar": False}), className="chart-panel"),
                        html.Div(dcc.Graph(id="chart-cumulative", config={"displayModeBar": False}), className="chart-panel"),
                        html.Div(dcc.Graph(id="chart-volume", config={"displayModeBar": False}), className="chart-panel"),
                        html.Div(dcc.Graph(id="chart-volatility", config={"displayModeBar": False}), className="chart-panel"),
                    ],
                ),
                html.Div(
                    className="insight-panel",
                    children=[
                        html.H2("Key differences revealed by the visualizations"),
                        html.P(id="insight-text"),
                    ],
                ),
                html.P(
                    "Data source: Yahoo Finance via yfinance · Prices auto-adjusted · Not investment advice",
                    className="footer-note",
                ),
            ],
        ),
    ]
)


@app.callback(
    Output("chart-indexed", "figure"),
    Output("chart-daily", "figure"),
    Output("chart-cumulative", "figure"),
    Output("chart-volume", "figure"),
    Output("chart-volatility", "figure"),
    Output("insight-text", "children"),
    Output("status-line", "children"),
    Input("ticker-select", "value"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
)
def update_all(tickers, start_date, end_date):
    tickers = tickers or []
    if isinstance(tickers, str):
        tickers = [tickers]

    if not tickers or not start_date or not end_date:
        empty = empty_fig("Select filters", "")
        msg = "Choose at least one company and a date range."
        return empty, empty, empty, empty, empty, msg, msg

    start = str(start_date)[:10]
    end = str(end_date)[:10]
    try:
        df = enrich(load_filtered(tickers, start, end))
    except Exception as exc:  # network / provider errors
        empty = empty_fig("Data unavailable", "")
        err = f"Could not load market data ({exc}). Try again shortly."
        return empty, empty, empty, empty, empty, err, err

    if df.empty:
        empty = empty_fig("No data for selection", "")
        msg = f"No rows returned for {', '.join(tickers)} between {start} and {end}."
        return empty, empty, empty, empty, empty, msg, msg

    n_days = df["Date"].nunique()
    status = (
        f"Showing {', '.join(tickers)} · {start} → {end} · "
        f"{n_days} trading days · last close date {df['Date'].max().date()}"
    )
    insight = build_insight(df, list(tickers), start, end)
    return (
        fig_indexed(df),
        fig_daily_returns(df),
        fig_cumulative(df),
        fig_volume(df),
        fig_volatility(df),
        insight,
        status,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8055"))
    app.run(host="0.0.0.0", port=port, debug=False)
