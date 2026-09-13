"""Nifty 100 Analytics — Streamlit Multi-Page App (Sprint 4).

Run from the repository root:

    streamlit run src/dashboard/app.py

The sidebar automatically shows the 8 screens defined in src/dashboard/pages/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=":chart_with_upwards_trend:",
)

st.title("Nifty 100 Analytics Dashboard")
st.markdown(
    "Explore the full **Nifty 100** universe — fundamental ratios, "
    "peer comparisons, screener filters, valuation flags, and capital "
    "allocation patterns.  "
    "Use the **sidebar** to navigate to any screen."
)

st.divider()
c1, c2, c3 = st.columns(3)
c1.info(
    "**Screens**\n\n🏠 Home  •  👤 Company Profile\n📊 Screener  •  🤝 Peers\n📈 Trends  •  🏭 Sectors\n💰 Capital Map  •  📄 Reports"
)
c2.info(
    "**Quick Start**\n\n1. Select a screen on the left\n2. Filter with sidebar controls\n3. Charts update interactively"
)
c3.info(
    "**Data**\n\n92 Nifty 100 companies\nAnnual financials 2019–2024\nSQLite `db/nifty100.db`"
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Nifty 100 Analytics**\n\nSelect a screen from the panel below.")
