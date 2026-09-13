"""Screen 02 — Company Profile.

Search a company by name or ticker, then see a profile card, 6 KPI
tiles, revenue/profit bar chart, ROE/ROCE dual-axis trend, and
pros/cons badges.
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
    get_companies,
    get_company_series,
    get_feature_frame,
    get_pl,
    get_prosandcons,
)

st.set_page_config(page_title="Company Profile", layout="wide")


def _fmt(value, suffix=""):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.2f}{suffix}"


st.title("👤  Company Profile")

companies = get_companies()
feature = get_feature_frame()

# ------------------------------------------------------------------
# Search + autocomplete
# ------------------------------------------------------------------
search = st.text_input(
    "Search company",
    placeholder="Type a company name or ticker (e.g. TCS, HDFC, Reliance)",
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

if len(candidates) == 0:
    st.warning("**Ticker not found — please try another.**")
    st.stop()

options = [f"{row['id']} — {row['company_name']}" for _, row in candidates.iterrows()]
choice = st.selectbox("Select company", options, label_visibility="collapsed")
ticker = choice.split(" — ")[0]

row = feature[feature["company_id"] == ticker]
if row.empty:
    st.warning("**Ticker not found — please try another.**")
    st.stop()
row = row.iloc[0]

company_meta = companies[companies["id"] == ticker]
about = company_meta["about_company"].iloc[0]
website = company_meta["website"].iloc[0]

# ------------------------------------------------------------------
# Company card
# ------------------------------------------------------------------
sector = row.get("broad_sector")
sub_sector = row.get("sub_sector")
st.subheader(row["company_name"])
st.caption(
    f"**Ticker:** {ticker}  |  **Sector:** {sector}  |  "
    f"**Sub-sector:** {sub_sector}"
)
st.write(
    about
    if about and str(about).strip().lower() not in ("null", "nan")
    else "*No company description available.*"
)
if website and str(website).strip().lower() not in ("null", "nan"):
    st.markdown(f"[Company website]({website})")

st.divider()

# ------------------------------------------------------------------
# 6 KPI tiles (latest screening year)
# ------------------------------------------------------------------
kpis = {
    "ROE": (row.get("return_on_equity_pct"), "%"),
    "ROCE": (row.get("return_on_capital_employed_pct"), "%"),
    "Net Profit Margin": (row.get("net_profit_margin_pct"), "%"),
    "D/E": (row.get("debt_to_equity"), ""),
    "Revenue CAGR 5y": (row.get("revenue_cagr_5yr"), "%"),
    "FCF (cr)": (row.get("free_cash_flow_cr"), ""),
}
cols = st.columns(6)
for col, (_, (value, suffix)) in zip(cols, kpis.items()):
    col.metric(_, _fmt(value, suffix))

st.divider()

# ------------------------------------------------------------------
# Revenue & Net Profit bar chart + ROE/ROCE dual-axis
# ------------------------------------------------------------------
pl = get_pl(ticker)
series = get_company_series(ticker)

c1, c2 = st.columns(2)

with c1:
    st.subheader("Revenue & Net Profit")
    if pl.empty:
        st.info("No P&L data available for this company.")
    else:
        years = pl["year"].str[:4]
        fig = go.Figure()
        fig.add_bar(x=years, y=pl["sales"], name="Revenue (cr)", marker_color="#1f77b4")
        fig.add_bar(
            x=years, y=pl["net_profit"], name="Net Profit (cr)", marker_color="#ff7f0e"
        )
        fig.update_layout(
            barmode="group",
            height=340,
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, width="stretch")

with c2:
    st.subheader("ROE & ROCE (10 years)")
    if series.empty or (
        series["return_on_equity_pct"].notna().sum() == 0
        and series["return_on_capital_employed_pct"].notna().sum() == 0
    ):
        st.info("No ROE/ROCE data available for this company.")
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=series["year_int"],
                y=series["return_on_equity_pct"],
                name="ROE %",
                mode="lines+markers",
                line=dict(color="#2ca02c", width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=series["year_int"],
                y=series["return_on_capital_employed_pct"],
                name="ROCE %",
                mode="lines+markers",
                yaxis="y2",
                line=dict(color="#d62728", width=2),
            )
        )
        fig.update_layout(
            height=340,
            margin=dict(t=10, b=10, l=10, r=10),
            yaxis=dict(title="ROE %"),
            yaxis2=dict(title="ROCE %", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------
# Pros / cons badges
# ------------------------------------------------------------------
st.divider()
st.subheader("Pros & Cons")

proscons = get_prosandcons(ticker)
pros = [
    str(p).strip()
    for p in proscons["pros"].dropna()
    if str(p).strip().lower() not in ("null", "nan")
]
cons = [
    str(c).strip()
    for c in proscons["cons"].dropna()
    if str(c).strip().lower() not in ("null", "nan")
]

if not pros and not cons:
    st.info("No pros/cons data available for this company.")
else:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**👍 Pros**")
        for item in pros:
            st.markdown(f"✅ {item}")
    with c2:
        st.markdown("**👎 Cons**")
        for item in cons:
            st.markdown(f"❌ {item}")
