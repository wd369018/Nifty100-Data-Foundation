"""Screen 06 — Sector Analysis.

Pick a sector.  Bubble chart (x = Revenue, y = ROE, size = Market Cap,
colour = sub-sector) plus a sector-median KPI bar chart below it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_feature_frame

st.set_page_config(page_title="Sector Analysis", layout="wide")

st.title("🏭  Sector Analysis")

frame = get_feature_frame()

sectors = sorted(frame["broad_sector"].dropna().unique().tolist())
if not sectors:
    st.info("No sector data available.")
    st.stop()

sector = st.selectbox("Sector", sectors)

sector_frame = frame[frame["broad_sector"] == sector].copy()

st.subheader(f"{sector} — sub-sector bubble map")

bubble_cols = ["sales", "return_on_equity_pct", "market_cap_crore", "sub_sector"]
present = [c for c in bubble_cols if c in sector_frame.columns]
chart_frame = sector_frame.dropna(subset=["return_on_equity_pct", "sales"])

if chart_frame.empty:
    st.info("No ROE/Revenue data available for companies in this sector.")
else:
    fig = px.scatter(
        chart_frame,
        x="sales",
        y="return_on_equity_pct",
        size="market_cap_crore" if "market_cap_crore" in chart_frame.columns else None,
        color="sub_sector" if "sub_sector" in chart_frame.columns else None,
        hover_name="company_name",
        height=460,
        size_max=38,
    )
    if fig.data:
        fig.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br>Revenue: %{x:.0f} cr<br>"
                "ROE: %{y:.1f}%<br>Market Cap: %{marker.size:.0f} cr<extra></extra>"
            )
        )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend=dict(y=1.12))
    st.plotly_chart(fig, width="stretch")

st.subheader(f"{sector} — sector median KPIs")

median_metrics = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "debt_to_equity",
]
median_metrics = [m for m in median_metrics if m in sector_frame.columns]
labels = {
    "return_on_equity_pct": "ROE %",
    "return_on_capital_employed_pct": "ROCE %",
    "net_profit_margin_pct": "NPM %",
    "operating_profit_margin_pct": "OPM %",
    "revenue_cagr_5yr": "Rev CAGR 5y %",
    "pat_cagr_5yr": "PAT CAGR 5y %",
    "debt_to_equity": "D/E",
}

medians = {
    labels[m]: pd.to_numeric(sector_frame[m], errors="coerce").median()
    for m in median_metrics
}
median_df = pd.DataFrame(
    {"metric": list(medians), "value": list(medians.values())}
).dropna(subset=["value"])

if median_df.empty:
    st.info("No median KPI data available for this sector.")
else:
    fig = px.bar(
        median_df,
        x="metric",
        y="value",
        color="metric",
        text="value",
        height=360,
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")

st.caption(f"{len(sector_frame)} companies in {sector}.")
