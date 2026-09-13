"""
CAGR engine for the Nifty100 Data Foundation project.

Sprint 2, Day 10. Computes revenue/PAT/EPS CAGR over 3, 5 and
10-year windows with explicit handling of every edge case.
"""

import math

# CAGR flags
FLAG_NORMAL = "NORMAL"
FLAG_DECLINE_TO_LOSS = "DECLINE_TO_LOSS"
FLAG_TURNAROUND = "TURNAROUND"
FLAG_BOTH_NEGATIVE = "BOTH_NEGATIVE"
FLAG_ZERO_BASE = "ZERO_BASE"
FLAG_INSUFFICIENT = "INSUFFICIENT"

FLAGS = {
    FLAG_NORMAL,
    FLAG_DECLINE_TO_LOSS,
    FLAG_TURNAROUND,
    FLAG_BOTH_NEGATIVE,
    FLAG_ZERO_BASE,
    FLAG_INSUFFICIENT,
}


def cagr(start_value, end_value, periods):
    """
    Compound Annual Growth Rate = ((end/start)^(1/n) - 1) x 100.

    Returns None when start_value is zero or negative (CAGR is not
    defined for a zero or negative base).
    """

    if start_value is None or end_value is None or periods is None:
        return None

    if not _is_number(start_value) or not _is_number(end_value):
        return None

    if not _is_number(periods):
        return None

    periods_number = float(periods)

    if periods_number <= 0:
        return None

    if float(start_value) <= 0:
        return None

    ratio = float(end_value) / float(start_value)

    if ratio <= 0:
        return None

    return (math.pow(ratio, 1.0 / periods_number) - 1.0) * 100.0


def cagr_with_flag(start_value, end_value, periods):
    """
    CAGR with edge-case handling.

    The 6 edge cases (Sprint 2, Day 10):
      - Positive -> Positive : compute normally (NORMAL)
      - Positive -> Negative : DECLINE_TO_LOSS
      - Negative -> Positive : TURNAROUND
      - Negative -> Negative : BOTH_NEGATIVE
      - Zero base            : ZERO_BASE
      - Insufficient data    : INSUFFICIENT

    Returns (cagr_value, flag). cagr_value is None for every
    non-NORMAL case.
    """

    if periods is None or periods <= 0:
        return None, FLAG_INSUFFICIENT

    if start_value is None or end_value is None:
        return None, FLAG_INSUFFICIENT

    if not _is_number(start_value) or not _is_number(end_value):
        return None, FLAG_INSUFFICIENT

    start = float(start_value)
    end = float(end_value)

    # Zero base -> ZERO_BASE (regardless of end sign).
    if abs(start) < 1e-9:
        return None, FLAG_ZERO_BASE

    if start > 0 and end > 0:
        value = cagr(start, end, periods)
        return value, FLAG_NORMAL

    if start > 0 > end:
        return None, FLAG_DECLINE_TO_LOSS

    if start < 0 < end:
        return None, FLAG_TURNAROUND

    if start < 0 and end < 0:
        return None, FLAG_BOTH_NEGATIVE

    return None, FLAG_INSUFFICIENT


def cagr_ending_at(values_by_year, through_year, window_years):
    """
    Compute CAGR for a time series ending at a specific year.

    Used to populate a CAGR value for every company-year row: the end
    value is `through_year` and the start value is `through_year -
    window_years` (closest available earlier year).

    Requires the end-year value to be present, otherwise INSUFFICIENT.

    Parameters:
        values_by_year (dict):
            Mapping of {year: value} sorted ascending.

        through_year (int):
            The ending year for the CAGR window.

        window_years (int):
            CAGR window (3, 5 or 10).

    Returns:
        tuple[float | None, str]:
            CAGR value and flag.
    """

    if window_years not in (3, 5, 10):
        return None, FLAG_INSUFFICIENT

    if not values_by_year:
        return None, FLAG_INSUFFICIENT

    series = sorted(values_by_year.items())

    if through_year not in values_by_year:
        return None, FLAG_INSUFFICIENT

    end_value = values_by_year[through_year]
    start_value = None

    for year_value in series:
        start_year = year_value[0]
        if (through_year - start_year) >= window_years:
            start_value = year_value[1]
            # Keep iterating: use the latest qualifying start year.
            continue

    if start_value is None:
        return None, FLAG_INSUFFICIENT

    return cagr_with_flag(start_value, end_value, window_years)


def series_cagr(values_by_year, window_years):
    """
    Compute CAGR for a time series across a window.

    The end value is the latest year available; the start value is the
    year `window_years` before the latest.

    Requires at least window_years + 1 distinct years of data,
    otherwise INSUFFICIENT.

    Parameters:
        values_by_year (dict | list of tuples):
            Mapping/iterable of {(year): value} sorted ascending.

        window_years (int):
            CAGR window (3, 5 or 10).

    Returns:
        tuple[float | None, str]:
            CAGR value and flag.
    """

    if window_years not in (3, 5, 10):
        return None, FLAG_INSUFFICIENT

    if isinstance(values_by_year, dict):
        series = sorted(values_by_year.items())
    else:
        series = sorted(values_by_year)

    if len(series) < window_years + 1:
        return None, FLAG_INSUFFICIENT

    end_year, end_value = series[-1]
    start_value = None

    for year_value in series:
        start_year = year_value[0]
        if (end_year - start_year) >= window_years:
            start_value = year_value[1]
            # Keep iterating: use the latest qualifying start year
            # (latest year such that end_year - start_year >= window).
            continue

    if start_value is None:
        return None, FLAG_INSUFFICIENT

    return cagr_with_flag(start_value, end_value, window_years)


# ============================================================
# HELPERS
# ============================================================


def _is_number(value):
    """Return True if value is a real number (not NaN/Inf)."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return False

    return not (math.isnan(number) or math.isinf(number))
