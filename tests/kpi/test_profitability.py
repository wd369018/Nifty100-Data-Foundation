"""Profitability ratio formula tests (Sprint 2, Day 08)."""

import pytest

from src.analytics.ratios import (
    cross_check_opm,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
)


def test_net_profit_margin_normal():
    assert net_profit_margin(25, 100) == pytest.approx(25.0)


def test_net_profit_margin_zero_sales_returns_none():
    assert net_profit_margin(25, 0) is None


def test_operating_profit_margin_normal():
    assert operating_profit_margin(20, 100) == pytest.approx(20.0)


def test_operating_profit_margin_zero_sales_returns_none():
    assert operating_profit_margin(20, 0) is None


def test_cross_check_opm_matches_within_tolerance():
    mismatch, difference = cross_check_opm(20.0, 20.4)
    assert mismatch is False
    assert difference == pytest.approx(0.4)


def test_cross_check_opm_mismatch_greater_than_one_pp():
    mismatch, difference = cross_check_opm(20.0, 22.5)
    assert mismatch is True
    assert difference == pytest.approx(2.5)


def test_return_on_equity_normal():
    # net_profit / (equity + reserves) * 100 = 50 / 200 * 100
    assert return_on_equity(50, 100, 100) == pytest.approx(25.0)


def test_return_on_equity_negative_equity_returns_none():
    # equity + reserves <= 0 -> undefined.
    assert return_on_equity(50, -100, -50) is None


def test_return_on_capital_employed_normal():
    # EBIT 30 / (100 + 100 + 100) * 100 = 10
    assert return_on_capital_employed(30, 100, 100, 100) == pytest.approx(10.0)


def test_return_on_assets_normal():
    assert return_on_assets(50, 500) == pytest.approx(10.0)


def test_return_on_assets_zero_assets_returns_none():
    assert return_on_assets(50, 0) is None
