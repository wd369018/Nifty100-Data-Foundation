"""Screen 01 — Home / Overview.

Shows 6 summary KPI tiles (year-selectable), a sector breakdown donut
chart, and the top-5 companies by composite quality score.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_all_market_cap, get_all_ratios, get_feature_frame

st.set_page_config(page_title="Home", layout="wide")

YEARS = [2019, 2020, 2021, 2022, 2023, 2024]


st.title("🏠  Home")


# ------------------------------------------------------------------
# Year selector in sidebar
# ------------------------------------------------------------------
sel_year = st.sidebar.selectbox("Data year", YEARS, index=len(YEARS) - 1)

# ------------------------------------------------------------------
# KPI tiles
# ------------------------------------------------------------------
ratios = get_all_ratios()
mc = get_all_market_cap()

ratios["year_int"] = ratios["year"].str[:4].astype(int)
yr_ratios = ratios[ratios["year_int"] == sel_year]
yr_mc = mc[mc["year"] == sel_year]

avg_roe = pd.to_numeric(yr_ratios["return_on_equity_pct"], errors="coerce").mean()
med_pe = yr_mc["pe_ratio"].median()
med_de = pd.to_numeric(yr_ratios["debt_to_equity"], errors="coerce").median()
total_cos = yr_ratios["company_id"].nunique()
med_rev_cagr = pd.to_numeric(yr_ratios["revenue_cagr_5yr"], errors="coerce").median()
debt_free = int((yr_ratios["icr_label"] == "Debt Free").sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Avg ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
c2.metric("Median P/E", f"{med_pe:.1f}" if pd.notna(med_pe) else "N/A")
c3.metric("Median D/E", f"{med_de:.2f}" if pd.notna(med_de) else "N/A")
c4.metric("Companies", total_cos)
c5.metric(
    "Median Rev CAGR 5y", f"{med_rev_cagr:.1f}%" if pd.notna(med_rev_cagr) else "N/A"
)
c6.metric("Debt-Free", debt_free)

st.divider()

# ------------------------------------------------------------------
# Sector breakdown donut
# ------------------------------------------------------------------
frame = get_feature_frame()
sector_counts = frame["broad_sector"].value_counts().reset_index()
sector_counts.columns = ["sector", "count"]

col_chart, col_table = st.columns([1, 1])

with col_chart:
    st.subheader("Sector breakdown")
    fig = px.pie(
        sector_counts,
        names="sector",
        values="count",
        hole=0.42,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    fig.update_traces(textinfo="percent+label", textposition="outside")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=380)
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------
# Top-5 by composite quality score
# ------------------------------------------------------------------
with col_table:
    st.subheader("Top 5 composite quality score")
    top5 = (
        frame.sort_values("composite_quality_score", ascending=False)
        .head(5)[
            ["company_id", "company_name", "broad_sector", "composite_quality_score"]
        ]
        .reset_index(drop=True)
    )
    st.dataframe(
        top5.rename(
            columns={
                "company_id": "Ticker",
                "company_name": "Name",
                "broad_sector": "Sector",
                "composite_quality_score": "Composite",
            }
        ),
        width="stretch",
        hide_index=True,
    )
