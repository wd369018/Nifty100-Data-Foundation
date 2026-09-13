"""Day 32 capital-allocation report tests."""

import pandas as pd
import pytest

from src.analytics.capital_allocation_report import (
    build_pattern_changes,
    coverage_issues,
    latest_year_distribution,
)


@pytest.fixture
def cap_frame():
    rows = []
    for cid in ["A", "B", "C"]:
        rows.append(
            {
                "company_id": cid,
                "year": "2023-03",
                "cfo_sign": "+",
                "cfi_sign": "-",
                "cff_sign": "-",
                "pattern_label": "Reinvestor",
            }
        )
    rows.append(
        {
            "company_id": "A",
            "year": "2024-03",
            "cfo_sign": "+",
            "cfi_sign": "+",
            "cff_sign": "-",
            "pattern_label": "Liquidating Assets",
        }
    )
    rows.append(
        {
            "company_id": "B",
            "year": "2024-03",
            "cfo_sign": None,
            "cfi_sign": None,
            "cff_sign": None,
            "pattern_label": "Cash Accumulator",
        }
    )
    return pd.DataFrame(rows)


def test_coverage_issues_detects_missing_and_null_patterns(cap_frame):
    issues = coverage_issues(cap_frame, universe={"A", "B", "C", "D"})
    assert issues["missing_companies"] == ["D"]
    assert issues["rows_with_null_pattern"] == 0
    # Company B's 2024 row has null signs.
    assert issues["rows_with_null_signs"] == 1
    assert issues["companies_without_latest_year"] == []


def test_latest_year_distribution(cap_frame):
    counts, latest = latest_year_distribution(cap_frame)

    assert counts["Liquidating Assets"] == 1
    assert counts["Cash Accumulator"] == 1
    assert counts["Reinvestor"] == 1
    assert counts["Shareholder Returns"] == 0

    by_year = latest.set_index("company_id")["year"]
    assert by_year["A"] == "2024-03"
    assert by_year["B"] == "2024-03"
    # C only has one year.
    assert by_year["C"] == "2023-03"


def test_pattern_changes_captures_transition(cap_frame):
    changes = build_pattern_changes(cap_frame)
    by_id = changes.set_index("company_id")

    a = by_id.loc["A"]
    assert bool(a["changed"]) is True
    assert a["prior_pattern"] == "Reinvestor"
    assert a["latest_pattern"] == "Liquidating Assets"

    b = by_id.loc["B"]
    assert b["prior_pattern"] == "Reinvestor"
    assert b["latest_pattern"] == "Cash Accumulator"

    # C has only a single year -> no change row is produced.
    assert "C" not in by_id.index


def test_pattern_changes_skips_single_year_companies():
    frame = pd.DataFrame(
        [{"company_id": "X", "year": "2024-03", "pattern_label": "Mixed"}]
    )
    changes = build_pattern_changes(frame)
    assert changes.empty
