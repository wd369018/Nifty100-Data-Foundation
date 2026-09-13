"""
Financial ratio formulas for the Nifty100 Data Foundation project.

Covers profitability, leverage and efficiency ratios (Sprint 2,
Days 08-09). Every function guards against division by zero and
returns None when a ratio is not mathematically defined.
"""

import math

# Financials sector companies (banks, NBFCs, insurance) have high
# structural leverage - standard D/E warnings are suppressed for them.
FINANCIALS_SECTOR = "Financials"

# Debt-to-equity threshold for the high-leverage flag (non-Financials).
HIGH_LEVERAGE_DE_THRESHOLD = 5.0

# Interest coverage below this is a warning.
ICR_WARNING_THRESHOLD = 1.5

# OPM cross-check tolerance in percentage points.
OPM_TOLERANCE_PP = 1.0


# ============================================================
# PROFITABILITY RATIOS (Day 08)
# ============================================================


def net_profit_margin(net_profit, sales):
    """
    Net Profit Margin = net_profit / sales x 100.

    Returns None when sales is zero or missing.
    """

    if sales is None or net_profit is None:
        return None

    if not _is_number(sales) or not _is_number(net_profit):
        return None

    if _is_zero(sales):
        return None

    return (float(net_profit) / float(sales)) * 100.0


def operating_profit_margin(operating_profit, sales):
    """
    Operating Profit Margin = operating_profit / sales x 100.

    Returns None when sales is zero or missing.
    """

    if sales is None or operating_profit is None:
        return None

    if not _is_number(sales) or not _is_number(operating_profit):
        return None

    if _is_zero(sales):
        return None

    return (float(operating_profit) / float(sales)) * 100.0


def cross_check_opm(computed_opm, reported_opm, tolerance=OPM_TOLERANCE_PP):
    """
    Cross-check computed OPM against the reported source value.

    Returns (mismatch: bool, difference in percentage points).
    """

    if computed_opm is None or reported_opm is None:
        return False, None

    difference = abs(computed_opm - reported_opm)

    return difference > tolerance, difference


def return_on_equity(net_profit, equity_capital, reserves):
    """
    Return on Equity = net_profit / (equity_capital + reserves) x 100.

    Returns None when equity + reserves is <= 0 (negative equity),
    because ROE is meaningless for negative shareholder equity.
    """

    if net_profit is None or equity_capital is None or reserves is None:
        return None

    denominators = [
        equity_capital,
        reserves,
    ]

    if any(not _is_number(v) for v in denominators):
        return None

    equity = float(equity_capital) + float(reserves)

    if equity <= 0:
        return None

    if not _is_number(net_profit):
        return None

    return (float(net_profit) / equity) * 100.0


def return_on_capital_employed(ebit, equity_capital, reserves, borrowings):
    """
    Return on Capital Employed = EBIT / (equity + reserves + borrowings) x 100.

    EBIT is approximated as operating_profit + other_income.

    Returns None when capital employed is <= 0.
    """

    denominators = [
        equity_capital,
        reserves,
        borrowings,
    ]

    if ebit is None or any(v is None for v in denominators):
        return None

    if any(not _is_number(v) for v in denominators) or not _is_number(ebit):
        return None

    capital_employed = float(equity_capital) + float(reserves) + float(borrowings)

    if capital_employed <= 0:
        return None

    return (float(ebit) / capital_employed) * 100.0


def roce_sector_benchmark(
    ebit,
    equity_capital,
    reserves,
    borrowings,
    sector,
    sector_median_roce=None,
):
    """
    ROCE with a Financials-sector carve-out.

    For companies in the Financials broad_sector, the standard ROCE
    formula understates profitability because deposits and borrowings
    inflate the capital base. A sector-relative benchmark is used
    instead: the computed ROCE is compared against the sector median
    rather than an absolute threshold.

    Returns the ROCE value and a flag indicating the method used.
    """

    roce = return_on_capital_employed(ebit, equity_capital, reserves, borrowings)

    if roce is None:
        return None, "not_applicable"

    is_financial = sector == FINANCIALS_SECTOR

    if is_financial and sector_median_roce is not None:
        # Sector-relative comparison: report ROCE relative to median.
        if sector_median_roce == 0:
            return None, "sector_relative_zero_median"

        relative_roce = roce / sector_median_roce * 100.0
        return relative_roce, "sector_relative"

    return roce, "absolute"


def return_on_assets(net_profit, total_assets):
    """
    Return on Assets = net_profit / total_assets x 100.

    Returns None when total_assets is zero or missing.
    """

    if net_profit is None or total_assets is None:
        return None

    if not _is_number(net_profit) or not _is_number(total_assets):
        return None

    if _is_zero(total_assets):
        return None

    return (float(net_profit) / float(total_assets)) * 100.0


# ============================================================
# LEVERAGE & EFFICIENCY RATIOS (Day 09)
# ============================================================


def debt_to_equity(borrowings, equity_capital, reserves):
    """
    Debt-to-Equity = borrowings / (equity_capital + reserves).

    Returns 0 (not None) when borrowings is zero - a debt-free company
    has a D/E of exactly 0.

    Returns None when equity is <= 0 (ratio undefined).
    """

    if borrowings is None:
        return None

    if not _is_number(borrowings):
        return None

    if _is_zero(borrowings) or abs(float(borrowings)) < 1e-9:
        return 0.0

    if equity_capital is None or reserves is None:
        return None

    if not _is_number(equity_capital) or not _is_number(reserves):
        return None

    equity = float(equity_capital) + float(reserves)

    if equity <= 0:
        return None

    return float(borrowings) / equity


def high_leverage_flag(de, sector):
    """
    High-leverage flag.

    True when D/E > 5 and the company is NOT in the Financials sector.
    Financial companies are excluded because high leverage is
    structurally normal for banks, NBFCs and insurers (Day 13 carve-out).
    """

    if de is None or sector is None:
        return False

    if sector == FINANCIALS_SECTOR:
        return False

    return de > HIGH_LEVERAGE_DE_THRESHOLD


def interest_coverage(operating_profit, other_income, interest):
    """
    Interest Coverage Ratio = (operating_profit + other_income) / interest.

    Returns None when interest is zero - debt-free companies do not
    pay interest, so ICR is undefined (display label 'Debt Free').
    """

    if operating_profit is None or other_income is None or interest is None:
        return None

    values = [operating_profit, other_income, interest]

    if any(not _is_number(v) for v in values):
        return None

    if _is_zero(interest):
        return None

    earnings_before_interest = float(operating_profit) + float(other_income)

    return earnings_before_interest / float(interest)


def interest_coverage_label(icr):
    """
    ICR display label.

    'Debt Free' when ICR is None (company has no interest expense).
    'At Risk' when ICR < 1.5 (cannot comfortably cover interest).
    'Satisfactory' otherwise.
    """

    if icr is None:
        return "Debt Free"

    if icr < ICR_WARNING_THRESHOLD:
        return "At Risk"

    return "Satisfactory"


def icr_warning_flag(icr):
    """
    ICR warning flag.

    True when ICR is defined and below 1.5 - the company is at risk
    of not covering its interest payments.
    """

    if icr is None:
        return False

    return icr < ICR_WARNING_THRESHOLD


def net_debt(borrowings, investments):
    """
    Net Debt = borrowings - investments.

    Investments are used as a proxy for liquid assets.
    """

    if borrowings is None or investments is None:
        return None

    if not _is_number(borrowings) or not _is_number(investments):
        return None

    return float(borrowings) - float(investments)


def asset_turnover(sales, total_assets):
    """
    Asset Turnover = sales / total_assets.

    Returns None when total_assets is zero or missing.
    """

    if sales is None or total_assets is None:
        return None

    if not _is_number(sales) or not _is_number(total_assets):
        return None

    if _is_zero(total_assets):
        return None

    return float(sales) / float(total_assets)


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


def _is_zero(value):
    """Return True if value is effectively zero."""

    return abs(float(value)) < 1e-9
