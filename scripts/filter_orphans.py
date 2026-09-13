"""
Filter orphan company_id records from Nifty100 child tables.

Valid records are kept.
Records whose company_id does not exist in companies.xlsx
are rejected and saved in an audit file.
"""

import sys
from pathlib import Path

import pandas as pd

# Allow running as `python scripts/filter_orphans.py` directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.fk_filter import filter_company_foreign_keys
from src.etl.loader import load_excel

RAW_DIR = Path("data/raw")
SUPPORTING_DIR = Path("data/supporting")

OUTPUT_FILE = Path("output/fk_rejections.csv")
SUMMARY_FILE = Path("output/fk_rejection_summary.csv")


def find_companies_file():
    """Locate the companies master Excel file."""

    if not RAW_DIR.exists():
        return None

    for f in RAW_DIR.glob("*.xlsx"):
        if "companies" in f.stem.lower():
            return f

    return None


def main():
    companies_file = find_companies_file()

    if companies_file is None:
        print("ERROR: companies.xlsx not found in data/raw.")
        return

    companies_df = load_excel(companies_file)

    all_files = []

    if RAW_DIR.exists():
        all_files.extend(sorted(RAW_DIR.glob("*.xlsx")))

    if SUPPORTING_DIR.exists():
        all_files.extend(sorted(SUPPORTING_DIR.glob("*.xlsx")))

    rejected_records = []
    summary = []

    for file_path in all_files:
        table_name = file_path.stem

        # companies.xlsx is the master table, so skip it.
        if table_name == "companies":
            continue

        df = load_excel(file_path)

        # Only child tables containing company_id need FK filtering.
        if "company_id" not in df.columns:
            continue

        valid_rows, rejected_rows = filter_company_foreign_keys(
            df,
            companies_df,
            table_name=table_name,
        )

        summary.append(
            {
                "table_name": table_name,
                "source_rows": len(df),
                "valid_rows": len(valid_rows),
                "rejected_rows": len(rejected_rows),
            }
        )

        if not rejected_rows.empty:
            rejected_records.append(rejected_rows)

        print(
            f"{table_name:<20} "
            f"source={len(df):<5} "
            f"valid={len(valid_rows):<5} "
            f"rejected={len(rejected_rows)}"
        )

    # Save all rejected rows.
    if rejected_records:
        rejection_df = pd.concat(
            rejected_records,
            ignore_index=True,
        )
    else:
        rejection_df = pd.DataFrame(
            columns=[
                "table_name",
                "rejection_reason",
                "company_id",
            ]
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    rejection_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    pd.DataFrame(summary).to_csv(
        SUMMARY_FILE,
        index=False,
    )

    print("\n" + "=" * 60)
    print("DQ-03 FOREIGN KEY FILTER")
    print("=" * 60)
    print(f"Total rejected rows : {len(rejection_df)}")
    print(f"Rejection audit     : {OUTPUT_FILE}")
    print(f"Summary             : {SUMMARY_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
