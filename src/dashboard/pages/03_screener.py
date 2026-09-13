"""Screen 03 — Screener.

Ten metric sliders in the sidebar build a live filter on the feature
frame.  The six preset buttons auto-fill the sliders.  Results are
shown as a table with a CSV download button.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import get_feature_frame

st.set_page_config(page_title="Screener", layout="wide")

st.title("📊  Screener")

frame = get_feature_frame()

# ------------------------------------------------------------------
# Slider definitions (column, direction)
# ------------------------------------------------------------------
SLIDERS = [
    ("roe_min", "return_on_equity_pct", "min"),
    ("de_max", "debt_to_equity", "max"),
    ("fcf_min", "free_cash_flow_cr", "min"),
    ("rev_cagr_min", "revenue_cagr_5yr", "min"),
    ("pat_cagr_min", "pat_cagr_5yr", "min"),
    ("opm_min", "operating_profit_margin_pct", "min"),
    ("pe_max", "pe_ratio", "max"),
    ("pb_max", "pb_ratio", "max"),
    ("dy_min", "dividend_yield_pct", "min"),
    ("icr_min", "interest_coverage", "min"),
]

LABELS = {
    "roe_min": "ROE min (%)",
    "de_max": "D/E max",
    "fcf_min": "FCF min (cr)",
    "rev_cagr_min": "Revenue CAGR 5y min (%)",
    "pat_cagr_min": "PAT CAGR 5y min (%)",
    "opm_min": "Op Margin min (%)",
    "pe_max": "P/E max",
    "pb_max": "P/B max",
    "dy_min": "Dividend Yield min (%)",
    "icr_min": "Interest Coverage min",
}


# Default (no-op) slider values = permissive bounds of the data.
def _bounds(column, direction):
    vals = pd.to_numeric(frame[column], errors="coerce").dropna()
    if vals.empty:
        return (0.0, 1.0, 0.0)
    lo, hi = float(vals.min()), float(vals.max())
    if hi - lo < 1e-9:
        hi = lo + 1.0
    if direction == "min":
        default = lo
    else:
        default = hi
    return (lo, hi, default)


PRESETS = {
    "Quality": {"roe_min": 15.0, "de_max": 1.0, "fcf_min": 0.0, "rev_cagr_min": 10.0},
    "Value": {"pe_max": 20.0, "pb_max": 4.5, "de_max": 2.0, "dy_min": 1.0},
    "Growth": {"pat_cagr_min": 20.0, "rev_cagr_min": 15.0, "de_max": 2.0},
    "Dividend": {"dy_min": 2.0, "fcf_min": 0.0},
    "Debt-Free": {"de_max": 0.10},
    "Turnaround": {"rev_cagr_min": 10.0, "fcf_min": 0.0},
}

# ------------------------------------------------------------------
# Sidebar: presets + sliders
# ------------------------------------------------------------------
st.sidebar.subheader("Metric filters")

st.sidebar.markdown("**Presets**")
preset_cols = st.sidebar.columns(3)
for i, (name, values) in enumerate(PRESETS.items()):
    with preset_cols[i % 3]:
        if st.button(name, width="stretch", key=f"preset_{name}"):
            st.session_state.update(values)
            st.rerun()

st.sidebar.markdown("---")

bounds = {key: _bounds(column, direction) for key, column, direction in SLIDERS}

for key, column, direction in SLIDERS:
    lo, hi, default = bounds[key]
    if key not in st.session_state:
        st.session_state[key] = default
    slider_kwargs = dict(
        min_value=float(lo),
        max_value=float(hi),
        key=key,
        label=LABELS[key],
    )
    if key == "de_max":
        slider_kwargs["step"] = 0.05
    st.sidebar.slider(**slider_kwargs)

if st.sidebar.button("Clear all filters"):
    for key, _, _ in SLIDERS:
        st.session_state.pop(key, None)
    st.rerun()

# ------------------------------------------------------------------
# Apply the live filter
# ------------------------------------------------------------------
mask = pd.Series(True, index=frame.index)

for key, column, direction in SLIDERS:
    value = st.session_state.get(key, bounds[key][2])
    if direction == "min" and value > bounds[key][0]:
        mask &= pd.to_numeric(frame[column], errors="coerce") >= value
    elif direction == "max" and value < bounds[key][1]:
        mask &= pd.to_numeric(frame[column], errors="coerce") <= value

results = frame[mask]
count = len(results)

st.subheader("Screener results")
st.markdown(f"**{count} company{'ies' if count != 1 else 'y'} match your filters**")

if count == 0:
    st.info("No companies match the current filters — loosen the sliders.")
    st.stop()

display_columns = [
    "company_id",
    "company_name",
    "broad_sector",
    "composite_quality_score",
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "free_cash_flow_cr",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
]
display_names = {
    "company_id": "Ticker",
    "company_name": "Name",
    "broad_sector": "Sector",
    "composite_quality_score": "Composite",
    "return_on_equity_pct": "ROE %",
    "return_on_capital_employed_pct": "ROCE %",
    "net_profit_margin_pct": "NPM %",
    "operating_profit_margin_pct": "OPM %",
    "debt_to_equity": "D/E",
    "interest_coverage": "ICR",
    "free_cash_flow_cr": "FCF (cr)",
    "revenue_cagr_5yr": "Rev CAGR 5y %",
    "pat_cagr_5yr": "PAT CAGR 5y %",
    "pe_ratio": "P/E",
    "pb_ratio": "P/B",
    "dividend_yield_pct": "Div Yield %",
}

out = results.sort_values("composite_quality_score", ascending=False)[
    display_columns
].reset_index(drop=True)
out_display = out.rename(columns=display_names)

st.dataframe(out_display, width="stretch", hide_index=True)

csv_bytes = out.to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download filtered results (CSV)",
    data=csv_bytes,
    file_name="screener_results.csv",
    mime="text/csv",
)
