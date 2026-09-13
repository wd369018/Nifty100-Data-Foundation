"""Capital allocation report (Sprint 5, Day 32).

Verifies that output/capital_allocation.csv is complete for the whole
universe, produces the latest-year 8-pattern distribution, confirms the
capital-allocation column inside cashflow_intelligence.xlsx and captures
the pattern change (latest vs prior year) for every company.

Run:  python -m src.analytics.capital_allocation_report
"""

import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cashflow_kpis import (
    PATTERN_CASH_ACCUMULATOR,
    PATTERN_DEBT_FUNDED_GROWTH,
    PATTERN_DISTRESS,
    PATTERN_LIQUIDATING,
    PATTERN_MIXED,
    PATTERN_PRE_REVENUE,
    PATTERN_REINVESTOR,
    PATTERN_SHAREHOLDER_RETURNS,
)

ALL_PATTERNS = [
    PATTERN_REINVESTOR,
    PATTERN_SHAREHOLDER_RETURNS,
    PATTERN_LIQUIDATING,
    PATTERN_DISTRESS,
    PATTERN_DEBT_FUNDED_GROWTH,
    PATTERN_CASH_ACCUMULATOR,
    PATTERN_PRE_REVENUE,
    PATTERN_MIXED,
]

CSV_PATH = Path("output/capital_allocation.csv")
XLSX_PATH = Path("output/cashflow_intelligence.xlsx")
DISTRIBUTION_PATH = Path("output/capital_pattern_distribution.csv")
CHANGES_PATH = Path("output/pattern_changes.csv")
DB_PATH = Path("db/nifty100.db")


def load_capital_allocation(path=CSV_PATH):
    """Read output/capital_allocation.csv."""
    return pd.read_csv(path)


def load_universe(db_path=DB_PATH):
    """Company ids from the live DB."""
    conn = sqlite3.connect(db_path)
    try:
        companies = pd.read_sql_query("SELECT company_id FROM sectors", conn)
    finally:
        conn.close()
    return set(companies["company_id"])


def coverage_issues(frame, universe):
    """Return dict of completeness problems for the CSV frame."""

    issues = {
        "missing_companies": sorted(universe - set(frame["company_id"])),
        "rows_with_null_pattern": int(frame["pattern_label"].isna().sum()),
        "rows_with_null_signs": int(
            frame[["cfo_sign", "cfi_sign", "cff_sign"]].isna().any(axis=1).sum()
        ),
    }

    no_latest = []
    for company_id, group in frame.groupby("company_id"):
        if group["year"].isna().any() or not len(
            group[group["year"] == group["year"].max()]
        ):
            no_latest.append(company_id)
    issues["companies_without_latest_year"] = sorted(no_latest)

    return issues


def latest_year_distribution(frame):
    """Count of each of the 8 patterns in the latest year per company."""

    rows = []
    for company_id, group in frame.groupby("company_id"):
        yearly = group.sort_values("year")
        rows.append(
            {
                "company_id": company_id,
                "year": yearly["year"].iloc[-1],
                "pattern": yearly["pattern_label"].iloc[-1],
            }
        )
    latest = pd.DataFrame(rows)
    counts = (
        latest["pattern"].value_counts().reindex(ALL_PATTERNS).fillna(0).astype(int)
    )
    return counts, latest


def build_pattern_changes(frame):
    """Latest-vs-prior-year pattern change per company."""

    rows = []
    for company_id, group in frame.groupby("company_id"):
        yearly = group.sort_values("year")
        if len(yearly) < 2:
            continue
        prior = yearly.iloc[-2]
        latest = yearly.iloc[-1]
        prior_pattern = str(prior["pattern_label"])
        latest_pattern = str(latest["pattern_label"])
        rows.append(
            {
                "company_id": company_id,
                "prior_year": str(prior["year"]),
                "latest_year": str(latest["year"]),
                "prior_pattern": prior_pattern,
                "latest_pattern": latest_pattern,
                "changed": prior_pattern != latest_pattern,
                "transition": f"{prior_pattern} -> {latest_pattern}",
            }
        )
    return pd.DataFrame(rows)


def verify_xlsx_label(xlsx_path=XLSX_PATH):
    """Check the capital-allocation column inside the Day 31 workbook.

    Returns (populated, missing) counts, where a value is missing when it
    is NaN/None.
    """

    frame = pd.read_excel(xlsx_path)
    if "capital_allocation_label" not in frame.columns:
        return None, None
    col = frame["capital_allocation_label"]
    return int(col.notna().sum()), int(col.isna().sum())


def main():
    print("=" * 60)
    print("CAPITAL ALLOCATION REPORT (Sprint 5, Day 32)")
    print("=" * 60)

    frame = load_capital_allocation()
    universe = load_universe()

    issues = coverage_issues(frame, universe)
    print(f"  CSV rows            : {len(frame)}")
    print(f"  Universe            : {len(universe)}")
    print(f"  Missing companies   : {issues['missing_companies']}")
    print(f"  Null-pattern rows   : {issues['rows_with_null_pattern']}")
    print(f"  Null-sign rows      : {issues['rows_with_null_signs']}")
    print(f"  No latest year      : {issues['companies_without_latest_year']}")

    counts, _ = latest_year_distribution(frame)
    print("\n  Latest-year distribution:")
    for pattern in ALL_PATTERNS:
        print(f"    {pattern:<22} {counts[pattern]}")

    populated, missing = verify_xlsx_label()
    print("\n  cashflow_intelligence.xlsx capital-allocation:")
    print(f"    populated          : {populated}")
    print(f"    missing            : {missing}")

    changes = build_pattern_changes(frame)
    n_changes = int(changes["changed"].sum())
    print(
        f"\n  Pattern changes (latest vs prior year): {n_changes} " f"of {len(changes)}"
    )

    DISTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"pattern": ALL_PATTERNS, "companies": [counts[p] for p in ALL_PATTERNS]}
    ).to_csv(DISTRIBUTION_PATH, index=False)
    changes.to_csv(CHANGES_PATH, index=False)

    print(f"\n  Distribution         : {DISTRIBUTION_PATH}")
    print(f"  Changes              : {CHANGES_PATH}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
