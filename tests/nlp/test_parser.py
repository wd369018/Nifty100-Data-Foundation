"""Day 29 parser tests: text-extraction and cross-validation."""

import pandas as pd

from src.nlp.parser import (
    ANALYSIS_PATTERN,
    cross_validate,
    parse_text_entries,
)


def test_pattern_matches_named_periods():
    assert ANALYSIS_PATTERN.search("10 Years: 21%").groups() == ("10", "21")
    assert ANALYSIS_PATTERN.search("5 Years       14%").groups() == ("5", "14")
    assert ANALYSIS_PATTERN.search("3 Years: 9%").groups() == ("3", "9")


def test_pattern_captures_negative_sign():
    match = ANALYSIS_PATTERN.search("1 Year: -2%")
    assert match.groups() == ("1", "-2")


def test_pattern_rejects_timeless_periods():
    assert ANALYSIS_PATTERN.search("TTM: 43%") is None
    assert ANALYSIS_PATTERN.search("Last Year: 12%") is None


def test_parse_text_entries_happy_path():
    raw = pd.DataFrame(
        [
            {
                "company_id": "XYZ",
                "compounded_sales_growth": "10 Years: 21%",
                "compounded_profit_growth": "5 Years       14%",
                "stock_price_cagr": "1 Year: -2%",
                "roe": "3 Years: 13%",
            }
        ]
    )
    parsed, failures = parse_text_entries(raw)

    assert len(failures) == 0
    assert len(parsed) == 4
    cols = {"company_id", "metric_type", "period_years", "value_pct"}
    assert set(parsed.columns) == cols

    sp = parsed[parsed["metric_type"] == "stock_price_cagr"].iloc[0]
    assert sp["period_years"] == 1
    assert sp["value_pct"] == -2.0

    roe = parsed[parsed["metric_type"] == "roe"].iloc[0]
    assert roe["period_years"] == 3
    assert roe["value_pct"] == 13.0


def test_parse_text_entries_collects_failures():
    raw = pd.DataFrame(
        [
            {
                "company_id": "XYZ",
                "compounded_sales_growth": "TTM: 43%",
                "compounded_profit_growth": "10 Years: 21%",
                "stock_price_cagr": None,
                "roe": None,
            }
        ]
    )
    parsed, failures = parse_text_entries(raw)

    assert len(parsed) == 1
    assert len(failures) == 1
    assert failures.iloc[0]["company_id"] == "XYZ"
    assert failures.iloc[0]["metric_type"] == "compounded_sales_growth"


def test_parse_text_entries_skips_blank_records():
    raw = pd.DataFrame(
        [
            {"company_id": None, "roe": "3 Years: 9%"},
            {"company_id": "XYZ", "roe": "3 Years: 9%"},
        ]
    )
    parsed, _ = parse_text_entries(raw)
    assert set(parsed["company_id"]) == {"XYZ"}


def test_cross_validate_flags_large_divergence(monkeypatch):
    parsed = pd.DataFrame(
        [
            {
                "company_id": "XYZ",
                "metric_type": "compounded_sales_growth",
                "period_years": 3,
                "value_pct": 5.0,
            },
            {
                "company_id": "XYZ",
                "metric_type": "compounded_sales_growth",
                "period_years": 3,
                "value_pct": 14.0,
            },
            {
                "company_id": "XYZ",
                "metric_type": "roe",
                "period_years": 10,
                "value_pct": 17.0,
            },
        ]
    )

    def fake_computed(_db):
        return {
            "XYZ": {
                "compounded_sales_growth": {
                    3: (15.22, "OK"),
                    5: (11.0, "OK"),
                    10: (9.0, "OK"),
                },
                "compounded_profit_growth": {
                    3: (8.0, "OK"),
                    5: (7.0, "OK"),
                    10: (6.0, "OK"),
                },
            }
        }

    monkeypatch.setattr("src.nlp.parser._computed_cagrs", fake_computed)
    out = cross_validate(parsed, db_path="ignored.db")

    # 5.0 vs 15.22 -> |10.22| > 5 flagged; 14.0 vs 15.22 -> not flagged;
    # roe is never cross-validated.
    assert len(out) == 1
    row = out.iloc[0]
    assert row["metric_type"] == "compounded_sales_growth"
    assert row["parsed_pct"] == 5.0
    assert row["computed_pct"] == 15.22
