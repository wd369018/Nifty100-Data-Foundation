# Sprint 2 — Financial Ratio Engine: Review & Retrospective

**Epic:** 02 — Financial Ratio Engine  
**Sprint:** Days 08–14  
**Status:** ✅ Complete — all exit criteria verified on `db/nifty100.db`

---

## 1. Sprint Goal

Engineer the KPI computation layer on top of the Sprint 1 data foundation:
derive a full set of financial ratios for every (company, fiscal year) in the
three statements, populate `financial_ratios` (1,100+ rows, no KPI column
left entirely NULL), log cross-check anomalies, and ship a quantitative
screener for the Day 14 review.

## 2. Deliverables

| Deliverable | Path | Notes |
|---|---|---|
| Formula KPI modules | `src/analytics/ratios.py`, `cagr.py`, `cashflow_kpis.py` | NPM, OPM, ROE, ROA, D/E, ICR, asset turnover, 6 flags, 4 capital-allocation patterns, composite quality score |
| Ratio engine | `src/analytics/engine.py` | Universe build → row-by-row KPIs → CAGR → CFO quality → composite → persist |
| Populated table | `db/nifty100.db` → `financial_ratios` | 1,155 rows / 92 companies |
| KPIs (unit tests) | `tests/kpi/*.py` | 60 tests (`test_profitability.py`, `test_leverage.py`, `test_cagr.py`, `test_cashflow_kpis.py`) |
| Capital allocation | `output/capital_allocation.csv` | 1,155 rows |
| Edge-case log | `output/ratio_edge_cases.log` | 298 lines, 6 sections |
| Screener | `scripts/screener.py` → `output/screener_result.csv` | 38 companies |
| Verification script | `scripts/verify_sprint2.py` | Re-runs every exit criterion |
| Make targets | `Makefile` | `analytics`, `kpi`; `test` covers `tests` |

## 3. Verification Results (fresh run: load → engine → screener)

| Exit criterion | Target | Actual | Status |
|---|---|---|---|
| `financial_ratios` rows | ≥ 1,100 | **1,155** | ✅ |
| Distinct companies | 92 | **92** | ✅ |
| FK violations | 0 | **0** | ✅ |
| All-null KPI columns | none | **NONE** | ✅ |
| KPI unit tests | ≥ 20 | **60** (159 total suite) | ✅ |
| Screener (ROE>15%, D/E<1) | 15–50 | **38** | ✅ |
| Spot checks vs hand calc | 0.00pp | **0.000000pp** | ✅ |

Populated counts: ROE 1,042 · NPM 1,057 · D/E 1,140 · revenue CAGR 695 ·
PAT CAGR 631 · EPS CAGR 623 · composite score 1,138. Remaining NULLs are
genuine coverage gaps (e.g. BS runs to 2024-09 while P&L ends 2024-03;
short history prevents a 5-year CAGR) — none are a whole column.

Flags & labels: `high_leverage_flag` True = **19** (0 for Financials) ·
`icr_label` = {Debt Free, Satisfactory, At Risk} · `icr_warning_flag` True = **117**.

Capital allocation (Day 11): Reinvestor **593** · Mixed 216 · Cash
Accumulator 105 · Growth Funded by Debt 97 · Liquidating Assets 95 ·
Distress Signal 41 · Pre-Revenue 8.

## 4. Key Design Decisions

- **Universe** = union of (company_id, year) across P&L / BS / CF.
- EBIT = `operating_profit + other_income` (Day 08 design) for ROCE.
- ROCE for **Financials** is reported as sector-relative vs a benchmark and
  the D/E high-leverage flag is **suppressed** (leverage is the business of
  a bank).
- CAGR is **trailing**, measured over the 5-year window ending at each row's
  year (`cagr_ending_at`), not measured on the latest absolute year only.
- `cfo_quality_score` = mean CFO/PAT over the trailing 5 years; returns
  `None` if any PAT in the window is zero (division guard).
- Composite quality score = unweighted mean of capped sub-scores
  (ROE / 40, NPM / 20, ROCE / 40, revenue 5y CAGR / 25, CFO quality / 2),
  each coerced to 0–100.
- Source-only columns (`book_value_per_share`, `capex_cr`,
  `free_cash_flow_cr`) are merged from the source file; flags persisted as
  `'True'/'False'`.

## 5. Edge Cases & Data Anomalies (see `output/ratio_edge_cases.log`)

1. **Reported OPM cross-check** — 216 mismatches >1pp: 9 genuine formula
   discrepancies vs **207 source-data artefacts** (reported margins outside
   the [-200%, 300%] plausibility band, e.g. AXISBANK 1,353%; the Sprint 1
   DQ-03 class). Artefacts are logged, not "fixed".
2. **ROCE vs `companies.roce_percentage`** — 3 companies differ >5pp.
3. **ROE vs `companies.roe_percentage`** — 3 companies differ >5pp.
   Reported values are a single latest snapshot; computed values are per FY,
   so some difference is expected.
4. **Implausible computed ROE** — 52 rows with |ROE| > 100%. Root cause is a
   **balance-sheet scale anomaly** in the source (e.g. BEL equity+reserves
   ≈ ₹11 cr against P&L profit ≈ ₹3,985 cr → ROE ≈ 4,744%). NESTLEIND's
   117.75% ROE is genuine (thin equity, not an artefact).
5. **Financials carve-out** — task doc lists 19 Financials; the source data
   holds **23** companies in that broad sector. Carve-out applies to all 23.
6. **Screener timing** — BS covers through 2024-09 but P&L only through
   2024-03, so the latest year's ROE is often NULL. The screener therefore
   uses the latest row **per company with ROE present**; using the absolute
   latest year yields only 1 company and is wrong.

## 6. Retrospective

### 6.1 What went well
- Formulae isolated in pure, small modules → deterministic KPI unit tests
  (60) independent of the database.
- Cross-check-first approach turned the 207 OPM artefacts from a blocker
  into a documented, categorised finding.
- Trailing-window CAGR and CFO quality scale correctly to mid-history rows
  instead of only the latest snapshot.

### 6.2 What was problematic
- `series_cagr` initially anchored windows on the earliest qualifying year
  instead of the latest — silently wrong growth numbers. Caught by the CAGR
  tests and fixed.
- `cfo_quality_score` division-by-zero guards were initially missing;
  PAT = 0 cases returned nonsense until specified as `None`.
- Filtering flags with a literal `*` in a PowerShell `python -c` command
  silently produced empty runs (`load_all` used a plain directory glob that
  missed files). Resolved by switching to a temp-script invocation.
- The task's "19 Financials" vs the data's 23 required a documented,
  data-driven decision rather than a hardcoded carve-out list.

### 6.3 Lessons for Sprint 3
- Keep every computed column's nullability contract explicit; a partially
  covered source table (BS/P&L year skew) is permanent and must be handled
  at query time (screener: "latest year with KPI present").
- Maintain the `verify_sprint2.py` script as the regression harness for the
  analytical layer.
- Treat all source `*_percentage` columns as advisory — cross-check, log,
  and do not overwrite.

---
*Generated after a full clean re-run: `python -m src.etl.load_all` →
`python -m src.analytics.engine` → `python scripts/screener.py` →
`python scripts/verify_sprint2.py` (159/159 tests pass).*