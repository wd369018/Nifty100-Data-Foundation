"""Screen 08 — Annual Reports.

Company search, then a table of available annual-report years with
clickable BSE PDF links.  Reports whose link returns 404 (or is
missing) show a red "Report unavailable" badge instead.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.dashboard.utils.db import (
    get_companies,
    get_documents,
    report_url_status,
)

st.set_page_config(page_title="Annual Reports", layout="wide")

st.title("📄  Annual Reports")

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

docs = get_documents(ticker)
if docs.empty:
    st.info(f"No annual report records found for {ticker}.")
    st.stop()

st.write(
    f"**{ticker}** — available annual reports (BSE PDFs). " f"{len(docs)} records."
)

rows_html = """
<table style="width:100%; border-collapse: collapse;">
<tr style="text-align:left;">
  <th style="padding:6px">Year</th>
  <th style="padding:6px">Report</th>
</tr>
"""
for _, row in docs.iterrows():
    year = int(row["year"]) if row["year"] is not None else "?"
    url = row["annual_report"]
    if url is None or str(url).strip().lower() in ("null", "nan", ""):
        badge = '<span style="color:white;background:#d62728;padding:2px 8px;border-radius:10px;">Report unavailable</span>'
    else:
        status = report_url_status(url)
        if status == "ok":
            badge = f'<a href="{url}" target="_blank">Open PDF ↗</a>'
        else:
            badge = (
                f'<a href="{url}" target="_blank" style="color:#999">Open PDF ↗</a> '
                '<span style="color:white;background:#d62728;padding:2px 8px;'
                'border-radius:10px;">Report unavailable</span>'
            )
    rows_html += f"<tr><td style='padding:6px'>{year}</td><td style='padding:6px'>{badge}</td></tr>"

rows_html += "</table>"

st.markdown(rows_html, unsafe_allow_html=True)
st.caption(
    "Reports are checked against the BSE website (404 → 'Report unavailable'). "
    "You may need to run the dashboard with internet access for live checks."
)
