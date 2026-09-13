"""Screen 05 — Trend Analysis.

Company search plus an up-to-3-metric selector overlays annual line
series with YoY % change annotations on every data point.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.utils.db import (
    METRIC_LABELS,
    get_companies,
    get_company_series,
)

st.set_page_config(page_title="Trend Analysis", layout="wide")

st.title("📈  Trend Analysis")

companies = get_companies()

search = st.text_input(
    "Search company",
    placeholder="Type a company name or ticker",
    label_visibility="collapsed",
)

if search.strip():
    needle = search.strip().lower()
    mask = companies["company_name"].str.lower().str.contains(
        needle, na=False
    ) | companies["id"].str.lower().str.contains(needle, na=False)
    candidates = companies[mask]
else:
    candidates = companies

if candidates.empty:
    st.warning("**Ticker not found — please try another.**")
    st.stop()

options = [f"{r.id} — {r.company_name}" for r in candidates.itertuples()]
choice = st.selectbox("Select company", options, label_visibility="collapsed")
ticker = choice.split(" — ")[0]

series = get_company_series(ticker)
if series.empty:
    st.info("No annual time-series data available for this company.")
    st.stop()

metrics = st.multiselect(
    "Metrics to overlay (max 3)",
    options=list(METRIC_LABELS),
    default=["sales"],
    format_func=lambda m: METRIC_LABELS[m],
    max_selections=3,
    help="Overlay up to three annual metrics with YoY % change labels.",
)

show_yoy = st.toggle("Show YoY % change on data points", value=True)

st.subheader(f"{ticker} — annual trends")

fig = go.Figure()
stored = []

for metric in metrics:
    if metric not in series.columns:
        continue
    values = pd.to_numeric(series[metric], errors="coerce")
    if values.notna().sum() == 0:
        continue
    fig.add_trace(
        go.Scatter(
            x=series["year_int"],
            y=values,
            name=METRIC_LABELS[metric],
            mode="lines+markers",
        )
    )
    stored.append((METRIC_LABELS[metric], values))

if not stored:
    st.info("None of the selected metrics have data for this company.")
    st.stop()

if show_yoy:
    for name, values in stored:
        pct_change = values.pct_change() * 100.0
        annotations = []
        for xv, yv, pc in zip(series["year_int"], values, pct_change):
            if pd.isna(yv) or pd.isna(pc):
                continue
            annotations.append(
                dict(
                    x=xv,
                    y=yv,
                    text=f"{pc:+.1f}%",
                    showarrow=False,
                    font=dict(size=9),
                    yshift=-16,
                    xshift=6,
                )
            )
        for ann in annotations:
            fig.add_annotation(ann)

fig.update_layout(
    height=460,
    margin=dict(t=20, b=10, l=10, r=10),
    xaxis=dict(title="Year"),
    yaxis=dict(title="Value"),
    legend=dict(orientation="h", y=1.12),
    hovermode="x unified",
)
st.plotly_chart(fig, width="stretch")

with st.expander("View raw annual data"):
    show_columns = ["year_int"] + [m for m in metrics if m in series.columns]
    st.dataframe(
        series[show_columns].rename(
            columns={
                "year_int": "Year",
                **{m: METRIC_LABELS[m] for m in metrics if m in series.columns},
            }
        ),
        width="stretch",
        hide_index=True,
    )
