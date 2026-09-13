"""
Run data-quality validation across all Nifty100 source Excel files.
"""

import sys
from pathlib import Path

# Allow running as `python scripts/run_validation.py` directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.loader import load_excel, normalize_year_column
from src.etl.validator import (
    save_validation_failures,
    validate_dataframe,
)

RAW_DIR = Path("data/raw")
SUPPORTING_DIR = Path("data/supporting")
OUTPUT_FILE = Path("output/validation_failures.csv")


def main():
    """Validate all available Excel source files."""

    failures = []
    processed_files = 0

    all_files = []

    if RAW_DIR.exists():
        all_files.extend(sorted(RAW_DIR.glob("*.xlsx")))

    if SUPPORTING_DIR.exists():
        all_files.extend(sorted(SUPPORTING_DIR.glob("*.xlsx")))

    if not all_files:
        print("ERROR: No Excel files found.")
        return

    # Load companies master first for FK validation.
    companies_file = None

    for f in all_files:
        if "companies" in f.stem.lower():
            companies_file = f
            break

    companies_df = None

    if companies_file and companies_file.exists():
        companies_df = load_excel(companies_file)
        print(f"Loaded companies master: " f"{len(companies_df)} rows")

    for file_path in all_files:

        table_name = file_path.stem

        # Extract the short table name from the filename.
        for part in table_name.split("-"):
            if part.lower() in {
                "companies",
                "profitandloss",
                "balancesheet",
                "cashflow",
                "analysis",
                "documents",
                "prosandcons",
                "financial_ratios",
                "market_cap",
                "peer_groups",
                "sectors",
                "stock_prices",
            }:
                table_name = part.lower()
                break

        print(f"\nValidating: {file_path}")

        try:
            df = load_excel(file_path)

            # Normalize year columns before validation.
            df = normalize_year_column(df)

            file_failures = validate_dataframe(
                df,
                table_name,
                reference_df=companies_df,
            )

            failures.extend(file_failures)

            processed_files += 1

            critical = sum(item["severity"] == "CRITICAL" for item in file_failures)

            warning = sum(item["severity"] == "WARNING" for item in file_failures)

            print(f"  Rows     : {len(df)}")

            print(f"  Failures : {len(file_failures)}")

            print(f"  CRITICAL : {critical}")

            print(f"  WARNING  : {warning}")

        except Exception as exc:

            print(f"  ERROR: {exc}")

    save_validation_failures(
        failures,
        OUTPUT_FILE,
    )

    total_critical = sum(item["severity"] == "CRITICAL" for item in failures)

    total_warning = sum(item["severity"] == "WARNING" for item in failures)

    print("\n" + "=" * 55)
    print("NIFTY100 DATA QUALITY VALIDATION")
    print("=" * 55)

    print(f"Files processed : {processed_files}")

    print(f"Total failures  : {len(failures)}")

    print(f"CRITICAL        : {total_critical}")

    print(f"WARNING         : {total_warning}")

    print(f"Output          : {OUTPUT_FILE}")

    print("=" * 55)


if __name__ == "__main__":
    main()
