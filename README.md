# Nifty 100 Data Foundation

End-to-end Nifty 100 analytics platform: ETL → financial ratios → screener
→ peer analysis → valuation → interactive Streamlit dashboard → NLP
pros/cons → cash flow intelligence → PDF report pack.

## Quick Start

```bash
# 1. Create / activate the virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Rebuild the database (skip if db/nifty100.db already exists)
python -m src.etl.load_all
python -m src.analytics.engine

# 4. Launch the dashboard
streamlit run src/dashboard/app.py
```

The app opens at **http://localhost:8501** with a wide layout and
sidebar navigation.

## Screens (8 pages)

| # | Screen | What it shows |
|---|--------|---------------|
| 01 | **Home** | 6 KPI tiles (year-selectable), sector donut, top-5 composite score |
| 02 | **Company Profile** | Search by name/ticker → company card, 6 KPIs, 10-year revenue/net-profit bars, ROE/ROCE dual-axis, pros/cons badges |
| 03 | **Screener** | 10 metric sliders + 6 preset buttons (Quality, Value, Growth, Dividend, Debt-Free, Turnaround); live results table + CSV download |
| 04 | **Peer Comparison** | 11 peer groups; radar chart (8 axes vs group average) + side-by-side KPI table with benchmark row highlighted |
| 05 | **Trends** | Company search + up to 3 metrics overlaid; 10-year line chart with YoY % annotations |
| 06 | **Sector Analysis** | 10 sectors; bubble chart (Revenue × ROE × Market Cap) + sector-median KPI bar |
| 07 | **Capital Allocation** | Treemap of 92 companies grouped by 8 capital-allocation patterns; click/dropdown drill-down |
| 08 | **Annual Reports** | Company search → list of years with BSE PDF links; 404s flagged with red badge |

> **Page path note:** Streamlit native multipage requires `pages/` files
> to sit beside the entry script. Pages live at `src/dashboard/pages/`
> (not a repo-root `pages/` directory) so they are discovered
> automatically when running `streamlit run src/dashboard/app.py`.

## Valuation Module

```bash
python -m src.analytics.valuation
```

Produces two artefacts in `output/`:

- `valuation_summary.xlsx` — 92 rows × 10 columns (PE, PB, EV/EBITDA, FCF
  yield, 5-year median PE, sector-relative flag).
- `valuation_flags.csv` — companies flagged **Caution** (P/E > 1.5× sector
  median) or **Discount** (P/E < 0.7× sector median).

## Project Layout

```
├── db/nifty100.db            # SQLite — companies, ratios, market cap, peer groups
├── src/
│   ├── etl/                  # Data ingestion & validation
│   ├── analytics/            # Ratio engine, screener, peers, valuation, cash-flow intelligence
│   ├── nlp/                  # Analysis-text parser + auto pros/cons generator
│   ├── reports/              # Tearsheet, sector & portfolio PDF generators
│   ├── screener/             # Feature frame + preset filter engine + export
│   └── dashboard/
│       ├── app.py            # Streamlit entry point
│       ├── utils/db.py       # Cached data loaders (@st.cache_data)
│       └── pages/            # The 8 screens (01_home … 08_reports)
├── config/screener_config.yaml
├── scripts/
│   ├── verify_sprint3.py     # Sprint 3 exit-criteria harness
│   ├── verify_sprint4.py     # Sprint 4 exit-criteria harness (dashboard + valuation)
│   ├── verify_sprint5.py     # Sprint 5 exit-criteria harness (NLP + cash flow + reports)
│   └── dev_smoke_dashboard.py
├── tests/                    # 267 unit tests (pytest)
├── output/                   # Screener workbook, valuation, NLP, cash-flow & allocation artefacts
├── reports/                  # Tearsheets, sector & portfolio PDFs (plus chart PNGs)
└── Makefile                  # load, analytics, test, verify3/4/5, dashboard, valuation, reports
```

## Testing & Verification

```bash
# Run the full test suite (381 tests, HTML report)
python -m pytest tests -v
python -m pytest tests --html=reports/pytest_report.html --self-contained-html

# Sprint 6 exit-criteria harness (clustering + API + 20 acceptance gates)
python scripts/verify_sprint6.py

# Sprint 5 exit-criteria harness (NLP, cash flow intelligence, PDF reports)
python scripts/verify_sprint5.py

# Sprint 4 exit-criteria harness (valuation + dashboard screens + health check)
python scripts/verify_sprint4.py

# Sprint 3 exit-criteria harness (screener + peers)
python scripts/verify_sprint3.py

# Streamlit smoke test (all 8 screens, profile timing for 5 tickers)
python -m scripts.dev_smoke_dashboard
```

## Sprint 5 — NLP, Cash Flow Intelligence & PDF Reports

```bash
# Day 29: parse analysis.xlsx free-text CAGR fields
python -m src.nlp.parser                    # -> output/analysis_parsed.csv (+ failures, divergence)

# Day 30: auto pros/cons (12 pro + 12 con rules, confidence > 60)
python -m src.nlp.pros_cons_generator      # -> output/pros_cons_generated.csv (92/92 coverage)

# Day 31: cash flow intelligence workbook
python -c "from src.analytics.cashflow_kpis import main; main()"
#   -> output/cashflow_intelligence.xlsx + output/distress_alerts.csv (13 flags)

# Day 32: capital-allocation coverage + distribution + pattern changes
python -m src.analytics.capital_allocation_report

# Days 33-34: batch tearsheets (88 PDFs, 4 documented skips) + sector PDFs
python -m src.reports.tearsheet --all      # -> reports/tearsheets/*.pdf
python -m src.reports.sector_report        # -> reports/sector/*.pdf (10 sectors)

# Day 35: portfolio summary with trend arrows + retrospective
python -m src.reports.portfolio_report     # -> reports/portfolio/portfolio_summary.pdf
```

Full details, decisions and deviations from the task brief are in
`docs/sprint5_review.md`.

## Sprint 6 — Clustering, REST API & Sign-off

### Day 36-37 — Clustering & descriptive analytics

```bash
# 92 companies -> 5 labelled archetypes (KMeans, sector-median imputation,
# StandardScaler, k=5, random_state=42). Elbow + assignment CSV.
python -m src.analytics.clustering     # -> reports/elbow_plot.png, output/cluster_labels.csv

# Cluster profiles, 10-KPI correlation heatmap, per-sector Z-score outliers,
# portfolio P10-P90 statistics.
python -m src.analytics.descriptive    # -> output/cluster_profile.csv, reports/correlation_heatmap.png,
                                       #    output/outlier_report.csv, output/portfolio_stats.csv
```

Clusters: 0 High-Quality Compounders, 1 High-Margin Franchises, 2 Defense
High-ROE Leaders, 3 Leveraged Financials, 4 Cash-Flow Outliers.

### Day 38-40 — FastAPI REST API (16 endpoints under /api/v1)

```bash
python -m uvicorn src.api.main:app --port 8000

python scripts/export_openapi.py      # -> docs/openapi.json + docs/nifty100.postman_collection.json
```

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | status, version, uptime, row counts for the 10 DB tables |
| `GET /companies` | list all 92 with sector / market-cap / search filters |
| `GET /companies/{ticker}` | profile + latest KPIs (404 if unknown) |
| `GET /companies/{ticker}/pl` `.../bs` `.../cashflow` `.../ratios` | statement & KPI history (optional `from_year`/`to_year`, `year`) |
| `GET /companies/{ticker}/tearsheet` | streamed PDF |
| `GET /screener` | `min_roe`, `max_de`, `min_fcf`, `sector`, `min_rev_cagr_5yr`, `min_pat_cagr_5yr`, `max_pe` (HTTP 400 on bad values) |
| `GET /sectors` | sector aggregates + market-cap category splits |
| `GET /sectors/{sector}/companies` | companies in one sector (404 if unknown) |
| `GET /peers/{group_name}` | peer membership + percentile ranks (404 if unknown) |
| `GET /companies/{ticker}/peers/compare` | 8-axis radar data |
| `GET /market-cap/{ticker}` | 2019-2024 valuation multiples |
| `GET /portfolio/stats` | P10-P90 portfolio statistics |
| `GET /companies/{ticker}/documents` | annual-report registry with link status |

### Day 41-42 — Unit, API & integration tests

```bash
python -m pytest tests/etl tests/kpi tests/dq -v   # normaliser, loader, ratios, DQ rules
python -m pytest tests/api -v                      # health, companies, screener (+dashboard integration), sectors
```

### Day 43 — Performance

```bash
python scripts/load_test_api.py     # 10 concurrent /screener calls < 10 s (measured ~1 s)
python scripts/perf_dashboard.py    # Company Profile < 3 s per ticker; writes output/perf_notes.md
python scripts/e2e_endpoints.py     # FastAPI + Streamlit co-run on separate ports
```

### Day 44 — Docs, formatting, archive

```bash
python scripts/build_analyst_guide.py    # -> docs/analyst_guide.pdf (12 pages)
python -m black src tests scripts        # formatter
python -m ruff check .                   # linter (pyproject.toml config)
```

`output/final_deliverables/` archives the 23 Sprint 6 deliverables.

### Day 45 — Acceptance & sign-off

```bash
python scripts/verify_sprint6.py     # 20 gates AC-01 .. AC-20 -> docs/acceptance_checklist.pdf
```

Full details, decisions and deviations from the task brief are in
`docs/sprint6_review.md`.

## Makefile Targets

```
make load           # Rebuild DB from raw data
make analytics      # Run ratio engine
make test           # pytest tests -v
make testhtml       # pytest + HTML report
make screener       # Build screener output
make peer           # Build peer percentiles + radar charts
make valuation      # python -m src.analytics.valuation
make dashboard      # streamlit run src/dashboard/app.py
make api            # uvicorn src.api.main:app (port 8000)
make cluster        # clustering + descriptive analytics
make profile        # build docs/analyst_guide.pdf
make lint           # black --check + ruff check
make loadtest / perf / e2e   # Day 43 performance harnesses
make verify3        # Sprint 3 harness
make verify4        # Sprint 4 harness
make verify5        # Sprint 5 harness
make verify6        # Sprint 6 harness (20 gates)
make nlp            # parser + pros/cons generator
make cfi            # cash flow intelligence workbook
make capalloc       # capital-allocation report
make tearsheet      # batch-tearsheet generator
make sector         # sector PDF reports
make portfolio      # portfolio summary PDF
```

> **Windows note:** `make` may not be available. Use the `python -m`
> / `venv\Scripts\python.exe` equivalents directly.

## Key Design Notes

- **10 broad sectors** (not 11): Financials, Energy, Consumer Discretionary,
  Industrials, Materials, Consumer Staples, Healthcare, Information Technology,
  Real Estate, Communication Services.
- **Screening year** = latest fiscal year with a computed ROE per company.
  Most companies use 2024-03; one company (SBIN) uses 2024-09.
- **FCF** is unavailable for 2 of 92 companies (e.g. SBIN) at baseline;
  FCF yield shows N/A for these.
- **Capital allocation** data is read from `output/capital_allocation.csv`
  (no database table).
- **All dashboard loaders** use `@st.cache_data(ttl=600)` (10-minute TTL).
- **Live report-link checks** can be disabled by setting the environment
  variable `NIFTY100_LINK_CHECK=0`.
- **Clustering** maps all 92 companies to 5 labelled archetypes
  (KMeans, feature scaling, sector-median imputation) — see
  `output/cluster_labels.csv`.
- **The API caches the screening feature frame** for the life of the
  process (`src/api/__init__.py:cached_feature_frame`) so `load_feature_frame`
  (CAGR computation) runs once at startup, not per request.
- **The database carries 10 sectors**, not the 11 assumed by the planning
  documents — the API and its tests follow the data.

## Requirements

Python 3.14.3, streamlit 1.63+, plotly 7.0+, pandas, numpy, openpyxl,
scipy, scikit-learn, requests, beautifulsoup4, lxml, pyyaml, tqdm,
reportlab, pymupdf, fastapi, uvicorn, httpx, pytest-html.
