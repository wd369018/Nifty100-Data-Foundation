"""
Full data load script for the Nifty100 Data Foundation project.

Day 05 deliverable:
- Load all 12 source files (7 core + 5 supplementary)
- Correct load order (companies first for FK references)
- Normalize years, deduplicate, filter orphans
- Load into SQLite (nifty100.db)
- Generate output/load_audit.csv with row counts & rejections
- Verify FK check = 0
"""

import csv
import sqlite3
from pathlib import Path

import pandas as pd

from src.etl.fk_filter import filter_company_foreign_keys
from src.etl.loader import (
    deduplicate,
    load_excel,
    normalize_year_column,
)

REJECTION_FILE = Path("output/load_rejections.csv")


RAW_DIR = Path("data/raw")
SUPPORTING_DIR = Path("data/supporting")
DB_PATH = Path("db/nifty100.db")
SCHEMA_PATH = Path("db/schema.sql")
AUDIT_FILE = Path("output/load_audit.csv")

# File stem -> SQLite table name mapping.
FILE_TABLE_MAP = {
    "companies": "companies",
    "profitandloss": "profitandloss",
    "balancesheet": "balancesheet",
    "cashflow": "cashflow",
    "analysis": "analysis",
    "documents": "documents",
    "prosandcons": "prosandcons",
    "financial_ratios": "financial_ratios",
    "market_cap": "market_cap",
    "peer_groups": "peer_groups",
    "sectors": "sectors",
    "stock_prices": "stock_prices",
}

# Load order: companies must be first (FK reference).
LOAD_ORDER = [
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

# Tables whose year column is stored as TEXT "YYYY-MM".
TEXT_YEAR_TABLES = {
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
}

# Documented source-data corrections (known-good values).
# TVS Motor's face value is missing in the source workbook;
# the correct face value is 1 (documented data fix).
CLEANING_RULES = {
    ("companies", "TVSMOTOR", "face_value"): 1,
}


def clean_row_values(df, table_name):
    """
    Apply documented source-data corrections before loading.

    Parameters:
        df (pandas.DataFrame):
            DataFrame to clean.

        table_name (str):
            Target table name.

    Returns:
        pandas.DataFrame:
            Cleaned DataFrame.
    """

    df = df.copy()

    for (table, company_id, column), value in CLEANING_RULES.items():
        if table_name != table or column not in df.columns:
            continue

        # companies uses 'id'; other tables use 'company_id'.
        id_column = "id" if table == "companies" else "company_id"

        if id_column not in df.columns:
            continue

        mask = df[id_column].eq(company_id) & df[column].isna()

        if mask.any():
            df.loc[mask, column] = value
            print(
                f"  Clean: {table_name}.{column} = {value} "
                f"for {company_id} ({int(mask.sum())} row(s))"
            )

    return df


def find_file(table_name):
    """Find the source Excel file for a given table name."""

    search_dirs = [RAW_DIR, SUPPORTING_DIR]

    for directory in search_dirs:
        if not directory.exists():
            continue
        for f in directory.glob("*.xlsx"):
            # Match by the last segment of the filename.
            parts = f.stem.split("-")
            if parts[-1].lower() == table_name:
                return f

    return None


def create_schema():
    """Create all database tables using schema.sql."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing database to start fresh.
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

    print(f"Schema created: {DB_PATH}")


def load_to_sqlite(df, table_name):
    """
    Insert a DataFrame into a SQLite table.

    Rows that violate table constraints are rejected and returned
    separately instead of failing the entire load.

    Returns:
        tuple[int, pandas.DataFrame]:
            (loaded_count, rejected_rows)
    """

    if df.empty:
        return 0, df

    rows_list = df.to_dict(orient="records")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    # Build the column list from the DataFrame.
    columns = list(df.columns)
    placeholders = ",".join("?" for _ in columns)
    column_names = ",".join(f"[{c}]" for c in columns)

    insert_sql = (
        f"INSERT INTO [{table_name}] " f"({column_names}) VALUES ({placeholders})"
    )

    loaded = 0
    rejected = []

    try:
        for row in rows_list:
            values = tuple(None if pd.isna(v) else v for v in row.values())

            try:
                conn.execute(insert_sql, values)
                loaded += 1
            except sqlite3.IntegrityError as exc:
                row_dict = dict(row)
                row_dict["_rejection_reason"] = str(exc)
                rejected.append(row_dict)
    finally:
        conn.commit()
        conn.close()

    rejected_df = pd.DataFrame(rejected) if rejected else None

    return loaded, rejected_df


def get_row_count(table_name):
    """Get the number of rows in a SQLite table."""

    conn = sqlite3.connect(str(DB_PATH))

    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        return cursor.fetchone()[0]
    finally:
        conn.close()


def check_foreign_keys():
    """Check for foreign key violations."""

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        return violations
    finally:
        conn.close()


def main():
    """Execute the full data load pipeline."""

    print("=" * 60)
    print("NIFTY100 FULL DATA LOAD")
    print("=" * 60)

    # Step 1: Create schema.
    print("\n[1/4] Creating database schema...")
    create_schema()

    # Step 2: Load all files.
    print("\n[2/4] Loading data files...")

    audit_rows = []
    companies_df = None
    all_rejections = []

    for table_name in LOAD_ORDER:
        file_path = find_file(table_name)

        if file_path is None:
            print(f"  SKIP: {table_name} (file not found)")
            audit_rows.append(
                {
                    "table_name": table_name,
                    "source_file": "NOT FOUND",
                    "source_rows": 0,
                    "loaded_rows": 0,
                    "rejected_rows": 0,
                    "status": "SKIPPED",
                }
            )
            continue

        print(f"\n  Loading: {table_name}")
        print(f"  File: {file_path.name}")

        try:
            df = load_excel(file_path)

            source_rows = len(df)
            print(f"  Source rows: {source_rows}")

            # Normalize year columns (only for TEXT-year tables).
            if table_name in TEXT_YEAR_TABLES:
                df = normalize_year_column(df)

            # Apply documented source-data corrections.
            df = clean_row_values(df, table_name)

            # Deduplicate.
            df = deduplicate(df, table_name)

            # FK filtering (skip for companies master).
            rejected_rows = 0
            if table_name != "companies" and companies_df is not None:
                if "company_id" in df.columns:
                    df, rejected = filter_company_foreign_keys(
                        df,
                        companies_df,
                        table_name=table_name,
                    )
                    rejected_rows = len(rejected)

                    if not rejected.empty:
                        rejected = rejected.copy()
                        rejected["_reason"] = "fk_orphan"
                        all_rejections.append(rejected)

            # Load to SQLite.
            loaded, load_rejected = load_to_sqlite(df, table_name)
            print(f"  Loaded: {loaded} rows")

            # Merge rejections from constraint failures.
            if load_rejected is not None and not load_rejected.empty:
                load_rejected = load_rejected.copy()
                load_rejected["_reason"] = "constraint"
                all_rejections.append(load_rejected)
                rejected_rows += len(load_rejected)
                print(f"  Rejected (constraints): {len(load_rejected)}")

            if rejected_rows > 0:
                print(f"  Total rejected   : {rejected_rows}")

            # Store companies df for FK filtering.
            if table_name == "companies":
                companies_df = df.copy()

            audit_rows.append(
                {
                    "table_name": table_name,
                    "source_file": file_path.name,
                    "source_rows": source_rows,
                    "loaded_rows": loaded,
                    "rejected_rows": rejected_rows,
                    "status": "OK",
                }
            )

        except Exception as e:
            print(f"  ERROR: {e}")
            audit_rows.append(
                {
                    "table_name": table_name,
                    "source_file": file_path.name,
                    "source_rows": 0,
                    "loaded_rows": 0,
                    "rejected_rows": 0,
                    "status": f"ERROR: {e}",
                }
            )

    # Step 3: FK check.
    print("\n[3/4] Running foreign key check...")
    violations = check_foreign_keys()

    if violations:
        print(f"  FK violations found: {len(violations)}")
        for v in violations[:10]:
            print(f"    {v}")
    else:
        print("  FK check: PASS (0 violations)")

    # Step 4: Row count verification.
    print("\n[4/4] Verifying row counts...")

    for row in audit_rows:
        if row["status"] == "OK":
            actual = get_row_count(row["table_name"])
            row["db_row_count"] = actual
            match = "OK" if actual == row["loaded_rows"] else "MISMATCH"
            print(
                f"  {row['table_name']:<20} expected={row['loaded_rows']:<6} actual={actual} [{match}]"
            )
        else:
            row["db_row_count"] = 0

    # Save audit.
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "table_name",
        "source_file",
        "source_rows",
        "loaded_rows",
        "rejected_rows",
        "db_row_count",
        "status",
    ]

    with open(AUDIT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    # Save rejection details (concat all rejected rows).
    if all_rejections:
        combined = pd.concat(
            all_rejections,
            ignore_index=True,
            sort=False,
        )
        combined.to_csv(
            REJECTION_FILE,
            index=False,
        )
        print(f"Rejection details : {REJECTION_FILE}")

    # Summary.
    print("\n" + "=" * 60)
    print("LOAD COMPLETE")
    print("=" * 60)

    total_loaded = sum(r["loaded_rows"] for r in audit_rows)
    total_rejected = sum(r["rejected_rows"] for r in audit_rows)

    print(f"Tables loaded   : {sum(1 for r in audit_rows if r['status'] == 'OK')}")
    print(f"Total rows loaded: {total_loaded}")
    print(f"Total rejected  : {total_rejected}")
    print(f"FK violations   : {len(violations)}")
    print(f"Database        : {DB_PATH}")
    print(f"Audit file      : {AUDIT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
