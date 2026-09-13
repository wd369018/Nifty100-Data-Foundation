"""Screen 04 — Peer Comparison.

Pick a peer group and a company inside it.  Shows a radar chart of the
company's 8 metrics against the group average, plus a side-by-side KPI
table for every company in the group with the benchmark row
highlighted.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.peer import RADAR_KEYS, RADAR_LABELS
from src.dashboard.utils.db import get_feature_frame, get_peer_groups, get_peers

st.set_page_config(page_title="Peer Comparison", layout="wide")

st.title("🤝  Peer Comparison")

frame = get_feature_frame()
groups = get_peer_groups()

if not groups:
    st.info("No peer groups found.")
    st.stop()

group_name = st.selectbox("Peer group", groups)
members = get_peers(group_name)

if members.empty:
    st.info("No companies in this peer group.")
    st.stop()

ids = members["company_id"].tolist()
group_frame = frame[frame["company_id"].isin(ids)].copy()
group_frame = group_frame.sort_values("composite_quality_score", ascending=False)

# ------------------------------------------------------------------
# Normalise the 8 radar axes within the group (0-100, D/E inverted)
# ------------------------------------------------------------------
scores = {}
for col in RADAR_KEYS:
    s = group_frame[col].dropna()
    if len(s) < 2:
        scores[col] = pd.Series(50.0, index=group_frame.index)
        continue
    p10, p90 = s.quantile(0.10), s.quantile(0.90)
    if p10 == p90:
        scores[col] = pd.Series(50.0, index=group_frame.index)
        continue
    clipped = s.clip(p10, p90)
    normed = ((clipped - p10) / (p90 - p10)) * 100
    if col == "debt_to_equity":
        normed = 100 - normed
    full = pd.Series(np.nan, index=group_frame.index)
    full.loc[normed.index] = normed
    scores[col] = full

normed = pd.DataFrame(scores, index=group_frame.index)
normed.index = group_frame["company_id"].values
normed.index.name = "company_id"

company_options = group_frame["company_id"].tolist()
company_ticker = st.selectbox("Company", company_options)

if company_ticker not in normed.index:
    st.info("No metrics available for this company.")
    st.stop()

company_vals = normed.loc[company_ticker].fillna(0).values
avg_vals = normed.mean().values

c1, c2 = st.columns([1, 1])

# ------------------------------------------------------------------
# Radar chart
# ------------------------------------------------------------------
with c1:
    st.subheader(f"{company_ticker} vs {group_name} average")
    n = len(RADAR_LABELS)
    angles = list(range(n))
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=list(company_vals),
            theta=RADAR_LABELS,
            fill="toself",
            name=company_ticker,
            line=dict(color="#1f77b4", width=2),
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=list(avg_vals),
            theta=RADAR_LABELS,
            fill="none",
            name=f"{group_name} avg",
            line=dict(color="#ff7f0e", width=2, dash="dash"),
        )
    )
    fig.update_layout(
        height=420,
        margin=dict(t=10, b=10, l=10, r=10),
        polar=dict(radialaxis=dict(range=[0, 100], tickvals=[0, 50, 100])),
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------
# Side-by-side KPI table (benchmark row highlighted)
# ------------------------------------------------------------------
with c2:
    st.subheader("Peer group: key metrics")
    kpi_cols = [
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "composite_quality_score",
    ]
    kpi_names = {
        "return_on_equity_pct": "ROE %",
        "return_on_capital_employed_pct": "ROCE %",
        "net_profit_margin_pct": "NPM %",
        "debt_to_equity": "D/E",
        "free_cash_flow_cr": "FCF (cr)",
        "revenue_cagr_5yr": "Rev CAGR 5y %",
        "pat_cagr_5yr": "PAT CAGR 5y %",
        "composite_quality_score": "Composite",
    }

    table = group_frame[["company_id", "company_name"] + kpi_cols].copy()
    table["Benchmark"] = (
        table["company_id"]
        .isin(members.loc[members["is_benchmark"], "company_id"])
        .map({True: "✅", False: ""})
    )
    table = table.rename(
        columns={
            "company_id": "Ticker",
            "company_name": "Name",
            **kpi_names,
        }
    )
    styled = table.style.apply(
        lambda r: (
            ["background-color: #fff3a3"] * len(r)
            if r["Benchmark"] == "✅"
            else [""] * len(r)
        ),
        axis=1,
    )
    st.dataframe(styled, width="stretch", hide_index=True)
    st.caption("Grey-highlighted rows are the group benchmark companies.")

st.divider()
st.caption(
    f"Data from `peer_groups` (Sprint 3) — {len(group_frame)} companies "
    f"in **{group_name}**."
)
