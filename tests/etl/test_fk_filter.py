import pandas as pd
import pytest

from src.etl.fk_filter import (
    filter_company_foreign_keys,
    save_rejection_audit,
)


def make_companies():
    return pd.DataFrame({"id": ["TCS", "RELIANCE", "HDFCBANK"]})


def test_filter_company_foreign_keys_keeps_valid():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "company_id": ["tcs", "RELIANCE ", "HDFCBANK"],
        }
    )

    valid, rejected = filter_company_foreign_keys(
        df, make_companies(), table_name="profitandloss"
    )

    assert len(valid) == 3
    assert rejected.empty


def test_filter_company_foreign_keys_rejects_orphans():
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "company_id": ["TCS", "GHOST"],
        }
    )

    valid, rejected = filter_company_foreign_keys(
        df, make_companies(), table_name="cashflow"
    )

    assert len(valid) == 1
    assert valid.iloc[0]["company_id"] == "TCS"

    assert len(rejected) == 1
    assert rejected.iloc[0]["company_id"] == "GHOST"
    assert "DQ-03" in rejected.iloc[0]["rejection_reason"]
    assert "cashflow" in rejected.iloc[0]["table_name"]


def test_filter_company_foreign_keys_case_insensitive():
    companies = pd.DataFrame({"id": ["tcs"]})
    df = pd.DataFrame({"id": [1], "company_id": ["TCS"]})

    valid, rejected = filter_company_foreign_keys(df, companies)

    assert len(valid) == 1
    assert rejected.empty


def test_filter_company_foreign_keys_missing_company_column():
    df = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError):
        filter_company_foreign_keys(df, make_companies(), table_name="cashflow")


def test_filter_company_foreign_keys_missing_master_column():
    df = pd.DataFrame({"id": [1], "company_id": ["TCS"]})
    companies = pd.DataFrame({"name": ["TCS"]})

    with pytest.raises(ValueError):
        filter_company_foreign_keys(df, companies, table_name="cashflow")


def test_filter_company_foreign_keys_null_company_id_rejected():
    df = pd.DataFrame(
        {
            "id": [1],
            "company_id": [None],
        }
    )

    valid, rejected = filter_company_foreign_keys(
        df, make_companies(), table_name="cashflow"
    )

    assert valid.empty
    assert len(rejected) == 1


def test_save_rejection_audit_creates_file(tmp_path):
    rejected = pd.DataFrame(
        {
            "table_name": ["cashflow"],
            "rejection_reason": ["DQ-03: ..."],
            "company_id": ["GHOST"],
        }
    )

    output = tmp_path / "rejections.csv"

    save_rejection_audit(rejected, output)

    df = pd.read_csv(output)

    assert len(df) == 1
    assert df.loc[0, "company_id"] == "GHOST"


def test_save_rejection_audit_empty(tmp_path):
    output = tmp_path / "rejections.csv"

    save_rejection_audit(pd.DataFrame(), output)

    df = pd.read_csv(output)

    assert "company_id" in df.columns
    assert df.empty
