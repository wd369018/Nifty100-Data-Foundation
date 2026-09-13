import pandas as pd

from src.etl.validator import (
    make_failure,
    save_validation_failures,
    validate_balance_sheet,
    validate_company_id_format,
    validate_company_year_uniqueness,
    validate_dataframe,
    validate_duplicate_rows,
    validate_foreign_keys,
    validate_non_negative,
    validate_not_empty,
    validate_null_company_ids,
    validate_null_year,
    validate_numeric_columns,
    validate_opm,
    validate_pk_uniqueness,
    validate_positive_sales,
    validate_required_columns,
    validate_urls,
    validate_year_range,
)


def test_make_failure():
    failure = make_failure(
        "DQ-01",
        "companies",
        "CRITICAL",
        "id",
        1,
        "Duplicate primary key: 1",
    )

    assert failure["rule_id"] == "DQ-01"
    assert failure["table_name"] == "companies"
    assert failure["severity"] == "CRITICAL"
    assert failure["column_name"] == "id"
    assert failure["record_id"] == 1


def test_validate_pk_uniqueness_duplicate():
    df = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "name": ["a", "b", "c"],
        }
    )

    failures = validate_pk_uniqueness(df, "companies")

    assert len(failures) == 2
    assert all(f["rule_id"] == "DQ-01" for f in failures)


def test_validate_pk_uniqueness_clean():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
        }
    )

    assert validate_pk_uniqueness(df, "companies") == []


def test_validate_pk_uniqueness_missing_column():
    df = pd.DataFrame({"name": ["a"]})

    failures = validate_pk_uniqueness(df, "companies")

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-01"


def test_validate_company_year_uniqueness_duplicate():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "TCS"],
            "year": ["2024-03", "2024-03"],
        }
    )

    failures = validate_company_year_uniqueness(df, "profitandloss")

    assert len(failures) == 2
    assert all(f["rule_id"] == "DQ-02" for f in failures)


def test_validate_company_year_uniqueness_clean():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "TCS"],
            "year": ["2024-03", "2023-03"],
        }
    )

    assert validate_company_year_uniqueness(df, "profitandloss") == []


def test_validate_company_year_uniqueness_missing_columns():
    df = pd.DataFrame({"id": [1]})

    assert validate_company_year_uniqueness(df, "profitandloss") == []


def test_validate_foreign_keys_valid():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["tcs", " RELIANCE "],
        }
    )
    companies = pd.DataFrame({"id": ["TCS", "RELIANCE"]})

    failures = validate_foreign_keys(df, companies, "profitandloss", "companies")

    assert failures == []


def test_validate_foreign_keys_orphan():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": ["GHOST"],
        }
    )
    companies = pd.DataFrame({"id": ["TCS"]})

    failures = validate_foreign_keys(df, companies, "profitandloss", "companies")

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-03"
    assert "GHOST" in failures[0]["message"]


def test_validate_foreign_keys_null():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": [None],
        }
    )
    companies = pd.DataFrame({"id": ["TCS"]})

    failures = validate_foreign_keys(df, companies, "profitandloss", "companies")

    assert len(failures) == 1
    assert "Missing" in failures[0]["message"]


def test_validate_balance_sheet_balanced():
    df = pd.DataFrame(
        {
            "id": [1],
            "total_assets": [1000],
            "total_liabilities": [1005],
        }
    )

    assert validate_balance_sheet(df) == []


def test_validate_balance_sheet_mismatch():
    df = pd.DataFrame(
        {
            "id": [1],
            "total_assets": [1000],
            "total_liabilities": [1500],
        }
    )

    failures = validate_balance_sheet(df)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-04"


def test_validate_opm_matches():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": [1000],
            "operating_profit": [200],
            "opm_percentage": [20],
        }
    )

    assert validate_opm(df) == []


def test_validate_opm_mismatch():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": [1000],
            "operating_profit": [200],
            "opm_percentage": [99],
        }
    )

    failures = validate_opm(df)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-05"


def test_validate_positive_sales():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": [-5],
        }
    )

    failures = validate_positive_sales(df)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-06"


def test_validate_required_columns_missing():
    df = pd.DataFrame({"company_id": [1]})

    failures = validate_required_columns(df, "profitandloss", ["company_id", "year"])

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-07"
    assert failures[0]["column_name"] == "year"


def test_validate_null_company_ids():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": [None],
        }
    )

    failures = validate_null_company_ids(df, "cashflow")

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-08"


def test_validate_null_year():
    df = pd.DataFrame(
        {
            "id": [1],
            "year": [None],
        }
    )

    failures = validate_null_year(df, "profitandloss")

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-09"


def test_validate_numeric_columns_non_numeric():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": ["abc"],
        }
    )

    failures = validate_numeric_columns(df, "profitandloss", ["sales"])

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-10"


def test_validate_numeric_columns_clean():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": [100],
        }
    )

    assert validate_numeric_columns(df, "profitandloss", ["sales"]) == []


def test_validate_duplicate_rows():
    df = pd.DataFrame(
        {
            "id": [1, 1],
            "sales": [100, 100],
        }
    )

    failures = validate_duplicate_rows(df, "profitandloss")

    assert len(failures) == 2
    assert all(f["rule_id"] == "DQ-11" for f in failures)


def test_validate_year_range_out_of_range():
    df = pd.DataFrame(
        {
            "id": [1],
            "year": ["2999-03"],
        }
    )

    failures = validate_year_range(df, "profitandloss", maximum_year=2100)

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-12"


def test_validate_year_range_valid():
    df = pd.DataFrame(
        {
            "id": [1],
            "year": ["2024-03"],
        }
    )

    assert validate_year_range(df, "profitandloss") == []


def test_validate_urls_invalid():
    df = pd.DataFrame(
        {
            "id": [1],
            "website": ["not-a-url"],
        }
    )

    failures = validate_urls(df, "companies", ["website"])

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-13"


def test_validate_urls_valid():
    df = pd.DataFrame(
        {
            "id": [1],
            "website": ["https://www.example.com"],
        }
    )

    assert validate_urls(df, "companies", ["website"]) == []


def test_validate_non_negative():
    df = pd.DataFrame(
        {
            "id": [1],
            "total_assets": [-100],
        }
    )

    failures = validate_non_negative(df, "balancesheet", ["total_assets"])

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-14"


def test_validate_not_empty():
    assert validate_not_empty(pd.DataFrame(), "companies")

    df = pd.DataFrame({"id": [1]})
    assert validate_not_empty(df, "companies") == []


def test_validate_company_id_format_empty():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": ["   "],
        }
    )

    failures = validate_company_id_format(df, "cashflow")

    assert len(failures) == 1
    assert failures[0]["rule_id"] == "DQ-16"


def test_validate_dataframe_empty_df():
    failures = validate_dataframe(pd.DataFrame(), "companies")

    assert any(f["rule_id"] == "DQ-15" for f in failures)


def test_validate_dataframe_clean_company():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_name": ["a", "b"],
            "website": ["https://a.com", "https://b.com"],
        }
    )

    failures = validate_dataframe(df, "companies")

    assert failures == []


def test_validate_dataframe_balance_sheet_rule_applied():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": ["TCS"],
            "year": ["2024-03"],
            "total_assets": [1000],
            "total_liabilities": [5000],
        }
    )

    failures = validate_dataframe(df, "balancesheet")

    assert any(f["rule_id"] == "DQ-04" for f in failures)


def test_save_validation_failures_creates_file(tmp_path):
    failures = [make_failure("DQ-01", "companies", "CRITICAL", "id", 1, "dup")]

    output = tmp_path / "validation_failures.csv"

    save_validation_failures(failures, output)

    df = pd.read_csv(output)

    assert len(df) == 1
    assert df.loc[0, "rule_id"] == "DQ-01"


def test_save_validation_failures_empty(tmp_path):
    output = tmp_path / "validation_failures.csv"

    save_validation_failures([], output)

    df = pd.read_csv(output)

    assert df.empty
