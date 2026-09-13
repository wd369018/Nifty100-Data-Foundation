"""CAGR engine edge-case tests (Sprint 2, Day 10)."""

import pytest

from src.analytics.cagr import (
    FLAG_BOTH_NEGATIVE,
    FLAG_DECLINE_TO_LOSS,
    FLAG_INSUFFICIENT,
    FLAG_NORMAL,
    FLAG_TURNAROUND,
    FLAG_ZERO_BASE,
    cagr,
    cagr_with_flag,
    series_cagr,
)


def test_cagr_normal():
    # 100 -> 200 over 5 years = ~14.87% CAGR.
    value = cagr(100, 200, 5)
    assert value == pytest.approx(14.87, abs=0.01)


def test_cagr_positive_positive_normal_flag():
    value, flag = cagr_with_flag(100, 161.051, 1)
    assert flag == FLAG_NORMAL
    assert value == pytest.approx(61.05, abs=0.01)


def test_cagr_positive_negative_decline_to_loss():
    value, flag = cagr_with_flag(100, -50, 3)
    assert value is None
    assert flag == FLAG_DECLINE_TO_LOSS


def test_cagr_negative_positive_turnaround():
    value, flag = cagr_with_flag(-100, 200, 3)
    assert value is None
    assert flag == FLAG_TURNAROUND


def test_cagr_negative_negative_both_negative():
    value, flag = cagr_with_flag(-100, -50, 3)
    assert value is None
    assert flag == FLAG_BOTH_NEGATIVE


def test_cagr_zero_base():
    value, flag = cagr_with_flag(0, 200, 3)
    assert value is None
    assert flag == FLAG_ZERO_BASE


def test_cagr_insufficient_periods():
    value, flag = cagr_with_flag(100, 200, 0)
    assert value is None
    assert flag == FLAG_INSUFFICIENT


def test_cagr_missing_values():
    value, flag = cagr_with_flag(None, 200, 3)
    assert value is None
    assert flag == FLAG_INSUFFICIENT


def test_series_cagr_normal_window():
    # 10 years of data starting at 2014, 5-year window.
    series = {2014 + i: 100 * (1.1**i) for i in range(10)}
    value, flag = series_cagr(series, 5)
    assert flag == FLAG_NORMAL
    assert value == pytest.approx(10.0, abs=0.1)


def test_series_cagr_insufficient_data():
    # Only 3 years of data -> 5-year window impossible.
    series = {2022: 100, 2023: 110, 2024: 121}
    value, flag = series_cagr(series, 5)
    assert value is None
    assert flag == FLAG_INSUFFICIENT


def test_series_cagr_has_required_span():
    # Exactly 6 points for a 5-year window.
    series = {2019 + i: i + 1 for i in range(6)}
    value, flag = series_cagr(series, 5)
    assert flag == FLAG_NORMAL
    assert value is not None


def test_cagr_negative_end_ratio_none():
    # ratio <= 0 cannot be raised to fractional power.
    assert cagr(100, 0, 5) is None
    assert cagr(100, -50, 5) is None
