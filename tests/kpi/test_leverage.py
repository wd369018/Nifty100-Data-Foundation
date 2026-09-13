"""Leverage & efficiency ratio tests (Sprint 2, Day 09)."""

import pytest

from src.analytics.ratios import (
    asset_turnover,
    debt_to_equity,
    high_leverage_flag,
    icr_warning_flag,
    interest_coverage,
    interest_coverage_label,
    net_debt,
    roce_sector_benchmark,
)


def test_debt_to_equity_debt_free_returns_zero():
    # Borrowings = 0 -> D/E = 0 (not None).
    assert debt_to_equity(0, 100, 100) == 0


def test_debt_to_equity_normal():
    assert debt_to_equity(150, 100, 50) == pytest.approx(1.0)


def test_debt_to_equity_negative_equity_returns_none():
    assert debt_to_equity(150, -100, -50) is None


def test_interest_coverage_normal():
    # (op_profit + other_income) / interest = 60/20
    assert interest_coverage(50, 10, 20) == pytest.approx(3.0)


def test_interest_coverage_zero_interest_returns_none():
    assert interest_coverage(50, 10, 0) is None


def test_interest_coverage_label_debt_free():
    # ICR None (debt-free) -> display label Debt Free.
    assert interest_coverage_label(None) == "Debt Free"


def test_interest_coverage_label_at_risk():
    assert interest_coverage_label(1.2) == "At Risk"
    assert icr_warning_flag(1.2) is True


def test_interest_coverage_label_satisfactory():
    assert interest_coverage_label(4.0) == "Satisfactory"
    assert icr_warning_flag(4.0) is False


def test_high_leverage_flag_non_financial():
    assert high_leverage_flag(7.0, "Industrials") is True


def test_high_leverage_flag_financials_suppressed():
    # Banks structurally levered -> flag suppressed.
    assert high_leverage_flag(7.0, "Financials") is False


def test_high_leverage_flag_low_de():
    assert high_leverage_flag(2.0, "Industrials") is False


def test_net_debt():
    assert net_debt(500, 200) == pytest.approx(300.0)


def test_asset_turnover_normal():
    assert asset_turnover(1000, 500) == pytest.approx(2.0)


def test_asset_turnover_zero_assets_returns_none():
    assert asset_turnover(1000, 0) is None


def test_roce_sector_relative_benchmark():
    # Financials company uses sector-relative comparison.
    value, method = roce_sector_benchmark(
        30, 100, 100, 800, "Financials", sector_median_roce=10.0
    )
    assert method == "sector_relative"
    assert value is not None


def test_roce_absolute_for_non_financials():
    value, method = roce_sector_benchmark(30, 100, 100, 100, "Industrials")
    assert method == "absolute"
    assert value == pytest.approx(10.0)
