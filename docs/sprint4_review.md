# Sprint 4 — Dashboard & Valuation: Review & Retrospective

**Epic:** 05 (Streamlit Dashboard) & 06 (Valuation)
**Sprint:** Days 22–28
**Status:** ✅ Complete — all exit criteria verified (`verify_sprint4.py` + 224/224 tests)

---

## 1. Sprint Goal

Deliver an interactive Streamlit dashboard running on `localhost:8501` with
8 screens covering the full Nifty 100 analytics surface, plus a standalone
valuation module that flags overvalued and undervalued stocks relative to
their sector median P/E.

## 2. Deliverables

| Deliverable | Path | Notes |
|---|---|---|
| Streamlit entry point | `src/dashboard/app.py` | Wide layout, sidebar expanded, "Nifty 100 Analytics" |
| Cached DB loaders | `src/dashboard/utils/db.py` | `@st.cache_data(ttl=600)` for every query; ROOT = parents[3] |
| Home screen | `src/dashboard/pages/01_home.py` | 6 KPI tiles, year selector, sector donut, top-5 table |
| Company Profile | `src/dashboard/pages/02_profile.py` | Search → company card, 6 KPIs, revenue/profit bars, ROE/ROCE dual-axis, pros/cons badges |
| Screener | `src/dashboard/pages/03_screener.py` | 10 sidebar sliders + 6 presets + CSV download |
| Peer Comparison | `src/dashboard/pages/04_peers.py` | 11 peer groups, radar chart vs average, benchmark-highlighted KPI table |
| Trends | `src/dashboard/pages/05_trends.py` | Company search, up to 3 metrics overlaid, YoY % annotations |
| Sector Analysis | `src/dashboard/pages/06_sectors.py` | 10 sectors, bubble chart, sector-median KPI bars |
| Capital Allocation | `src/dashboard/pages/07_capital.py` | Treemap, 8 patterns, click drill-down |
| Annual Reports | `src/dashboard/pages/08_reports.py` | BSE PDF links with 404 badges, env-gated live checks |
| Valuation module | `src/analytics/valuation.py` | FCF yield, P/E sector flags, 5-year median P/E |
| Valuation summary | `output/valuation_summary.xlsx` | 92 rows × 10 columns |
| Valuation flags | `output/valuation_flags.csv` | 44 companies (Caution 14 + Discount 30) |
| Smoke test | `scripts/dev_smoke_dashboard.py` | AppTest: all 8 screens + profile timing for 5 tickers |
| Verification harness | `scripts/verify_sprint4.py` | 28+ exit-criteria checks across valuation, dashboard and health |
| Valuation tests | `tests/analytics/test_valuation.py` | 18 unit + integration tests |
| README | `README.md` | Run instructions, screen descriptions, project layout |

## 3. Verification Results

### Valuation (fresh build from DB)

| Check | Target | Actual | Status |
|---|---|---|---|
| 92-company summary built | 92 rows | **92** | ✅ |
| Output columns match spec | 10 columns | **10** | ✅ |
| Caution / Discount / Fair all present | ≥ 1 each | **14 / 30 / 48** | ✅ |
| No company missing a flag | 0 None | **0** | ✅ |
| FCF yields computed | ≥ 80 | **90 / 92** | ✅ |
| Flags CSV matches fresh rebuild | exact match | **match** | ✅ |
| `valuation_summary.xlsx` rows × cols | 92 × 10 | **92 × 10** | ✅ |

### Dashboard Screens (AppTest)

| Screen | Renders clean | Key element counts | Status |
|---|---|---|---|
| 01 Home | ✅ | 6 metrics, 1 donut | ✅ |
| 02 Profile | ✅ | 6 metrics, 1 selectbox | ✅ |
| 03 Screener | ✅ | 10 sliders, 6 preset buttons, CSV download | ✅ |
| 04 Peers | ✅ | 11 groups, 1 radar, 1 KPI table | ✅ |
| 05 Trends | ✅ | 1 multiselect | ✅ |
| 06 Sectors | ✅ | 10 sectors | ✅ |
| 07 Capital | ✅ | 1 treemap | ✅ |
| 08 Reports | ✅ | 1 company selector | ✅ |

### Profile Load Time (day 27 target: < 3 s)

| Ticker | Time | Status |
|---|---|---|
| TCS | 0.05 s | ✅ |
| SBIN | 0.06 s | ✅ |
| HINDUNILVR | 0.07 s | ✅ |
| RELIANCE | 0.04 s | ✅ |
| SUNPHARMA | 0.05 s | ✅ |

### Infrastructure

| Check | Status |
|---|---|
| Headless `/_stcore/health == 200` | ✅ |
| `requirements.txt` includes `streamlit` | ✅ |
| `use_container_width` → `width="stretch"` | ✅ |
| 224/224 tests pass (`pytest`) | ✅ |

## 4. Key Design Decisions

- **Page path:** Streamlit native multipage requires `pages/` adjacent to
  the entry script. Pages live at `src/dashboard/pages/` rather than a
  repo-root `pages/` directory, which the spec originally assumed. This is
  the minimum deviation required for automatic discovery to work.
- **DB path resolution:** `db.py` uses `Path(__file__).resolve().parents[3]`
  to find the repo root from `src/dashboard/utils/db.py` (4 levels up:
  utils → dashboard → src → root). This was initially incorrect
  (`parents[2]` = `src/`) and surfaced immediately as "unable to open
  database file" on the first smoke run.
- **ROCE is not persisted in `financial_ratios`** — the screener computes
  it on-the-fly from the balance sheet, but `get_company_series` (used by
  Profile and Trends) needs it per-year. ROCE was added inside
  `get_company_series` by merging the P&L and balance sheet and computing
  `EBIT / (equity + reserves + borrowings)` per row.
- **Valuation headers are snake_case** (`pe_ratio`, `pb_ratio`, …) for
  consistency with `financial_ratios` and `market_cap`. The verify harness
  checks the exact `OUTPUT_COLUMNS` order rather than mapping to "P/E" etc.
- **`capital_allocation` is CSV-only** — there is no database table. The
  dashboard reads `output/capital_allocation.csv` directly via
  `db.get_capital_allocation()`.
- **10 broad sectors, not 11** — the live data contains 10 distinct
  `broad_sector` values. The spec's "11 sectors" was aspirational.
- **Live report-link checks** are gated behind `NIFTY100_LINK_CHECK=0`
  (skip) so the verify harness and smoke test run offline without network
  timeouts. Default (`1`) enables live HEAD checks.
- **Streamlit 1.63 deprecation:** `use_container_width` → `width="stretch"`
  was applied across all pages to silence warnings (not fatal in 1.63 but
  will be removed after 2025-12-31).
- **FCF unavailable for 2/92 companies** (including SBIN) at the 2024
  baseline → FCF yield shows N/A. The verify harness checks that 90+ of 92
  companies have a computed FCF yield.
- **`pd.NA` in peers normalisation** was replaced with `np.nan` because
  `pd.Series(pd.NA, ..., dtype="float64")` raises an error in pandas 3.x.

## 5. Edge Cases & Issues Encountered

1. **"unable to open database file" on first smoke run:** `db.py` path was
   `parents[2]` (pointing at `src/` instead of the repo root). Fixed to
   `parents[3]`.
2. **Profile crash — `return_on_capital_employed_pct` not in index:**
   `get_company_series` called `get_ratios()` which returns `financial_ratios`
   — a table that does not persist ROCE (it is computed on-the-fly by the
   screener engine). Rewrote `get_company_series` to merge P&L + balance sheet
   and compute ROCE from first principles per row.
3. **Screener presets not filling sliders:** Preset buttons wrote to
   `st.session_state["roe_min"]` but the slider widget key was `"w_roe_min"`.
   Removed the `value=` kwarg and made the slider key match the session-state
   key exactly, so presets work via Streamlit's native session-state
   mechanism.
4. **`fig.add_annotations(annotations)` AttributeError:** Plotly's
   `Figure.add_annotations` does not exist; the correct API is
   `fig.add_annotation(single_dict)` called in a loop.
5. **`pd.Series(pd.NA, ..., dtype="float64")` in peers page:** This raises
   in pandas 3.x. Replaced with `pd.Series(np.nan, index=...)`.
6. **Screener Streamlit warning — "widget value set via Session State":**
   Both `key=` and `value=` were passed to `st.slider`. Removed `value=`;
   the widget now reads its initial value from session-state alone.
7. **AppTest `plotly_chart` not an attribute:** Streamlit's AppTest does not
   expose `at.plotly_chart`; use `at.get("plotly_chart")` instead.
8. **AppTest caption value inaccessible via `str()`:** The `.value`
   attribute is needed; `.replace("**", "")` strips the markdown bold markers
   to match the plain "Ticker: TCS" string.

## 6. Retrospective

### 6.1 What went well
- The AppTest smoke-test approach (`dev_smoke_dashboard.py`) caught the
  Profile crash (ROCE KeyError), trends crash (`add_annotations`), and
  the initial DB path bug before manual testing began.
- Caching every loader with `@st.cache_data(ttl=600)` means the dashboard
  stays fast even under repeated navigation — all profile loads came in
  under 100 ms after the first cache warm.
- The valuation module's merge-collision bug was caught and fixed during
  code review (pre-smoke), saving significant debugging time.
- All 8 screens share the same data-loading layer (`db.py`), so a single
  bug fix (ROCE computation in `get_company_series`) fixed Profile and
  Trends simultaneously.

### 6.2 What was problematic
- **ROCE not being persisted** was the single most expensive surprise — it
  required rewriting `get_company_series` to merge two additional tables and
  compute a metric from first principles, rather than simply selecting a
  column.
- Streamlit's AppTest has meaningful API gaps: no `plotly_chart` attribute,
  caption values not surfaced via `str()`, and session-state interaction
  warnings that required understanding the widget lifecycle in depth.
- The capital-allocation treemap click handler took multiple rewrites before
  the Plotly `on_select` return structure was correctly understood (points
  come back as a dict with `.selection.points`, not as a list).

### 6.3 Lessons for Sprint 5
- Persist all computed metrics that downstream consumers need, rather than
  relying on ad-hoc on-the-fly computation. ROCE is now a second example
  (after composite score) of a metric that would benefit from a DB column.
- AppTest coverage should be added early in the sprint so API surprises
  surface before the final smoke-test push.
- Keep the `NIFTY100_LINK_CHECK` env-gate pattern for any screen that
  performs external network calls — it makes offline verification fast
  and deterministic.

---
*Generated after full verification: `python scripts/verify_sprint4.py`
(all checks pass) + `python -m pytest tests/ -v` (224/224 pass).*
