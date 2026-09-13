"""20 KPI ratio tests — ROE, D/E, ICR, leverage flags, CAGR, OPM, CFO quality.

Sprint 6, Day 41 deliverable (tests/kpi/test_ratios.py).
"""

import pytest

from src.analytics.cagr import (
    FLAG_BOTH_NEGATIVE,
    FLAG_DECLINE_TO_LOSS,
    FLAG_INSUFFICIENT,
    FLAG_NORMAL,
    FLAG_TURNAROUND,
    FLAG_ZERO_BASE,
    cagr_with_flag,
)
from src.analytics.cashflow_kpis import cfo_quality_label, cfo_quality_score
from src.analytics.ratios import (
    cross_check_opm,
    debt_to_equity,
    high_leverage_flag,
    icr_warning_flag,
    interest_coverage,
    interest_coverage_label,
    net_profit_margin,
    return_on_assets,
    return_on_equity,
)


def test_roe_positive_equity():
    assert return_on_equity(50, 100, 100) == pytest.approx(25.0)


def test_roe_negative_equity_returns_none():
    assert return_on_equity(50, -100, -50) is None


def test_roe_zero_equity_returns_none():
    assert return_on_equity(10, 0, 0) is None


def test_de_debt_free_returns_zero():
    assert debt_to_equity(0, 100, 100) == 0


def test_de_normal_calculation():
    assert debt_to_equity(200, 100, 100) == pytest.approx(1.0)


def test_icr_zero_interest_returns_none():
    assert interest_coverage(50, 10, 0) is None


def test_icr_normal_calculation():
    assert interest_coverage(50, 10, 20) == pytest.approx(3.0)


def test_icr_warning_flag_below_threshold():
    assert icr_warning_flag(1.2) is True
    assert interest_coverage_label(1.2) == "At Risk"


def test_high_leverage_flag_non_financial():
    assert high_leverage_flag(7.0, "Industrials") is True


def test_high_leverage_flag_financials_suppressed():
    assert high_leverage_flag(7.0, "Financials") is False


def test_high_leverage_flag_low_de_not_flagged():
    assert high_leverage_flag(2.0, "Industrials") is False


def test_cagr_turnaround_flag():
    value, flag = cagr_with_flag(-10, 20, 5)
    assert value is None
    assert flag == FLAG_TURNAROUND


def test_cagr_decline_to_loss_flag():
    value, flag = cagr_with_flag(100, -50, 5)
    assert value is None
    assert flag == FLAG_DECLINE_TO_LOSS


def test_cagr_both_negative_flag():
    value, flag = cagr_with_flag(-100, -50, 5)
    assert value is None
    assert flag == FLAG_BOTH_NEGATIVE


def test_cagr_zero_base_flag():
    value, flag = cagr_with_flag(0, 50, 5)
    assert value is None
    assert flag == FLAG_ZERO_BASE


def test_cagr_normal_calculation():
    # 100 -> 161.051 over 5 years is exactly 10.0% CAGR.
    value, flag = cagr_with_flag(100, 161.051, 5)
    assert flag == FLAG_NORMAL
    assert value == pytest.approx(10.0, abs=0.01)


def test_cagr_insufficient_periods():
    value, flag = cagr_with_flag(100, 200, 0)
    assert value is None
    assert flag == FLAG_INSUFFICIENT


def test_opm_cross_check_divergence_flag():
    mismatch, difference = cross_check_opm(20.0, 22.5)
    assert mismatch is True
    assert difference == pytest.approx(2.5)


def test_opm_cross_check_within_tolerance():
    mismatch, _ = cross_check_opm(20.0, 20.4)
    assert mismatch is False


def test_cfo_quality_score_calculation():
    cfo = [100, 120, 110, 130, 140]
    pat = [80, 90, 100, 100, 100]
    assert cfo_quality_score(cfo, pat) == pytest.approx(1.28, abs=0.01)


def test_cfo_quality_score_zero_pat_returns_none():
    assert cfo_quality_score([100], [0]) is None


def test_cfo_quality_label_thresholds():
    assert cfo_quality_label(1.3) == "High Quality"
    assert cfo_quality_label(0.7) == "Moderate"
    assert cfo_quality_label(0.3) == "Accrual Risk"


def test_npm_and_roa_basics():
    assert net_profit_margin(25, 100) == pytest.approx(25.0)
    assert return_on_assets(50, 500) == pytest.approx(10.0)
