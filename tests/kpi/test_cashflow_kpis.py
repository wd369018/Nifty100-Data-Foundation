"""Cash flow KPI formula tests (Sprint 2, Day 11)."""

import pytest

from src.analytics.cashflow_kpis import (
    CAPEX_ASSET_LIGHT,
    CAPEX_CAPITAL_INTENSIVE,
    CAPEX_MODERATE,
    PATTERN_CASH_ACCUMULATOR,
    PATTERN_DEBT_FUNDED_GROWTH,
    PATTERN_DISTRESS,
    PATTERN_LIQUIDATING,
    PATTERN_MIXED,
    PATTERN_PRE_REVENUE,
    PATTERN_REINVESTOR,
    PATTERN_SHAREHOLDER_RETURNS,
    QUALITY_ACCRUAL_RISK,
    QUALITY_HIGH,
    QUALITY_MODERATE,
    capex_intensity,
    capex_intensity_label,
    capital_allocation_pattern,
    cfo_quality_label,
    cfo_quality_score,
    fcf_conversion_rate,
    free_cash_flow,
)


def test_free_cash_flow():
    assert free_cash_flow(500, -200) == pytest.approx(300.0)


def test_free_cash_flow_negative_allowed():
    assert free_cash_flow(100, -300) == pytest.approx(-200.0)


def test_cfo_quality_score_high():
    # CFO/PAT always > 1 -> High Quality.
    score = cfo_quality_score([120, 110, 130], [100, 100, 100])
    assert score == pytest.approx(1.2)
    assert cfo_quality_label(score) == QUALITY_HIGH


def test_cfo_quality_score_moderate():
    score = cfo_quality_score([75, 65, 70], [100, 100, 100])
    assert 0.5 <= score <= 1.0
    assert cfo_quality_label(score) == QUALITY_MODERATE


def test_cfo_quality_score_accrual_risk():
    score = cfo_quality_score([30, 40, 20], [100, 100, 100])
    assert score < 0.5
    assert cfo_quality_label(score) == QUALITY_ACCRUAL_RISK


def test_cfo_quality_score_pat_zero_returns_none():
    pat_zero = [100, 0, 100]
    assert cfo_quality_score([120, 110, 130], pat_zero) is None


def test_cfo_quality_score_window_limit():
    # Only last 5 years are used even when 8 are provided.
    cfo_values = [10] * 3 + [120, 110, 130, 125, 115]
    pat_values = [100] * 3 + [100, 100, 100, 100, 100]
    score = cfo_quality_score(cfo_values, pat_values, window_years=5)
    years_used = 5
    expected = sum(cfo_values[-years_used:]) / sum(pat_values[-years_used:])
    assert score == pytest.approx(expected)


def test_capex_intensity_asset_light():
    assert capex_intensity(-20, 1000) == pytest.approx(2.0)
    assert capex_intensity_label(2.0) == CAPEX_ASSET_LIGHT


def test_capex_intensity_moderate():
    assert capex_intensity(-50, 1000) == pytest.approx(5.0)
    assert capex_intensity_label(5.0) == CAPEX_MODERATE


def test_capex_intensity_capital_intensive():
    assert capex_intensity(-150, 1000) == pytest.approx(15.0)
    assert capex_intensity_label(15.0) == CAPEX_CAPITAL_INTENSIVE


def test_capex_intensity_zero_sales_none():
    assert capex_intensity(-50, 0) is None


def test_fcf_conversion_rate():
    assert fcf_conversion_rate(250, 500) == pytest.approx(50.0)


def test_fcf_conversion_rate_zero_operating_profit_none():
    assert fcf_conversion_rate(250, 0) is None


def test_capital_allocation_reinvestor():
    assert capital_allocation_pattern(500, -200, -100) == PATTERN_REINVESTOR


def test_capital_allocation_shareholder_returns():
    # (+,-,-) with high CFO/PAT -> Shareholder Returns.
    pattern = capital_allocation_pattern(500, -200, -100, cfo_pat_ratio=1.8)
    assert pattern == PATTERN_SHAREHOLDER_RETURNS


def test_capital_allocation_liquidating():
    assert capital_allocation_pattern(300, 100, -400) == PATTERN_LIQUIDATING


def test_capital_allocation_distress():
    assert capital_allocation_pattern(-100, 50, 150) == PATTERN_DISTRESS


def test_capital_allocation_debt_funded_growth():
    assert capital_allocation_pattern(-50, -200, 400) == PATTERN_DEBT_FUNDED_GROWTH


def test_capital_allocation_cash_accumulator():
    assert capital_allocation_pattern(400, 200, 300) == PATTERN_CASH_ACCUMULATOR


def test_capital_allocation_pre_revenue():
    assert capital_allocation_pattern(-50, -100, -200) == PATTERN_PRE_REVENUE


def test_capital_allocation_mixed():
    assert capital_allocation_pattern(200, -150, 100) == PATTERN_MIXED
