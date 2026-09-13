# Sprint 3 — Screener & Peer Engine: Review & Retrospective

**Epic:** 03 (Screener) & 04 (Peer Engine)
**Sprint:** Days 15–21
**Status:** ✅ Complete — all exit criteria verified on `db/nifty100.db`

---

## 1. Sprint Goal

Build the multi-preset financial screener with a weighted composite quality
score and the peer-analysis layer on top of the Sprint 2 ratio engine:
6 analyst-editable preset screeners (each returning 5–50 companies),
percentile ranks within 11 peer groups, per-company radar charts, and a
colour-coded peer comparison workbook.

## 2. Deliverables

| Deliverable | Path | Notes |
|---|---|---|
| Screener config (analyst-editable) | `config/screener_config.yaml` | 18 filterable metrics, 6 presets, Financials / Debt-Free carve-outs |
| Filter engine | `src/screener/engine.py` | Feature frame → threshold filters → weighted composite (P10/P90 winsorised, global + sector) → sorted presets |
| Screener export | `src/screener/export.py` | 8-sheet workbook with green/red threshold colour-coding + Summary tab |
| Screener workbook | `output/screener_output.xlsx` | 6 preset sheets (92 colour-coded rows each) + All Companies + Summary |
| Peer analysis | `src/analytics/peer.py` | SQL PERCENT_RANK (ties = min rank), D/E inverted, radar + bar charts, comparison workbook |
| Percentile table | `db/nifty100.db` → `peer_percentiles` | 542 rows / 56 companies (added to `db/schema.sql`) |
| Radar / bar charts | `reports/radar_charts/*.png` | 56 radar (peer overlay) + 36 bar (vs Nifty 100) |
| Peer comparison | `output/peer_comparison.xlsx` | 11 sheets, green/yellow/red percentiles, gold benchmark rows, median summary |
| Unit tests | `tests/screener/test_engine.py`, `tests/analytics/test_peer.py` | 47 new tests |
| Verification script | `scripts/verify_sprint3.py` | Re-runs every exit criterion |

## 3. Verification Results (fresh run: screener → peer pipeline)

| Exit criterion | Target | Actual | Status |
|---|---|---|---|
| Quality Compounder | 5–50 | **22** | ✅ |
| Value Pick | 5–50 | **5** | ✅ |
| Growth Accelerator | 5–50 | **19** | ✅ |
| Dividend Champion | 5–50 | **30** | ✅ |
| Debt-Free Blue Chip | 5–50 | **37** | ✅ |
| Turnaround Watch | 5–50 | **32** | ✅ |
| `peer_comparison.xlsx` sheets | 11 | **11** | ✅ |
| `screener_output.xlsx` sheets | 8 | **8** | ✅ |
| DQ rule unit tests | ≥ 14 | **33** (DQ-01…DQ-16) | ✅ |
| Unit tests total | — | **206 / 206** | ✅ |
| QC top 5 thresholds | ROE>15, FCF>0, RevCAGR>10 | INDIGO, IRCTC, ADANIPOWER, TRENT, NESTLEIND | ✅ |
| IT Services ROE ranking | TCS #1 | TCS 1.00 → TECHM 0.00 | ✅ |
| Radar + bar charts | 56 + 36 | **56 + 36** | ✅ |

Percentile table: 542 rows for 56 peer-group companies (10 metrics × ~9.7
filled per company — FCF and CAGR metrics are naturally sparser). The 36
companies without a peer group are handled via `peer_percentile_for()` which
returns *"No peer group assigned for <company>"*.

## 4. Key Design Decisions

- **Screening year** = latest fiscal year *with a computed ROE* per company
  (identical rule to the Sprint 2 screener), not the absolute latest year —
  BS runs to 2024-09 while P&L ends 2024-03, so the latest year's ROE is
  usually NULL.
- **D/E carve-out is operator-aware**: the Financials sector is skipped only
  for *max* D/E filters (`<` / `<=`). A `==` D/E test (e.g. "zero debt")
  still applies to banks — this is what keeps Debt-Free Blue Chip honest.
- **Debt Free passes ICR**: any company labelled `Debt Free` has no interest
  expense → infinite coverage → passes any ICR minimum.
- **Composite score** (Day 17, sums to 100): Profitability 35 (ROE 15 +
  ROCE 10 + NPM 10), Cash quality 30 (FCF CAGR 15 + CFO/PAT 10 + FCF-positive
  5), Growth 20 (Rev CAGR 10 + PAT CAGR 10), Leverage 15 (D/E 10 + ICR 5).
  Non-null components are reweighted; P10/P90 winsorisation per component
  (global and sector-relative variants both emitted); D/E inverted.
- **Numpy-boolean tolerance**: pandas 3.x returns `numpy.bool` scalars;
  the filter evaluator detects them by dtype (`bool` in `str(value.dtype)`),
  not by `type(value).__name__`. This was the root cause of Turnaround Watch
  returning 0 companies before the fix.
- **PERCENT_RANK** uses SQL semantics: `(rank − 1) / (n − 1)` with
  `method='min'` ties, always ranked **ascending** so the best value scores
  1.0; D/E is then inverted (`1 − pct`) so lower leverage = higher percentile.
- **Radar charts**: winsorised 0–100 per axis within the peer group
  (8 axes: ROE, ROCE, NPM, D/E inverted, FCF, PAT CAGR 5y, Rev CAGR 5y,
  composite); company = filled polygon, group average = dashed overlay.
  Companies with no peer group get a raw-value bar chart vs the Nifty 100
  average instead.

## 5. Edge Cases & Issues Encountered

1. **Turnaround Watch = 0 (first run)**: `_evaluate(value is True)` failed
   for `numpy.bool_` scalars, silently dropping every row on the
   `de_declining == True` filter. Fixed with dtype-based detection.
   Rebuilt: 32 companies.
2. **Merge collision**: `financial_ratios.id` collided with `companies.id`
   during the feature-frame join → renamed the master table column to
   `company_master_id`.
3. **PERCENT_RANK direction bug**: ranking "desc" made the *best* company
   score 0.0 (rank 1). Standard SQL PERCENT_RANK ranks ascending; changed to
   ascending + D/E inversion. Spot check: TCS (highest IT Services ROE)
   now sits at 1.00.
4. **Single colour-coding was dead**: preset sheets originally contained
   only companies passing every filter → red cells could never appear.
   Sheets now show the full 92-company universe sorted by composite, so both
   green (pass) and red (fail) threshold cells are visible and meaningful.
5. **Threshold calibration**: Value Pick needed P/B 4.5 (P/B<3 returned 4,
   falling below the 5-company floor); Debt-Free Blue Chip needed `D/E <=
   0.10` + the Financials `==` carve-out refinement to land at 37 without
   admitting structurally-leveraged banks.
6. **Consumer Finance group size (3)**: fine for percentiles but the sheet's
   median row is placed below a blank spacer — the workbook stores a headered
   1 + data + blank + median layout; no functional issue.
7. **Missing `fcf_positive` on minimal frames**: `compute_component_scores`
   now derives the flag from `free_cash_flow_cr` when the column is absent,
   keeping the component function self-sufficient for unit tests.

## 6. Retrospective

### 6.1 What went well
- Operator-aware carve-outs keep preset logic configurable and data-honest
  (banks are not "debt-free", but their leverage is structural).
- The smoke-test loop (feature frame → presets → Excel → workbook inspection)
  caught the numpy-bool and ranking bugs *before* writing the test suite.
- `verify_sprint3.py` codifies every exit criterion so the whole sprint can be
  re-verified in one command.

### 6.2 What was problematic
- Bool semantics across pandas 3.x (`numpy.bool`) were the single most
  costly bug of the sprint — silent data loss, not an exception.
- SQL PERCENT_RANK semantics are easy to get backwards (rank 1 = best = 0.0);
  a unit test pinning `_percent_rank` would have caught it immediately.
- Preset calibration was iterative; a small hand-computed sanity table in the
  config review would have cut the P/B and D/E tuning cycles.

### 6.3 Lessons for Sprint 4
- Pin scalar-dtype assumptions (bool/int/NaN) as explicit unit tests and run
  them against the *actual* pandas dtype family in use.
- Keep the percentile/rank direction contract in one helper with a named
  "best = 1.0" convention, and unit-test ties.
- Continue the `verify_sprintN.py` pattern as the regression harness.

---
*Generated after a full clean re-run: `python scripts/verify_sprint3.py`
(all checks pass) + `python -m pytest tests/ -v` (206/206 pass).*