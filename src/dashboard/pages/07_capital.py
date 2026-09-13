"""Screen 07 — Capital Allocation Map.

Treemap of all 92 companies grouped by the 8 capital-allocation
patterns.  Clicking a pattern shows the list of companies inside it.
A dropdown fallback is provided for keyboard accessibility.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.express as px
import streamlit as st

from src.dashboard.utils.db import get_capital_allocation, get_companies

st.set_page_config(page_title="Capital Allocation", layout="wide")

st.title("💰  Capital Allocation Map")

alloc = get_capital_allocation()
if alloc.empty:
    st.info("No capital allocation data found. Run the ratio engine first.")
    st.stop()

companies = get_companies()[["id", "company_name"]]
data = alloc.merge(companies, left_on="company_id", right_on="id", how="left")
data = data.drop(columns=["id", "company_id"]).rename(
    columns={"company_name": "company"}
)
data["pattern"] = data["pattern_label"]

st.markdown(
    "**Click a pattern group** (or a company tile) to see the companies "
    "inside it.  The dropdown below is a keyboard-friendly alternative."
)

fig = px.treemap(
    data,
    path=["pattern", "company"],
    color="pattern",
    custom_data=["company"],
    height=520,
)
fig.update_traces(
    hovertemplate="<b>%{label}</b><br>%{customdata[0]}<extra></extra>",
    texttemplate="%{label}",
)
fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))

selection = st.plotly_chart(
    fig, width="stretch", on_select="rerun", selection_mode="points"
)

pattern_set = set(data["pattern"].unique())
company_set = set(data["company"].unique())

clicked_pattern = None
clicked_company = None

try:
    points = (selection or {}).selection.points or []
    for point in points:
        custom = point.get("customdata") or []
        label = point.get("label")
        for item in custom:
            if item in pattern_set:
                clicked_pattern = item
            elif item in company_set:
                clicked_company = item
        if label in pattern_set:
            clicked_pattern = label
        elif label in company_set:
            clicked_company = label
except Exception:
    pass

patterns = sorted(data["pattern"].unique().tolist())
pattern_choice = st.selectbox(
    "Browse by pattern", ["-- choose a pattern --"] + patterns
)

st.subheader("Companies by capital allocation pattern")

chosen_pattern = None
if pattern_choice != "-- choose a pattern --":
    chosen_pattern = pattern_choice
elif clicked_pattern:
    chosen_pattern = clicked_pattern
elif clicked_company:
    chosen_pattern = data.loc[data["company"] == clicked_company, "pattern"].iloc[0]

if chosen_pattern:
    subset = data[data["pattern"] == chosen_pattern]
    st.write(f"**{chosen_pattern}** — {len(subset)} companies")
    st.dataframe(
        subset[["pattern", "company"]].rename(
            columns={"pattern": "Pattern", "company": "Company"}
        ),
        width="stretch",
        hide_index=True,
    )
else:
    st.caption(
        "Click a pattern on the treemap, or pick one from the dropdown, "
        "to list its companies."
    )
