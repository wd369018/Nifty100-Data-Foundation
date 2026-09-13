import pandas as pd
import pytest

from src.etl.loader import (
    deduplicate,
    get_excel_sheets,
    load_excel,
    normalize_year_column,
)


def test_load_excel(tmp_path):
    """
    Test that an Excel file is loaded correctly.
    """

    file_path = tmp_path / "sample.xlsx"

    df = pd.DataFrame(
        {
            "Company Name": ["Reliance", "TCS"],
            "Ticker Symbol": ["RELIANCE", "TCS"],
            "Revenue": [1000, 2000],
        }
    )

    df.to_excel(file_path, index=False)

    result = load_excel(file_path)

    assert len(result) == 2
    assert list(result.columns) == [
        "company_name",
        "ticker_symbol",
        "revenue",
    ]


def test_load_excel_removes_empty_rows(tmp_path):
    """
    Test that completely empty rows are removed.
    """

    file_path = tmp_path / "sample.xlsx"

    df = pd.DataFrame(
        {
            "Company Name": ["Reliance", None, "TCS"],
            "Revenue": [1000, None, 2000],
        }
    )

    df.to_excel(file_path, index=False)

    result = load_excel(file_path)

    assert len(result) == 2


def test_load_excel_normalizes_column_names(tmp_path):
    """
    Test column-name normalization.
    """

    file_path = tmp_path / "sample.xlsx"

    df = pd.DataFrame(
        {
            " Company Name ": ["Reliance"],
            "Profit & Loss": [500],
            "Financial Year": [2024],
        }
    )

    df.to_excel(file_path, index=False)

    result = load_excel(file_path)

    assert "company_name" in result.columns
    assert "profit_&_loss" in result.columns
    assert "financial_year" in result.columns


def test_load_excel_file_not_found():
    """
    Test missing Excel file handling.
    """

    with pytest.raises(FileNotFoundError):
        load_excel("data/raw/missing_file.xlsx")


def test_load_excel_invalid_extension(tmp_path):
    """
    Test invalid file extension handling.
    """

    file_path = tmp_path / "sample.csv"

    file_path.write_text("company,revenue\nTCS,1000")

    with pytest.raises(ValueError):
        load_excel(file_path)


def test_get_excel_sheets(tmp_path):
    """
    Test retrieving worksheet names.
    """

    file_path = tmp_path / "multi_sheet.xlsx"

    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame({"Company": ["TCS"]}).to_excel(
            writer,
            sheet_name="Companies",
            index=False,
        )

        pd.DataFrame({"Revenue": [1000]}).to_excel(
            writer,
            sheet_name="Financials",
            index=False,
        )

    sheets = get_excel_sheets(file_path)

    assert sheets == [
        "Companies",
        "Financials",
    ]


def test_get_excel_sheets_file_not_found():
    """
    Test missing workbook handling.
    """

    with pytest.raises(FileNotFoundError):
        get_excel_sheets("data/raw/missing.xlsx")


def test_normalize_year_column_raw_format():
    """
    Test that raw Excel year formats are normalized.
    """

    df = pd.DataFrame(
        {
            "year": ["Mar 2024", "Mar-23", "FY24"],
        }
    )

    result = normalize_year_column(df)

    assert list(result["year"]) == [
        "2024-03",
        "2023-03",
        "2024-03",
    ]


def test_normalize_year_column_keeps_other_columns():
    """
    Test that normalization only touches the year column.
    """

    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "TCS"],
            "year": ["Mar 2024", "Mar 2023"],
        }
    )

    result = normalize_year_column(df)

    assert list(result["company_id"]) == ["TCS", "TCS"]
    assert list(result["year"]) == ["2024-03", "2023-03"]


def test_normalize_year_column_missing_year():
    """
    Test that a dataframe without a year column is unchanged.
    """

    df = pd.DataFrame({"id": [1], "name": ["TCS"]})

    result = normalize_year_column(df)

    assert result.equals(df)


def test_deduplicate_full_rows():
    """
    Test removing completely identical rows.
    """

    df = pd.DataFrame(
        {
            "id": [1, 1],
            "company_id": ["TCS", "TCS"],
        }
    )

    result = deduplicate(df, "analysis")

    assert len(result) == 1


def test_deduplicate_subkey_table():
    """
    Test deduplication on (company_id, year) for time-series tables.
    """

    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "company_id": ["TCS", "TCS", "TCS"],
            "year": ["2024-03", "2024-03", "2023-03"],
        }
    )

    result = deduplicate(df, "profitandloss")

    assert len(result) == 2


def test_deduplicate_subkey_table_keeps_other_rows():
    """
    Test that rows with different company/year combinations survive.
    """

    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "RELIANCE"],
            "year": ["2024-03", "2024-03"],
        }
    )

    result = deduplicate(df, "cashflow")

    assert len(result) == 2


def test_deduplicate_non_subkey_table():
    """
    Test that non-subkey tables only drop identical rows.
    """

    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "TCS"],
            "year": ["2024-03", "2024-03"],
            "name": ["A", "B"],
        }
    )

    # Same company/year but different other data is kept.
    result = deduplicate(df, "sectors")

    assert len(result) == 2


# ============================================================
# File-based checks: loader reads the correct row counts and
# column names for every raw + supporting workbook (Day 41).
# ============================================================

import glob
import sqlite3

RAW_FILES = {
    "companies": {
        "glob": "data/raw/*companies.xlsx",
        "required": ["id", "company_name", "roce_percentage", "roe_percentage"],
    },
    "profitandloss": {
        "glob": "data/raw/*profitandloss.xlsx",
        "required": [
            "company_id",
            "year",
            "sales",
            "net_profit",
            "operating_profit",
            "opm_percentage",
        ],
    },
    "balancesheet": {
        "glob": "data/raw/*balancesheet.xlsx",
        "required": [
            "company_id",
            "year",
            "equity_capital",
            "reserves",
            "borrowings",
            "total_assets",
            "total_liabilities",
        ],
    },
    "cashflow": {
        "glob": "data/raw/*cashflow.xlsx",
        "required": [
            "company_id",
            "year",
            "operating_activity",
            "investing_activity",
            "financing_activity",
            "net_cash_flow",
        ],
    },
    "documents": {
        "glob": "data/raw/*documents.xlsx",
        "required": ["company_id", "year", "annual_report"],
    },
}

SUPPORTING_FILES = {
    "financial_ratios": {
        "glob": "data/supporting/*financial_ratios.xlsx",
        "required": [
            "company_id",
            "year",
            "return_on_equity_pct",
            "debt_to_equity",
            "operating_profit_margin_pct",
        ],
    },
    "market_cap": {
        "glob": "data/supporting/*market_cap.xlsx",
        "required": [
            "company_id",
            "year",
            "pe_ratio",
            "pb_ratio",
            "ev_ebitda",
        ],
    },
    "peer_groups": {
        "glob": "data/supporting/*peer_groups.xlsx",
        "required": ["peer_group_name", "company_id", "is_benchmark"],
    },
    "sectors": {
        "glob": "data/supporting/*sectors.xlsx",
        "required": ["company_id", "broad_sector", "sub_sector"],
    },
    "stock_prices": {
        "glob": "data/supporting/*stock_prices.xlsx",
        "required": [
            "company_id",
            "date",
            "open_price",
            "close_price",
        ],
    },
}


def _db_count(table):
    conn = sqlite3.connect("db/nifty100.db")
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _find(glob_pattern):
    matches = glob.glob(glob_pattern)
    assert matches, f"No source file found for {glob_pattern}"
    return matches[0]


@pytest.mark.parametrize("table", sorted(RAW_FILES))
def test_raw_file_rowcount_ge_db(table):
    config = RAW_FILES[table]
    df = load_excel(_find(config["glob"]))
    assert len(df) > 0
    assert len(df) >= _db_count(table)


@pytest.mark.parametrize("table", sorted(RAW_FILES))
def test_raw_file_columns(table):
    config = RAW_FILES[table]
    df = load_excel(_find(config["glob"]))
    for col in config["required"]:
        assert col in df.columns, f"{table} missing column {col}"


@pytest.mark.parametrize("table", sorted(SUPPORTING_FILES))
def test_supporting_file_rowcount_ge_db(table):
    config = SUPPORTING_FILES[table]
    df = load_excel(_find(config["glob"]))
    assert len(df) > 0
    assert len(df) >= _db_count(table)


@pytest.mark.parametrize("table", sorted(SUPPORTING_FILES))
def test_supporting_file_columns(table):
    config = SUPPORTING_FILES[table]
    df = load_excel(_find(config["glob"]))
    for col in config["required"]:
        assert col in df.columns, f"{table} missing column {col}"
