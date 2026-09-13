"""14 DQ rule tests — one per rule, each violating exactly that rule.

Sprint 6, Day 41 deliverable (tests/dq/test_rules.py).
"""

import pandas as pd

from src.etl.validator import (
    validate_balance_sheet,
    validate_company_year_uniqueness,
    validate_dataframe,
    validate_duplicate_rows,
    validate_foreign_keys,
    validate_non_negative,
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


def _failure(rule_id, severity, failures):
    assert failures, "expected failures to be non-empty"
    assert failures[0]["rule_id"] == rule_id
    assert failures[0]["severity"] == severity


def test_dq01_pk_uniqueness():
    df = pd.DataFrame({"id": ["A", "A", "B"], "name": ["x", "x", "y"]})
    failures = validate_pk_uniqueness(df, "companies")
    _failure("DQ-01", "CRITICAL", failures)


def test_dq02_company_year_uniqueness():
    df = pd.DataFrame({"company_id": ["TCS", "TCS"], "year": ["2024-03", "2024-03"]})
    failures = validate_company_year_uniqueness(df, "profitandloss")
    _failure("DQ-02", "CRITICAL", failures)


def test_dq03_foreign_key_integrity():
    child = pd.DataFrame({"company_id": ["TCS", "MISSING"]})
    master = pd.DataFrame({"id": ["TCS"]})
    failures = validate_foreign_keys(child, master, "cashflow", "companies")
    assert any(f["rule_id"] == "DQ-03" for f in failures)
    assert failures[0]["severity"] == "CRITICAL"


def test_dq04_balance_sheet_equation():
    df = pd.DataFrame(
        {
            "id": [1],
            "total_assets": [1000.0],
            "total_liabilities": [800.0],
        }
    )
    failures = validate_balance_sheet(df)
    _failure("DQ-04", "CRITICAL", failures)


def test_dq05_opm_cross_check():
    df = pd.DataFrame(
        {
            "id": [1],
            "sales": [100.0],
            "operating_profit": [20.0],
            "opm_percentage": [40.0],  # actual OPM is 20 -> mismatch
        }
    )
    failures = validate_opm(df)
    _failure("DQ-05", "WARNING", failures)


def test_dq06_positive_sales():
    df = pd.DataFrame({"id": [1], "sales": [-50.0]})
    failures = validate_positive_sales(df)
    _failure("DQ-06", "WARNING", failures)


def test_dq07_required_columns():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["2024-03"]})
    failures = validate_required_columns(
        df, "profitandloss", ["company_id", "year", "sales"]
    )
    _failure("DQ-07", "CRITICAL", failures)


def test_dq08_null_company_ids():
    df = pd.DataFrame({"company_id": ["TCS", None], "year": ["2024-03"] * 2})
    failures = validate_null_company_ids(df, "cashflow")
    _failure("DQ-08", "CRITICAL", failures)


def test_dq09_null_year():
    df = pd.DataFrame({"company_id": ["TCS"], "year": [None]})
    failures = validate_null_year(df, "balancesheet")
    _failure("DQ-09", "CRITICAL", failures)


def test_dq10_numeric_columns():
    df = pd.DataFrame({"id": [1], "sales": ["not-a-number"], "net_profit": [10.0]})
    failures = validate_numeric_columns(df, "profitandloss", ["sales", "net_profit"])
    _failure("DQ-10", "WARNING", failures)


def test_dq11_duplicate_rows():
    df = pd.DataFrame({"id": [1, 1], "name": ["TCS", "TCS"]})
    failures = validate_duplicate_rows(df, "companies")
    _failure("DQ-11", "WARNING", failures)


def test_dq12_year_range():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["1799-03"]})
    failures = validate_year_range(df, "profitandloss")
    _failure("DQ-12", "WARNING", failures)


def test_dq13_url_format():
    df = pd.DataFrame({"id": [1], "annual_report": ["not-a-url"]})
    failures = validate_urls(df, "documents", ["annual_report"])
    _failure("DQ-13", "WARNING", failures)


def test_dq14_negative_values():
    df = pd.DataFrame({"id": [1], "total_assets": [100.0], "total_liabilities": [-5.0]})
    failures = validate_non_negative(
        df, "balancesheet", ["total_assets", "total_liabilities"]
    )
    _failure("DQ-14", "WARNING", failures)


# ------------------------------------------------------------------
# Master-validator routing: dataframe violates ONE rule -> that rule_id.
# ------------------------------------------------------------------


def test_master_validator_routes_balance_sheet_rule():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "RELIANCE"],
            "year": ["2024-03", "2024-03"],
            "total_assets": [1000.0, 2000.0],
            "total_liabilities": [700.0, 1900.0],
            "equity_capital": [100.0, 100.0],
            "reserves": [100.0, 100.0],
            "borrowings": [100.0, 100.0],
            "total_debt_cr": [10.0, 10.0],
        }
    )
    failures = validate_dataframe(df, "balancesheet")
    rule_ids = {f["rule_id"] for f in failures}
    assert "DQ-04" in rule_ids
    assert all(f["severity"] in ("CRITICAL", "WARNING") for f in failures)


def test_master_validator_routes_positive_sales_rule():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": ["TCS"],
            "year": ["2024-03"],
            "sales": [-10.0],
            "expenses": [5.0],
            "operating_profit": [-15.0],
            "opm_percentage": [0.0],
            "net_profit": [-10.0],
            "eps": [0.0],
            "total_assets": [100.0],
            "total_liabilities": [90.0],
        }
    )
    failures = validate_dataframe(df, "profitandloss")
    rule_ids = {f["rule_id"] for f in failures}
    assert "DQ-06" in rule_ids
