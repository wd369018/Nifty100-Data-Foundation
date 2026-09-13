"""
Data-quality manual review for the Nifty100 Data Foundation project.

Day 06 deliverable:
- Select 5 random companies from the loaded database
- Show their year coverage across financial tables
- Identify companies with fewer than 5 years of financial history
- Re-verify FK integrity and overall DB health
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("db/nifty100.db")

FIN_TABLES = [
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
]

SAMPLE_SIZE = 5
MIN_YEARS = 5


def get_connection():
    """Create a SQLite connection for the Nifty100 database."""

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_companies():
    """Return the list of company ids and names."""

    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT id, company_name FROM companies ORDER BY id",
            conn,
        )
    finally:
        conn.close()


def get_year_coverage(company_id, table_name):
    """Return sorted years for a company in a table."""

    conn = get_connection()
    try:
        df = pd.read_sql_query(
            f"""
            SELECT year
            FROM [{table_name}]
            WHERE company_id = ?
            ORDER BY year
            """,
            conn,
            params=(company_id,),
        )
        return df["year"].tolist()
    finally:
        conn.close()


def get_record_count(table_name, company_id=None):
    """Return row count for a table (optionally filtered by company)."""

    conn = get_connection()
    try:
        if company_id is None:
            return conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
        return conn.execute(
            f"SELECT COUNT(*) FROM [{table_name}] WHERE company_id = ?",
            (company_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def review_sample_companies(companies):
    """Print per-table year coverage for sampled companies."""

    print("=" * 70)
    print("SAMPLE COMPANY REVIEW (5 random companies)")
    print("=" * 70)

    sampled = companies.sample(n=SAMPLE_SIZE, random_state=42)

    for _, company in sampled.iterrows():
        cid = company["id"]
        print(f"\n{company['company_name']} ({cid})")

        for table in FIN_TABLES + ["market_cap"]:
            years = get_year_coverage(cid, table)
            label = table.replace("_", " ").upper()
            count = len(years)

            if not years:
                print(f"  {label:<20} -")
                continue

            start = years[0]
            end = years[-1]
            print(f"  {label:<20} {count:>3} yrs  " f"{start} -> {end}")


def identify_companies_with_little_history():
    """Find companies with fewer than N years in any financial table."""

    conn = get_connection()
    try:
        companies = pd.read_sql_query(
            "SELECT id, company_name FROM companies",
            conn,
        )
    finally:
        conn.close()

    print("\n" + "=" * 70)
    print(f"COMPANIES WITH < {MIN_YEARS} YEARS OF HISTORY")
    print("=" * 70)

    found = False

    for _, company in companies.iterrows():
        cid = company["id"]

        for table in FIN_TABLES:
            hist = get_year_coverage(cid, table)

            if 0 < len(hist) < MIN_YEARS:
                print(
                    f"  {company['company_name']:<28} ({cid:<12}) "
                    f"{table:<16} {len(hist)} years "
                    f"[{hist[0]} -> {hist[-1]}]"
                )
                found = True

    if not found:
        print("  None (all companies meet the threshold).")

    return found


def verify_db_health():
    """Verify FK integrity and table-level record counts."""

    conn = get_connection()
    try:
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()

    print("\n" + "=" * 70)
    print("DATABASE HEALTH SUMMARY")
    print("=" * 70)

    tables = [
        "companies",
        "sectors",
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
        "financial_ratios",
        "market_cap",
        "peer_groups",
        "stock_prices",
    ]

    total = 0

    for table in tables:
        count = get_record_count(table)
        total += count
        print(f"  {table:<20} {count:>6} rows")

    print(f"\n  TOTAL RECORDS   : {total}")
    print(f"  FK VIOLATIONS   : {len(fk_violations)}")

    if fk_violations:
        for violation in fk_violations[:10]:
            print(f"    {violation}")

    print("\n" + "=" * 70)
    print("REVIEW COMPLETE")
    print("=" * 70)


def main():
    """Run the Day 06 data-quality review."""

    companies = get_companies()

    print(f"Companies in database: {len(companies)}")
    print()

    review_sample_companies(companies)
    identify_companies_with_little_history()
    verify_db_health()


if __name__ == "__main__":
    main()
