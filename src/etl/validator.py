"""
Data quality validator for the Nifty100 Data Foundation project.
"""

from pathlib import Path

import pandas as pd

SEVERITIES = {
    "CRITICAL": "CRITICAL",
    "WARNING": "WARNING",
}


def make_failure(
    rule_id,
    table_name,
    severity,
    column_name,
    record_id,
    message,
):
    """Create a standardized validation failure record."""
    return {
        "rule_id": rule_id,
        "table_name": table_name,
        "severity": severity,
        "column_name": column_name,
        "record_id": record_id,
        "message": message,
    }


# ============================================================
# DQ-01 — Primary Key Uniqueness
# ============================================================


def validate_pk_uniqueness(df, table_name, pk_column="id"):
    """Validate that the primary-key column contains no duplicates."""
    failures = []

    if pk_column not in df.columns:
        failures.append(
            make_failure(
                "DQ-01",
                table_name,
                "CRITICAL",
                pk_column,
                None,
                f"Missing primary-key column: {pk_column}",
            )
        )
        return failures

    duplicates = df[df[pk_column].duplicated(keep=False)]

    for _, row in duplicates.iterrows():
        failures.append(
            make_failure(
                "DQ-01",
                table_name,
                "CRITICAL",
                pk_column,
                row.get(pk_column),
                f"Duplicate primary key: {row.get(pk_column)}",
            )
        )

    return failures


# ============================================================
# DQ-02 — Company + Year Uniqueness
# ============================================================


def validate_company_year_uniqueness(
    df,
    table_name,
    company_column="company_id",
    year_column="year",
):
    """Validate company/year uniqueness for time-series tables."""
    failures = []

    required = {company_column, year_column}

    if not required.issubset(df.columns):
        return failures

    duplicates = df[
        df.duplicated(
            subset=[company_column, year_column],
            keep=False,
        )
    ]

    for _, row in duplicates.iterrows():
        failures.append(
            make_failure(
                "DQ-02",
                table_name,
                "CRITICAL",
                f"{company_column},{year_column}",
                row.get("id"),
                (
                    "Duplicate company/year combination: "
                    f"{row.get(company_column)} / "
                    f"{row.get(year_column)}"
                ),
            )
        )

    return failures


# ============================================================
# DQ-03 — Foreign Key Integrity
# ============================================================


def validate_foreign_keys(
    df,
    reference_df,
    table_name,
    reference_table,
    company_column="company_id",
    reference_column="id",
):
    """Validate company_id values against the companies master table."""
    failures = []

    if company_column not in df.columns:
        return failures

    if reference_column not in reference_df.columns:
        return failures

    valid_ids = set(
        reference_df[reference_column].dropna().astype(str).str.strip().str.upper()
    )

    for _, row in df.iterrows():
        value = row.get(company_column)

        if pd.isna(value):
            failures.append(
                make_failure(
                    "DQ-03",
                    table_name,
                    "CRITICAL",
                    company_column,
                    row.get("id"),
                    "Missing foreign-key company_id.",
                )
            )
            continue

        company_id = str(value).strip().upper()

        if company_id not in valid_ids:
            failures.append(
                make_failure(
                    "DQ-03",
                    table_name,
                    "CRITICAL",
                    company_column,
                    row.get("id"),
                    (
                        f"Invalid company_id '{company_id}'. "
                        f"Not found in {reference_table}."
                    ),
                )
            )

    return failures


# ============================================================
# DQ-04 — Balance Sheet Equation
# ============================================================


def validate_balance_sheet(df, tolerance_pct=1.0):
    """
    Validate that total assets approximately equal
    total liabilities.
    """
    failures = []

    required = {
        "total_assets",
        "total_liabilities",
    }

    if not required.issubset(df.columns):
        return failures

    for _, row in df.iterrows():

        assets = pd.to_numeric(
            row["total_assets"],
            errors="coerce",
        )

        liabilities = pd.to_numeric(
            row["total_liabilities"],
            errors="coerce",
        )

        if pd.isna(assets) or pd.isna(liabilities):
            continue

        if assets == 0:
            continue

        difference_pct = (abs(assets - liabilities) / abs(assets)) * 100

        if difference_pct > tolerance_pct:
            failures.append(
                make_failure(
                    "DQ-04",
                    "balancesheet",
                    "CRITICAL",
                    "total_assets,total_liabilities",
                    row.get("id"),
                    (
                        f"Balance mismatch: "
                        f"assets={assets}, "
                        f"liabilities={liabilities}, "
                        f"difference={difference_pct:.2f}%"
                    ),
                )
            )

    return failures


# ============================================================
# DQ-05 — OPM Calculation
# ============================================================


def validate_opm(df, tolerance_pct=1.0):
    """Validate reported OPM against calculated OPM."""
    failures = []

    required = {
        "sales",
        "operating_profit",
        "opm_percentage",
    }

    if not required.issubset(df.columns):
        return failures

    for _, row in df.iterrows():

        sales = pd.to_numeric(
            row["sales"],
            errors="coerce",
        )

        operating_profit = pd.to_numeric(
            row["operating_profit"],
            errors="coerce",
        )

        reported_opm = pd.to_numeric(
            row["opm_percentage"],
            errors="coerce",
        )

        if pd.isna(sales) or pd.isna(operating_profit):
            continue

        if pd.isna(reported_opm) or sales == 0:
            continue

        calculated_opm = (operating_profit / sales) * 100

        if abs(calculated_opm - reported_opm) > tolerance_pct:
            failures.append(
                make_failure(
                    "DQ-05",
                    "profitandloss",
                    "WARNING",
                    "opm_percentage",
                    row.get("id"),
                    (
                        f"OPM mismatch: "
                        f"reported={reported_opm:.2f}%, "
                        f"calculated={calculated_opm:.2f}%"
                    ),
                )
            )

    return failures


# ============================================================
# DQ-06 — Positive Sales
# ============================================================


def validate_positive_sales(df):
    """Validate that sales values are positive."""
    failures = []

    if "sales" not in df.columns:
        return failures

    for _, row in df.iterrows():

        sales = pd.to_numeric(
            row["sales"],
            errors="coerce",
        )

        if pd.isna(sales):
            continue

        if sales <= 0:
            failures.append(
                make_failure(
                    "DQ-06",
                    "profitandloss",
                    "WARNING",
                    "sales",
                    row.get("id"),
                    f"Sales must be positive: {sales}",
                )
            )

    return failures


# ============================================================
# DQ-07 — Required Columns
# ============================================================


def validate_required_columns(
    df,
    table_name,
    required_columns,
):
    """Validate that all required columns exist."""
    failures = []

    for column in required_columns:

        if column not in df.columns:
            failures.append(
                make_failure(
                    "DQ-07",
                    table_name,
                    "CRITICAL",
                    column,
                    None,
                    f"Required column missing: {column}",
                )
            )

    return failures


# ============================================================
# DQ-08 — Null Company IDs
# ============================================================


def validate_null_company_ids(df, table_name):
    """Validate that company_id is not null."""
    failures = []

    if "company_id" not in df.columns:
        return failures

    null_rows = df[df["company_id"].isna()]

    for _, row in null_rows.iterrows():
        failures.append(
            make_failure(
                "DQ-08",
                table_name,
                "CRITICAL",
                "company_id",
                row.get("id"),
                "company_id cannot be null.",
            )
        )

    return failures


# ============================================================
# DQ-09 — Null Year
# ============================================================


def validate_null_year(df, table_name):
    """Validate that year is not null in time-series tables."""
    failures = []

    if "year" not in df.columns:
        return failures

    null_rows = df[df["year"].isna()]

    for _, row in null_rows.iterrows():
        failures.append(
            make_failure(
                "DQ-09",
                table_name,
                "CRITICAL",
                "year",
                row.get("id"),
                "Year cannot be null.",
            )
        )

    return failures


# ============================================================
# DQ-10 — Numeric Columns
# ============================================================


def validate_numeric_columns(
    df,
    table_name,
    numeric_columns,
):
    """Validate numeric fields."""
    failures = []

    for column in numeric_columns:

        if column not in df.columns:
            continue

        converted = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        invalid = df[column].notna() & converted.isna()

        for index in df[invalid].index:

            failures.append(
                make_failure(
                    "DQ-10",
                    table_name,
                    "WARNING",
                    column,
                    df.loc[index].get("id"),
                    (
                        f"Non-numeric value found in "
                        f"{column}: {df.loc[index][column]}"
                    ),
                )
            )

    return failures


# ============================================================
# DQ-11 — Duplicate Rows
# ============================================================


def validate_duplicate_rows(df, table_name):
    """Detect completely duplicated rows."""
    failures = []

    duplicates = df[df.duplicated(keep=False)]

    for _, row in duplicates.iterrows():

        failures.append(
            make_failure(
                "DQ-11",
                table_name,
                "WARNING",
                "*",
                row.get("id"),
                "Completely duplicated row detected.",
            )
        )

    return failures


# ============================================================
# DQ-12 — Year Range
# ============================================================


def validate_year_range(
    df,
    table_name,
    minimum_year=1900,
    maximum_year=2100,
):
    """Validate year values."""
    failures = []

    if "year" not in df.columns:
        return failures

    for _, row in df.iterrows():

        year = row.get("year")

        if pd.isna(year):
            continue

        year_text = str(year)

        digits = "".join(character for character in year_text if character.isdigit())

        if not digits:
            continue

        year_number = int(digits[:4])

        if not (minimum_year <= year_number <= maximum_year):
            failures.append(
                make_failure(
                    "DQ-12",
                    table_name,
                    "WARNING",
                    "year",
                    row.get("id"),
                    f"Year outside valid range: {year}",
                )
            )

    return failures


# ============================================================
# DQ-13 — URL Format
# ============================================================


def validate_urls(
    df,
    table_name,
    url_columns,
):
    """Validate URL fields using a basic format check."""
    failures = []

    for column in url_columns:

        if column not in df.columns:
            continue

        for _, row in df.iterrows():

            value = row.get(column)

            if pd.isna(value) or str(value).strip() == "":
                continue

            value = str(value).strip().lower()

            if not (value.startswith("http://") or value.startswith("https://")):
                failures.append(
                    make_failure(
                        "DQ-13",
                        table_name,
                        "WARNING",
                        column,
                        row.get("id"),
                        f"Invalid URL format: {value}",
                    )
                )

    return failures


# ============================================================
# DQ-14 — Negative Values
# ============================================================


def validate_non_negative(
    df,
    table_name,
    columns,
):
    """Detect negative values where negatives are not expected."""
    failures = []

    for column in columns:

        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        negative_rows = df[values < 0]

        for _, row in negative_rows.iterrows():

            failures.append(
                make_failure(
                    "DQ-14",
                    table_name,
                    "WARNING",
                    column,
                    row.get("id"),
                    (f"Negative value detected " f"in {column}: {row.get(column)}"),
                )
            )

    return failures


# ============================================================
# DQ-15 — Empty DataFrame
# ============================================================


def validate_not_empty(df, table_name):
    """Validate that a source table contains records."""
    failures = []

    if df.empty:
        failures.append(
            make_failure(
                "DQ-15",
                table_name,
                "CRITICAL",
                "*",
                None,
                "Table contains no records.",
            )
        )

    return failures


# ============================================================
# DQ-16 — Identifier Format
# ============================================================


def validate_company_id_format(
    df,
    table_name,
):
    """Validate company identifier formatting."""
    failures = []

    if "company_id" not in df.columns:
        return failures

    for _, row in df.iterrows():

        value = row.get("company_id")

        if pd.isna(value):
            continue

        value = str(value).strip()

        if value == "":
            failures.append(
                make_failure(
                    "DQ-16",
                    table_name,
                    "WARNING",
                    "company_id",
                    row.get("id"),
                    "Empty company_id.",
                )
            )

    return failures


# ============================================================
# MASTER VALIDATOR
# ============================================================


def validate_dataframe(
    df,
    table_name,
    reference_df=None,
):
    """Run all applicable data-quality rules for a dataframe."""

    failures = []

    # ============================================================
    # DQ-15 — Table must not be empty
    # ============================================================
    failures.extend(
        validate_not_empty(
            df,
            table_name,
        )
    )

    # ============================================================
    # DQ-01 — Primary Key Uniqueness
    # ============================================================
    if "id" in df.columns:
        failures.extend(
            validate_pk_uniqueness(
                df,
                table_name,
            )
        )

    # ============================================================
    # Time-series tables
    # ============================================================
    time_series_tables = {
        "profitandloss",
        "balancesheet",
        "cashflow",
        "financial_ratios",
        "stock_prices",
    }

    # ============================================================
    # DQ-02 — Company + Year uniqueness
    # ============================================================
    if (
        table_name in time_series_tables
        and "company_id" in df.columns
        and "year" in df.columns
    ):
        failures.extend(
            validate_company_year_uniqueness(
                df,
                table_name,
            )
        )

    # ============================================================
    # DQ-07 — Required Columns
    # ============================================================
    required_columns_map = {
        "companies": ["id"],
        "profitandloss": ["company_id", "year"],
        "balancesheet": ["company_id", "year"],
        "cashflow": ["company_id", "year"],
        "financial_ratios": ["company_id", "year"],
        "stock_prices": ["company_id"],
    }

    if table_name in required_columns_map:
        failures.extend(
            validate_required_columns(
                df,
                table_name,
                required_columns_map[table_name],
            )
        )

    # ============================================================
    # DQ-08 — Null Company IDs
    # ============================================================
    if "company_id" in df.columns:
        failures.extend(
            validate_null_company_ids(
                df,
                table_name,
            )
        )

    # ============================================================
    # DQ-16 — Company ID Format
    # ============================================================
    if "company_id" in df.columns:
        failures.extend(
            validate_company_id_format(
                df,
                table_name,
            )
        )

    # ============================================================
    # DQ-03 — Foreign Key Integrity
    # ============================================================
    # companies table khud companies master hai,
    # isliye uspar FK validation nahi chalega.
    if (
        reference_df is not None
        and table_name != "companies"
        and "company_id" in df.columns
    ):
        failures.extend(
            validate_foreign_keys(
                df,
                reference_df,
                table_name,
                "companies",
            )
        )

    # ============================================================
    # DQ-09 — Null Year
    # ============================================================
    if table_name in time_series_tables and "year" in df.columns:
        failures.extend(
            validate_null_year(
                df,
                table_name,
            )
        )

    # ============================================================
    # DQ-12 — Year Range
    # ============================================================
    if "year" in df.columns:
        failures.extend(
            validate_year_range(
                df,
                table_name,
            )
        )

    # ============================================================
    # DQ-10 — Numeric Column Validation
    # ============================================================
    numeric_columns_map = {
        "profitandloss": [
            "sales",
            "expenses",
            "operating_profit",
            "opm_percentage",
            "net_profit",
            "eps",
        ],
        "balancesheet": [
            "total_assets",
            "total_liabilities",
        ],
        "cashflow": [
            "cash_from_operating_activity",
            "cash_from_investing_activity",
            "cash_from_financing_activity",
        ],
    }

    if table_name in numeric_columns_map:
        failures.extend(
            validate_numeric_columns(
                df,
                table_name,
                numeric_columns_map[table_name],
            )
        )

    # ============================================================
    # DQ-11 — Duplicate Complete Rows
    # ============================================================
    failures.extend(
        validate_duplicate_rows(
            df,
            table_name,
        )
    )

    # ============================================================
    # DQ-13 — URL Validation
    # ============================================================
    possible_url_columns = [
        column
        for column in df.columns
        if "url" in column.lower()
        or "website" in column.lower()
        or "link" in column.lower()
    ]

    if possible_url_columns:
        failures.extend(
            validate_urls(
                df,
                table_name,
                possible_url_columns,
            )
        )

    # ============================================================
    # DQ-14 — Negative Values
    # ============================================================
    non_negative_map = {
        "profitandloss": [
            "sales",
        ],
        "balancesheet": [
            "total_assets",
            "total_liabilities",
        ],
    }

    if table_name in non_negative_map:
        failures.extend(
            validate_non_negative(
                df,
                table_name,
                non_negative_map[table_name],
            )
        )

    # ============================================================
    # Table-specific validations
    # ============================================================

    # DQ-04 — Balance Sheet Equation
    if table_name == "balancesheet":
        failures.extend(validate_balance_sheet(df))

    # DQ-05 — OPM Cross Check
    if table_name == "profitandloss":
        failures.extend(validate_opm(df))

    # DQ-06 — Positive Sales
    if table_name == "profitandloss":
        failures.extend(validate_positive_sales(df))

    return failures


# ============================================================
# SAVE RESULTS
# ============================================================


def save_validation_failures(
    failures,
    output_path="output/validation_failures.csv",
):
    """Save validation failures to CSV."""

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    columns = [
        "rule_id",
        "table_name",
        "severity",
        "column_name",
        "record_id",
        "message",
    ]

    if not failures:

        pd.DataFrame(columns=columns).to_csv(
            output_path,
            index=False,
        )

        return

    pd.DataFrame(failures).reindex(columns=columns).to_csv(
        output_path,
        index=False,
    )
