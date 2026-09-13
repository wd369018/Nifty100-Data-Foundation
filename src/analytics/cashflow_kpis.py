"""
Cash flow KPIs and capital allocation classifier.

Sprint 2, Day 11.

Free Cash Flow, CFO Quality Score, CapEx Intensity, FCF Conversion
Rate and the 8-pattern capital allocation classifier based on the
sign of (CFO, CFI, CFF).
"""

import math

import pandas as pd

# ---- CFO Quality Score labels --------
QUALITY_HIGH = "High Quality"
QUALITY_MODERATE = "Moderate"
QUALITY_ACCRUAL_RISK = "Accrual Risk"

# ---- CapEx Intensity labels -----------
CAPEX_ASSET_LIGHT = "Asset Light"
CAPEX_MODERATE = "Moderate"
CAPEX_CAPITAL_INTENSIVE = "Capital Intensive"

# ---- Capital allocation 8 patterns ----
PATTERN_REINVESTOR = "Reinvestor"
PATTERN_SHAREHOLDER_RETURNS = "Shareholder Returns"
PATTERN_LIQUIDATING = "Liquidating Assets"
PATTERN_DISTRESS = "Distress Signal"
PATTERN_DEBT_FUNDED_GROWTH = "Growth Funded by Debt"
PATTERN_CASH_ACCUMULATOR = "Cash Accumulator"
PATTERN_PRE_REVENUE = "Pre-Revenue"
PATTERN_MIXED = "Mixed"


def free_cash_flow(operating_activity, investing_activity):
    """
    Free Cash Flow = operating_activity + investing_activity.

    Negative values are allowed and meaningful (a company can consume
    more cash than it generates while expanding).
    """

    if operating_activity is None or investing_activity is None:
        return None

    if not _is_number(operating_activity) or not _is_number(investing_activity):
        return None

    return float(operating_activity) + float(investing_activity)


def cfo_quality_score(cfo_values, pat_values, window_years=5):
    """
    CFO Quality Score = average over 5 years of (CFO / PAT).

    Labels (based on the score):
      - > 1.0  : High Quality (cash earnings exceed accounting profit)
      - 0.5-1.0: Moderate
      - < 0.5  : Accrual Risk

    Returns None when PAT is zero or when no valid ratios exist.
    Uses available years when fewer than `window_years` are present.

    Parameters:
        cfo_values (list): CFO per year (element order matters).
        pat_values (list): PAT per year, aligned with cfo_values.

        window_years (int): Rolling window length in years.

    Returns:
        float | None: The CFO quality score.
    """

    if cfo_values is None or pat_values is None:
        return None

    if len(cfo_values) != len(pat_values) or not cfo_values:
        return None

    if len(cfo_values) > window_years:
        cfo_values = cfo_values[-window_years:]
        pat_values = pat_values[-window_years:]

    # PAT = 0 makes the CFO/PAT ratio undefined -> no score.
    if any(
        pat is None or not _is_number(pat) or abs(float(pat)) < 1e-9
        for pat in pat_values
    ):
        return None

    ratios = []

    for cfo, pat in zip(cfo_values, pat_values):
        if cfo is None:
            continue

        if not _is_number(cfo):
            continue

        ratios.append(float(cfo) / float(pat))

    if not ratios:
        return None

    return sum(ratios) / len(ratios)


def cfo_quality_label(score):
    """
    Convert a CFO quality score into a human-readable label.
    """

    if score is None:
        return None

    if score > 1.0:
        return QUALITY_HIGH

    if score >= 0.5:
        return QUALITY_MODERATE

    return QUALITY_ACCRUAL_RISK


def cfo_quality_score_with_label(cfo_values, pat_values, window_years=5):
    """
    CFO Quality Score plus its label.
    """

    score = cfo_quality_score(cfo_values, pat_values, window_years)

    return score, cfo_quality_label(score)


def capex_intensity(investing_activity, sales):
    """
    CapEx Intensity = abs(investing_activity) / sales x 100.

    Labels:
      - < 3%  : Asset Light
      - 3-8%  : Moderate
      - > 8%  : Capital Intensive

    Returns None when sales is zero or missing.
    """

    if investing_activity is None or sales is None:
        return None

    if not _is_number(investing_activity) or not _is_number(sales):
        return None

    if abs(float(sales)) < 1e-9:
        return None

    return abs(float(investing_activity)) / abs(float(sales)) * 100.0


def capex_intensity_label(intensity):
    """
    Convert CapEx intensity into a label.
    """

    if intensity is None:
        return None

    if intensity < 3.0:
        return CAPEX_ASSET_LIGHT

    if intensity <= 8.0:
        return CAPEX_MODERATE

    return CAPEX_CAPITAL_INTENSIVE


def fcf_conversion_rate(free_cash_flow_value, operating_profit):
    """
    FCF Conversion Rate = FCF / operating_profit x 100.

    Returns None when operating_profit is zero or missing.
    """

    if free_cash_flow_value is None or operating_profit is None:
        return None

    if not _is_number(free_cash_flow_value) or not _is_number(operating_profit):
        return None

    if abs(float(operating_profit)) < 1e-9:
        return None

    return float(free_cash_flow_value) / float(operating_profit) * 100.0


def capital_allocation_pattern(cfo, cfi, cff, cfo_pat_ratio=None):
    """
    Classify the capital allocation pattern from the signs of
    (CFO, CFI, CFF), plus an optional CFO/PAT ratio used to
    distinguish Reinvestor from Shareholder Returns.

    Patterns:
      (+,-,-)                   -> Reinvestor
      (+,-,-) + high CFO/PAT    -> Shareholder Returns
      (+,+,-)                   -> Liquidating Assets
      (-,+,+)                   -> Distress Signal
      (-,-,+)                   -> Growth Funded by Debt
      (+,+,+)                   -> Cash Accumulator
      (-,-,-)                   -> Pre-Revenue
      (+,-,+)                   -> Mixed

    Signs use 0 as neutral -> positive for sign classification
    (a zero cash flow item is treated as non-negative for the
    pattern, matching conventional practice).
    """

    cfo_sign = _sign(cfo)
    cfi_sign = _sign(cfi)
    cff_sign = _sign(cff)

    pattern = _classify(cfo_sign, cfi_sign, cff_sign)

    # Reinvestor vs Shareholder Returns refinement.
    if (
        pattern == PATTERN_REINVESTOR
        and cfo_pat_ratio is not None
        and _is_number(cfo_pat_ratio)
        and float(cfo_pat_ratio) > 1.0
    ):
        pattern = PATTERN_SHAREHOLDER_RETURNS

    return pattern


def _classify(cfo_sign, cfi_sign, cff_sign):
    """Return the pattern label for the given sign combination."""

    if cfo_sign == "+":
        if cfi_sign == "-" and cff_sign == "-":
            return PATTERN_REINVESTOR

        if cfi_sign == "+" and cff_sign == "-":
            return PATTERN_LIQUIDATING

        if cfi_sign == "+" and cff_sign == "+":
            return PATTERN_CASH_ACCUMULATOR

        if cfi_sign == "-" and cff_sign == "+":
            return PATTERN_MIXED

        return PATTERN_MIXED

    if cfo_sign == "-":
        if cfi_sign == "+" and cff_sign == "+":
            return PATTERN_DISTRESS

        if cfi_sign == "-" and cff_sign == "+":
            return PATTERN_DEBT_FUNDED_GROWTH

        if cfi_sign == "-" and cff_sign == "-":
            return PATTERN_PRE_REVENUE

        return PATTERN_MIXED

    return PATTERN_MIXED


def _sign(value):
    """
    Return the sign of a value for capital-allocation classification.

    Zero/None counts as positive (non-negative). This matches the
    conventional treatment where a zero line-item does not break
    the pattern.
    """

    if value is None:
        return "+"

    if not _is_number(value):
        return "+"

    if float(value) < 0:
        return "-"

    return "+"


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


# ============================================================
# SPRINT 5, DAY 31 - Cash Flow Intelligence builder
# ============================================================

CFI_COLUMNS = [
    "company_id",
    "sector",
    "cfo_quality_score",
    "cfo_quality_label",
    "capex_intensity_pct",
    "capex_label",
    "fcf_cagr_5yr",
    "fcf_conversion_pct",
    "distress_flag",
    "deleveraging_flag",
    "capital_allocation_label",
]


def fcf_cagr_5yr(fcf_by_year, latest_year):
    """
    CAGR of free cash flow over a 5-year window ending at `latest_year`.

    Falls back to the longest available window when fewer than 5 years are
    present, and returns None when the series is empty or the CAGR is
    undefined (e.g. negative starting value flips the sign).
    """

    from src.analytics.cagr import cagr_ending_at

    if not fcf_by_year:
        return None

    window_years = 5
    while window_years >= 2:
        value, flag = cagr_ending_at(fcf_by_year, latest_year, window_years)
        if value is not None:
            return _round2(value * 100.0)
        window_years -= 1

    return None


def _round2(value):
    if value is None:
        return None
    return round(float(value), 2)


def _year_int(year_str):
    try:
        return int(str(year_str)[:4])
    except (TypeError, ValueError):
        return None


def build_cashflow_intelligence_frame(db_path, sector_map=None):
    """
    Produce the 92-row Cash Flow Intelligence frame.

    One row per company. `distress_flag` = latest year CFO < 0 AND CFF > 0;
    `deleveraging_flag` = latest year CFF < 0 AND borrowings lower than the
    prior year.
    """

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        cashflow = pd.read_sql_query("SELECT * FROM cashflow ORDER BY year", conn)
        pl = pd.read_sql_query(
            "SELECT company_id, year, net_profit, operating_profit, sales "
            "FROM profitandloss ORDER BY year",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT company_id, year, borrowings FROM balancesheet " "ORDER BY year",
            conn,
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    finally:
        conn.close()

    if sector_map is None:
        sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))

    rows = []
    for company_id in sorted(sector_map):
        cf = cashflow[cashflow["company_id"] == company_id]
        plc = pl[pl["company_id"] == company_id]
        bsc = bs[bs["company_id"] == company_id]

        latest_year = cf["year"].max() if not cf.empty else None

        if latest_year is None:
            # Company has no cash flow history in the DB (e.g. ATGL).
            rows.append(
                {
                    "company_id": company_id,
                    "sector": sector_map[company_id],
                    "cfo_quality_score": None,
                    "cfo_quality_label": None,
                    "capex_intensity_pct": None,
                    "capex_label": None,
                    "fcf_cagr_5yr": None,
                    "fcf_conversion_pct": None,
                    "distress_flag": False,
                    "deleveraging_flag": False,
                    "capital_allocation_label": None,
                }
            )
            continue

        latest_row = cf[cf["year"] == latest_year].iloc[-1]
        cfo = _num(latest_row.get("operating_activity"))
        cfi = _num(latest_row.get("investing_activity"))
        cff = _num(latest_row.get("financing_activity"))

        # ---- CFO quality score (last 5 years of CFO / PAT) ----
        cfo_vals, pat_vals = [], []
        yearly = cf.sort_values("year")
        for _, r in yearly.tail(5).iterrows():
            cfo_v = _num(r.get("operating_activity"))
            pat_rows = plc[plc["year"] == r["year"]]
            pat_v = (
                _num(pat_rows["net_profit"].iloc[-1]) if not pat_rows.empty else None
            )
            cfo_vals.append(cfo_v if cfo_v is not None else 0.0)
            pat_vals.append(pat_v)
        score = cfo_quality_score(cfo_vals, pat_vals)
        score_label = cfo_quality_label(score)

        # ---- CapEx intensity (latest year) ----
        sales_row = plc[plc["year"] == latest_year]
        sales_v = _num(sales_row["sales"].iloc[-1]) if not sales_row.empty else None
        intensity = capex_intensity(cfi, sales_v)
        intensity_label = capex_intensity_label(intensity)

        # ---- FCF CAGR over 5 years ----
        fcf_by_year = {}
        for _, r in yearly.iterrows():
            year_i = _year_int(r["year"])
            fcf_v = free_cash_flow(
                _num(r.get("operating_activity")),
                _num(r.get("investing_activity")),
            )
            if year_i is not None and fcf_v is not None:
                fcf_by_year[year_i] = fcf_v
        latest_year_i = _year_int(latest_year)
        cagr5 = fcf_cagr_5yr(fcf_by_year, latest_year_i)

        # ---- FCF conversion (latest year) ----
        op_row = plc[plc["year"] == latest_year]
        op_v = _num(op_row["operating_profit"].iloc[-1]) if not op_row.empty else None
        fcf_v = free_cash_flow(cfo, cfi)
        conversion = fcf_conversion_rate(fcf_v, op_v)

        # ---- Distress and deleveraging flags ----
        distress = bool(cfo is not None and cff is not None and cfo < 0 and cff > 0)
        prior_cff = None
        if len(yearly) >= 2:
            prior_row = yearly.iloc[-2]
            prior_cff = _num(prior_row.get("financing_activity"))
        borrowings_latest = None
        if not bsc.empty:
            borrowings_latest = _num(bsc.sort_values("year")["borrowings"].iloc[-1])
            borrowings_prior = (
                _num(bsc.sort_values("year")["borrowings"].iloc[-2])
                if len(bsc) >= 2
                else None
            )
        else:
            borrowings_prior = None
        deleveraging = bool(
            cff is not None
            and cff < 0
            and borrowings_latest is not None
            and borrowings_prior is not None
            and borrowings_latest < borrowings_prior
        )
        _ = prior_cff  # kept for symmetry/documentation

        # ---- Capital allocation pattern (latest year) ----
        pat_pat_row = plc[plc["year"] == latest_year]
        pat_v = (
            _num(pat_pat_row["net_profit"].iloc[-1]) if not pat_pat_row.empty else None
        )
        cfo_pat_ratio = (
            (cfo / pat_v)
            if (cfo is not None and pat_v is not None and abs(pat_v) > 1e-9)
            else None
        )
        pattern = capital_allocation_pattern(cfo, cfi, cff, cfo_pat_ratio)

        rows.append(
            {
                "company_id": company_id,
                "sector": sector_map[company_id],
                "cfo_quality_score": _round2(score),
                "cfo_quality_label": score_label,
                "capex_intensity_pct": _round2(intensity),
                "capex_label": intensity_label,
                "fcf_cagr_5yr": cagr5,
                "fcf_conversion_pct": _round2(conversion),
                "distress_flag": distress,
                "deleveraging_flag": deleveraging,
                "capital_allocation_label": pattern,
            }
        )

    frame = pd.DataFrame(rows, columns=CFI_COLUMNS)
    return frame


def build_distress_alerts(frame, db_path="db/nifty100.db"):
    """
    Extract the distress rows for output/distress_alerts.csv.

    Columns: company_id, cfo_operating, cff_financing, latest_net_profit
    (values are pulled from the live DB for the flagged companies).
    """

    import sqlite3

    if frame.empty or "distress_flag" not in frame.columns:
        return pd.DataFrame(
            columns=[
                "company_id",
                "cfo_operating",
                "cff_financing",
                "latest_net_profit",
            ]
        )

    flagged = set(frame.loc[frame["distress_flag"], "company_id"])

    conn = sqlite3.connect(db_path)
    try:
        cashflow = pd.read_sql_query("SELECT * FROM cashflow ORDER BY year", conn)
        pl = pd.read_sql_query(
            "SELECT company_id, year, net_profit FROM profitandloss " "ORDER BY year",
            conn,
        )
    finally:
        conn.close()

    rows = []
    for company_id in sorted(flagged):
        cf = cashflow[cashflow["company_id"] == company_id]
        plc = pl[pl["company_id"] == company_id]
        if cf.empty:
            continue
        latest_year = cf["year"].max()
        latest = cf[cf["year"] == latest_year].iloc[-1]
        pat_row = plc[plc["year"] == latest_year]
        rows.append(
            {
                "company_id": company_id,
                "cfo_operating": _num(latest.get("operating_activity")),
                "cff_financing": _num(latest.get("financing_activity")),
                "latest_net_profit": (
                    _num(pat_row["net_profit"].iloc[-1]) if not pat_row.empty else None
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["company_id", "cfo_operating", "cff_financing", "latest_net_profit"],
    )


def main(db_path="db/nifty100.db"):
    """
    Build and write the Sprint 5 Day 31 cash-flow deliverables:
      output/cashflow_intelligence.xlsx
      output/distress_alerts.csv
    """

    from pathlib import Path

    frame = build_cashflow_intelligence_frame(db_path)

    out_xlsx = Path("output/cashflow_intelligence.xlsx")
    out_csv = Path("output/distress_alerts.csv")
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Cash Flow Intelligence", index=False)

    distress = build_distress_alerts(frame)
    distress.to_csv(out_csv, index=False)

    print("=" * 60)
    print("CASH FLOW INTELLIGENCE (Sprint 5, Day 31)")
    print("=" * 60)
    print(f"  Companies              : {len(frame)}")
    print(f"  Distress flagged       : {int(distress_flag_count(frame))}")
    print(f"  Deleveraging flagged   : {int(deleveraging_flag_count(frame))}")
    print(f"  CFO Quality labels     : {quality_label_counts(frame)}")
    print(f"\n  Output                 : {out_xlsx}")
    print(f"  Distress alerts        : {out_csv}")
    print("=" * 60)
    return 0


def distress_flag_count(frame):
    if "distress_flag" not in frame.columns:
        return 0
    return int(frame["distress_flag"].sum())


def deleveraging_flag_count(frame):
    if "deleveraging_flag" not in frame.columns:
        return 0
    return int(frame["deleveraging_flag"].sum())


def quality_label_counts(frame):
    if "cfo_quality_label" not in frame.columns:
        return {}
    return frame["cfo_quality_label"].value_counts().to_dict()


def _num(value):
    from src.screener.engine import _num as engine_num

    return engine_num(value)
