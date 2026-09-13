"""Day 34/35 report tests (sector + portfolio)."""

import pytest

from src.reports.portfolio_report import _delta, _growth_pct, build_portfolio_rows
from src.reports.sector_report import _median, _pattern_chart, _sector_rows

# ------------------------------------------------------------------
# Sector report
# ------------------------------------------------------------------


def test_median():
    assert _median([]) is None
    assert _median([10.0]) == 10.0
    assert _median([1.0, 3.0, 2.0]) == 2.0
    assert _median([1.0, 3.0, 2.0, None]) == 2.0


def test_sector_rows_filters_by_sector():
    import pandas as pd

    latest = pd.DataFrame(
        [
            {
                "company_id": "A",
                "company_name": "Alpha",
                "sector": "Materials",
                "return_on_equity_pct": 10.0,
                "operating_profit_margin_pct": 12.0,
                "revenue_cagr_5yr": 5.0,
                "pat_cagr_5yr": 6.0,
                "free_cash_flow_cr": 10.0,
            },
            {
                "company_id": "B",
                "company_name": "Beta",
                "sector": "Energy",
                "return_on_equity_pct": 8.0,
                "operating_profit_margin_pct": 9.0,
                "revenue_cagr_5yr": 4.0,
                "pat_cagr_5yr": 5.0,
                "free_cash_flow_cr": 8.0,
            },
        ]
    )
    rows = _sector_rows("Materials", latest)
    assert [r["company"] for r in rows] == ["Alpha"]


def test_pattern_chart_returns_png_bytes():
    dist = [("Cash Accumulator", 3), ("Reinvestor", 1)]
    result = _pattern_chart(dist)
    assert result is not None
    result.seek(0)
    assert result.read()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pattern_chart_none_for_empty():
    assert _pattern_chart([]) is None


# ------------------------------------------------------------------
# Portfolio report
# ------------------------------------------------------------------


def test_delta_improves():
    arrow, text, bad = _delta("Revenue (Rs Cr)", 110.0, 100.0)
    assert arrow == "\u2191"
    assert "10.0%" in text
    assert bad is False


def test_delta_declines_is_bad():
    arrow, text, bad = _delta("Revenue (Rs Cr)", 90.0, 100.0)
    assert arrow == "\u2193"
    assert bad is True


def test_delta_flat_within_band():
    arrow, text, bad = _delta("Revenue (Rs Cr)", 101.0, 100.0)
    assert arrow == "\u2192"
    assert bad is False


def test_delta_zero_prior_flat():
    arrow, text, _ = _delta("Revenue (Rs Cr)", 10.0, 0.0)
    assert arrow == "\u2192"


def test_growth_pct():
    assert _growth_pct(120.0, 100.0) == 20.0
    assert _growth_pct(100.0, 120.0) == pytest.approx(-16.666, abs=0.01)
    assert _growth_pct(10.0, 0.0) is None
    assert _growth_pct(None, 5.0) is None


def test_build_portfolio_rows_real_db():
    pages = build_portfolio_rows()
    ids = [p["company_id"] for p in pages]
    assert pages  # non-empty
    assert ids == sorted(ids)  # alphabetical
    for page in pages:
        assert len(page["rows"]) == 7
        assert page["narrative"]
        # Y-axis colors: one arrow char per metric row.
        assert all(
            row["arrow"] in ("\u2191", "\u2193", "\u2192") for row in page["rows"]
        )
