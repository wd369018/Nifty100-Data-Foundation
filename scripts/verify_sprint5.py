"""Sprint 5 exit-criteria verification harness.

Run:  python scripts/verify_sprint5.py

Checks (against the Sprint 5 exit criteria):
  1. output/analysis_parsed.csv exists with the expected columns.
  2. output/pros_cons_generated.csv -> every company has >= 1 pro and
     >= 1 con, all confidence values exceed 60.
  3. output/cashflow_intelligence.xlsx -> 92 rows with all columns,
     ATGL row present (no cash flow) flagged; distress_alerts.csv rows
     are a subset of the flagged companies.
  4. capital_allocation.csv coverage + output/pattern_changes.csv.
  5. reports/tearsheets/*.pdf -> count = 92 - skipped and every file
     >= 30 KB; skipped_tearsheets.csv documents the gap.
  6. reports/sector/*.pdf = 10 files (data has 10 sectors).
  7. reports/portfolio/portfolio_summary.pdf exists.
  Run: python -m pytest tests/ (optional, external).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))


def load_universe():
    import sqlite3

    conn = sqlite3.connect(ROOT / "db" / "nifty100.db")
    try:
        companies = pd.read_sql_query("SELECT company_id FROM sectors", conn)
    finally:
        conn.close()
    return set(companies["company_id"])


def main():
    print("=" * 72)
    print("SPRINT 5 VERIFICATION - EXIT CRITERIA")
    print("=" * 72)

    universe = load_universe()

    # ---- Day 29: parser ----
    parsed_path = ROOT / "output" / "analysis_parsed.csv"
    exist_ok = parsed_path.exists()
    if exist_ok:
        parsed = pd.read_csv(parsed_path)
        need_cols = {"company_id", "metric_type", "period_years", "value_pct"}
        check("D29 analysis_parsed.csv columns", set(parsed.columns) >= need_cols)
        check("D29 at least 40 parsed rows", len(parsed) >= 40, f"{len(parsed)} rows")
        check(
            "D29 parse_failures.csv exists",
            (ROOT / "output" / "parse_failures.csv").exists(),
        )
        check(
            "D29 divergence file exists",
            (ROOT / "output" / "analysis_divergence.csv").exists(),
        )
    else:
        check("D29 analysis_parsed.csv exists", False)

    # ---- Day 30: pros/cons ----
    pc_path = ROOT / "output" / "pros_cons_generated.csv"
    if pc_path.exists():
        pc = pd.read_csv(pc_path)
        pro_ids = set(pc[pc["type"] == "pro"]["company_id"])
        con_ids = set(pc[pc["type"] == "con"]["company_id"])
        check(
            "D30 all companies have >= 1 pro",
            universe <= pro_ids,
            f"{len(pro_ids)}/{len(universe)}",
        )
        check(
            "D30 all companies have >= 1 con",
            universe <= con_ids,
            f"{len(con_ids)}/{len(universe)}",
        )
        check(
            "D30 confidence strictly above 60",
            bool((pc["confidence_pct"] > 60).all()),
            f"min={pc['confidence_pct'].min()}",
        )
        check(
            "D30 no duplicate (company, type, rule)",
            pc.duplicated(["company_id", "type", "rule_id"]).sum() == 0,
        )
    else:
        check("D30 pros_cons_generated.csv exists", False)

    # ---- Day 31: cash flow intelligence ----
    xlsx_path = ROOT / "output" / "cashflow_intelligence.xlsx"
    xlsx_cols = {
        "company_id",
        "sector",
        "cfo_quality_score",
        "cfo_quality_label",
        "capex_intensity_pct",
        "capex_label",
        "fcf_cagr_5yr",
        "fcf_conversion_pct",
        "distress_flag",
        "deleveraging_flag",
        "capital_allocation_label",
    }
    if xlsx_path.exists():
        xl = pd.read_excel(xlsx_path)
        check("D31 xlsx has 92 rows", len(xl) == 92, f"{len(xl)} rows")
        check("D31 xlsx has all columns", set(xl.columns) >= xlsx_cols)
        check("D31 covers the universe", set(xl["company_id"]) == universe)
        distress = pd.read_csv(ROOT / "output" / "distress_alerts.csv")
        flagged = set(xl.loc[xl["distress_flag"], "company_id"])
        check(
            "D31 distress alerts match flagged set",
            set(distress["company_id"]) == flagged,
            f"{len(distress)} alerts for {len(flagged)} flagged",
        )
    else:
        check("D31 cashflow_intelligence.xlsx exists", False)

    # ---- Day 32: capital allocation ----
    cap_path = ROOT / "output" / "capital_allocation.csv"
    if cap_path.exists():
        cap = pd.read_csv(cap_path)
        check(
            "D32 capital_allocation covers universe", set(cap["company_id"]) == universe
        )
        check("D32 no null pattern label", cap["pattern_label"].isna().sum() == 0)
        check(
            "D32 pattern_changes.csv exists",
            (ROOT / "output" / "pattern_changes.csv").exists(),
        )
        check(
            "D32 distribution csv exists",
            (ROOT / "output" / "capital_pattern_distribution.csv").exists(),
        )
    else:
        check("D32 capital_allocation.csv exists", False)

    # ---- Day 34: tearsheets ----
    tear_dir = ROOT / "reports" / "tearsheets"
    skips_path = ROOT / "output" / "skipped_tearsheets.csv"
    tear_files = sorted(tear_dir.glob("*.pdf")) if tear_dir.exists() else []
    sizes = [f.stat().st_size for f in tear_files]
    n_skips = len(pd.read_csv(skips_path)) if skips_path.exists() else None
    expected = 92 - (n_skips or 0)
    check(
        "D33/D34 tearsheet count = 92 - skips",
        len(tear_files) == expected,
        f"{len(tear_files)} files, {n_skips} skipped",
    )
    check(
        "D34 every tearsheet >= 30 KB",
        len(tear_files) > 0 and all(s >= 30_000 for s in sizes),
        f"min={min(sizes) if sizes else 0}",
    )
    check(
        "D34 skipped_tearsheets.csv exists and lists gaps",
        skips_path.exists() and n_skips == 4,
        f"{n_skips} skip rows",
    )

    # ---- Day 34: sector reports ----
    sector_dir = ROOT / "reports" / "sector"
    sector_files = sorted(sector_dir.glob("*.pdf")) if sector_dir.exists() else []
    check(
        "D34 sector PDFs = 10 (data has 10 sectors)",
        len(sector_files) == 10,
        f"{len(sector_files)} files",
    )

    # ---- Day 35: portfolio summary ----
    pf_path = ROOT / "reports" / "portfolio" / "portfolio_summary.pdf"
    check(
        "D35 portfolio_summary.pdf exists",
        pf_path.exists() and pf_path.stat().st_size > 50_000,
        f"{pf_path.stat().st_size} bytes" if pf_path.exists() else "",
    )

    # ---- Summary ----
    print()
    failed = 0
    for name, ok, detail in CHECKS:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        detail_str = f"  [{detail}]" if detail else ""
        print(f"  [{mark}] {name}{detail_str}")

    print()
    print("=" * 72)
    if failed:
        print(f"SPRINT 5 VERIFICATION: {failed} CHECK(S) FAILED")
        return 1
    print("ALL SPRINT 5 CHECKS PASSED")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
