"""
Excel data loader for the Nifty100 Data Foundation project.
"""

from pathlib import Path

import pandas as pd

from src.etl.normaliser import normalize_year

SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}

# Tables deduplicated on the (company_id, year) natural key.
SUBKEY_TABLES = {
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
    "documents",
    "market_cap",
}


def load_excel(file_path, sheet_name=0):
    """
    Load an Excel file into a pandas DataFrame.

    Raw source workbooks contain a title row before the actual
    column headers, while supporting files have headers in row 1.

    Parameters:
        file_path (str | Path):
            Path to Excel file.

        sheet_name (str | int):
            Excel sheet name or sheet index.

    Returns:
        pandas.DataFrame:
            Loaded and cleaned DataFrame.

    Raises:
        FileNotFoundError:
            If the Excel file does not exist.

        ValueError:
            If the file is not an Excel file.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only Excel files (.xlsx, .xls) are supported.")

    # Raw files have a title row before the headers.
    # Supporting files have headers in the first row.
    if "data\\raw" in str(file_path).lower() or "data/raw" in str(file_path).lower():
        header_row = 1
    else:
        header_row = 0

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name,
        header=header_row,
    )

    # Remove completely empty rows.
    df = df.dropna(how="all").reset_index(drop=True)

    # Normalize column names.
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )

    return df


def normalize_year_column(df):
    """
    Normalize the 'year' column in a DataFrame using normalize_year().

    Parameters:
        df (pandas.DataFrame):
            DataFrame potentially containing a 'year' column.

    Returns:
        pandas.DataFrame:
            DataFrame with normalized year values.
    """

    if "year" in df.columns:
        df["year"] = df["year"].apply(normalize_year)

    return df


def deduplicate(df, table_name):
    """
    Remove duplicate rows from a DataFrame.

    For tables with a natural (company_id, year) key, deduplicate on
    that key. For all tables, remove completely identical rows.

    Parameters:
        df (pandas.DataFrame):
            DataFrame to deduplicate.

        table_name (str):
            Name of the table for context.

    Returns:
        pandas.DataFrame:
            Deduplicated DataFrame.
    """

    before = len(df)

    if (
        table_name in SUBKEY_TABLES
        and "company_id" in df.columns
        and "year" in df.columns
    ):
        df = df.drop_duplicates(
            subset=["company_id", "year"],
            keep="first",
        ).reset_index(drop=True)
    else:
        df = df.drop_duplicates(
            keep="first",
        ).reset_index(drop=True)

    after = len(df)

    if before != after:
        print(
            f"  Dedup {table_name}: "
            f"{before} -> {after} "
            f"(-{before - after} rows)"
        )

    return df


def filter_valid_company_ids(df, companies_df):
    """
    Filter child-table rows using the companies master.

    Rows whose company_id exists in companies_df['id'] are kept.
    Rows whose company_id does not exist are returned separately
    as rejected rows.

    Raw source data is never modified.

    Parameters:
        df (pandas.DataFrame):
            Child-table DataFrame containing company_id.

        companies_df (pandas.DataFrame):
            Master companies DataFrame containing id.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]:
            valid_rows, rejected_rows

    Raises:
        ValueError:
            If required identifier columns are missing.
    """

    if "company_id" not in df.columns:
        raise ValueError("Child dataframe must contain 'company_id' column.")

    if "id" not in companies_df.columns:
        raise ValueError("Companies master must contain 'id' column.")

    # Normalize master company IDs for comparison.
    valid_ids = companies_df["id"].dropna().astype(str).str.strip().str.upper()

    # Normalize child company IDs for comparison.
    child_ids = df["company_id"].astype(str).str.strip().str.upper()

    valid_mask = child_ids.isin(set(valid_ids))

    # Valid records.
    valid_rows = df.loc[valid_mask].copy()

    # Orphan/invalid records.
    rejected_rows = df.loc[~valid_mask].copy()

    return (
        valid_rows.reset_index(drop=True),
        rejected_rows.reset_index(drop=True),
    )


def get_excel_sheets(file_path):
    """
    Return all sheet names from an Excel workbook.

    Parameters:
        file_path (str | Path):
            Path to Excel file.

    Returns:
        list[str]:
            Names of all worksheets.

    Raises:
        FileNotFoundError:
            If the Excel file does not exist.

        ValueError:
            If the file is not an Excel file.
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only Excel files (.xlsx, .xls) are supported.")

    excel_file = pd.ExcelFile(file_path)

    return excel_file.sheet_names
