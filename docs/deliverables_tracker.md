# Project Deliverables Tracker

All 23 deliverables are required for project sign-off on Day 45. Status
updated as each deliverable is completed.

| ID | Sprint | Deliverable | Location | Status |
| --- | --- | --- | --- | --- |
| D-01 | Sprint 1 | nifty100.db | db/nifty100.db | Done |
| D-02 | Sprint 1 | load_audit.csv | output/load_audit.csv | Done |
| D-03 | Sprint 1 | validation_failures.csv | output/validation_failures.csv | Done |
| D-04 | Sprint 1 | exploratory_queries.sql | notebooks/exploratory_queries.sql | Done |
| D-05 | Sprint 2 | financial_ratios table | db/nifty100.db → financial_ratios (1155 rows) | Done |
| D-06 | Sprint 2 | capital_allocation.csv | output/capital_allocation.csv | Done |
| D-07 | Sprint 3 | screener_output.xlsx | output/screener_output.xlsx | Done |
| D-08 | Sprint 3 | screener_config.yaml | config/screener_config.yaml | Done |
| D-09 | Sprint 3 | peer_comparison.xlsx | output/peer_comparison.xlsx | Done |
| D-10 | Sprint 3 | 92 Radar Charts | reports/radar_charts/ (92 files) | Done |
| D-11 | Sprint 4 | Streamlit Dashboard (8 Screens) | src/dashboard/app.py + src/dashboard/pages/ | Done |
| D-12 | Sprint 4 | valuation_summary.xlsx | output/valuation_summary.xlsx | Done |
| D-13 | Sprint 5 | cashflow_intelligence.xlsx | output/cashflow_intelligence.xlsx | Done |
| D-14 | Sprint 5 | pros_cons_generated.csv | output/pros_cons_generated.csv | Done |
| D-15 | Sprint 5 | analysis_parsed.csv | output/analysis_parsed.csv | Done |
| D-16 | Sprint 5 | 92 Company Tearsheets | reports/tearsheets/ (92 files) | Done |
| D-17 | Sprint 5 | 10 Sector Reports (data-driven; spec assumed 11) | reports/sector/ (10 files) | Done |
| D-18 | Sprint 5 | Portfolio Summary PDF | reports/portfolio/portfolio_summary.pdf | Done |
| D-19 | Sprint 6 | cluster_labels.csv | output/cluster_labels.csv | Done |
| D-20 | Sprint 6 | FastAPI Server (16 Endpoints) | src/api/main.py | Done |
| D-21 | Sprint 6 | pytest_report.html | reports/pytest_report.html (381 passed) | Done |
| D-22 | Sprint 6 | analyst_guide.pdf | docs/analyst_guide.pdf | Done |
| D-23 | Sprint 6 | acceptance_checklist.pdf | docs/acceptance_checklist.pdf | Done |

Notes

- D-01 / D-05: the database lives at `db/nifty100.db` (13 tables).
- D-17: the data contains 10 distinct `broad_sector` values, so 10 sector
  reports are generated; the tracker's "11" mirrored the original spec
  assumption and is a documented deviation (see docs/sprint6_review.md).
- Zero-failure rule (`make test` before every Git commit) is enforced by
  `scripts/verify_sprint6.py` gate AC-16.