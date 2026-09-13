"""
Nifty100 Screener Filter Engine (Sprint 3, Days 15-17).

Loads config/screener_config.yaml, builds a per-company feature frame
(the latest screening year for every company in the universe), and
applies threshold filters defined by analyst presets.

Day 15  - filter core: 15 filterable metrics + sorted output.
Day 16  - the 6 preset screeners.
Day 17  - weighted composite quality score (P10/P90 winsorised,
          global and sector-relative) and screener_output.xlsx.

Design notes:
- The screening year per company is the latest fiscal year with a
  computed ROE (ROE is the anchor metric for the composite score and
  guarantees the P&L is present).
- D/E filters skip the Financials sector entirely.
- An ICR filter passes any company labelled 'Debt Free' (a debt-free
  company has no interest expense -> infinite coverage).
- Filters never raise: a missing value simply fails the filter.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import yaml

from src.analytics.cagr import cagr_ending_at
from src.analytics.ratios import FINANCIALS_SECTOR, return_on_capital_employed

CONFIG_PATH = Path("config/screener_config.yaml")
DB_PATH = Path("db/nifty100.db")
SCREENER_OUTPUT_PATH = Path("output/screener_output.xlsx")

# ============================================================
# The 20 KPI columns shown in every preset sheet.
# ============================================================
KPI_COLUMNS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "interest_coverage",
    "asset_turnover",
    "free_cash_flow_cr",
    "cash_from_operations_cr",
    "total_debt_cr",
    "earnings_per_share",
    "book_value_per_share",
    "dividend_payout_ratio_pct",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "eps_cagr_5yr",
    "pe_ratio",
    "pb_ratio",
    "dividend_yield_pct",
]

# Composite score weights (Day 17 weighted scheme, sums to 100).
QUALITY_WEIGHTS = {
    "roe_score": 15.0,  # Profitability 35%
    "roce_score": 10.0,
    "npm_score": 10.0,
    "fcf_cagr_score": 15.0,  # Cash quality 30%
    "cfo_pat_score": 10.0,
    "fcf_pos_score": 5.0,
    "rev_cagr_score": 10.0,  # Growth 20%
    "pat_cagr_score": 10.0,
    "de_score": 10.0,  # Leverage 15%
    "icr_score": 5.0,
}

# Continuous component scores -> their source metric columns.
COMPONENT_METRICS = {
    "roe_score": "return_on_equity_pct",
    "roce_score": "return_on_capital_employed_pct",
    "npm_score": "net_profit_margin_pct",
    "fcf_cagr_score": "fcf_cagr_5yr",
    "cfo_pat_score": "cfo_pat_ratio",
    "rev_cagr_score": "revenue_cagr_5yr",
    "pat_cagr_score": "pat_cagr_5yr",
    "de_score": "debt_to_equity",
    "icr_score": "interest_coverage",
}


def load_config(path=CONFIG_PATH):
    """Load the analyst-editable screener configuration."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# ============================================================
# FEATURE FRAME
# ============================================================


def _num(value):
    """Return float or None for a possibly-NaN numeric value."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_year(year_value):
    """Convert 'YYYY-MM' TEXT year to an integer year (YYYY)."""
    text = str(year_value)
    if not text or len(text) < 4:
        return None
    try:
        return int(text[:4])
    except ValueError:
        return None


def _pick_baseline(group):
    """Latest year with ROE, falling back to the latest year overall."""
    ordered = group.sort_values("year")
    with_roe = ordered.dropna(subset=["return_on_equity_pct"])
    if not with_roe.empty:
        return with_roe.iloc[-1]
    return ordered.iloc[-1]


def load_feature_frame(db_path=DB_PATH):
    """
    Build the per-company feature frame used by all presets.

    One row per company - the latest fiscal year with a computed ROE -
    enriched with P&L, market-cap and derived metrics.

    Returns a DataFrame with the 20 KPI columns plus every column the
    presets filter on (pe, pb, dividend yield, market cap, sales, net
    profit, 3-year CAGR, FCF CAGR, CFO/PAT, D/E decline flag, icr_label).
    """

    conn = sqlite3.connect(db_path)
    try:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios", conn)
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
        market_cap = pd.read_sql_query(
            "SELECT company_id, year, pe_ratio, pb_ratio, "
            "dividend_yield_pct, market_cap_crore FROM market_cap",
            conn,
        )
        profitandloss = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit, operating_profit, "
            "other_income FROM profitandloss",
            conn,
        )
        balancesheet = pd.read_sql_query(
            "SELECT company_id, year, equity_capital, reserves, borrowings "
            "FROM balancesheet",
            conn,
        )
        cashflow = pd.read_sql_query(
            "SELECT company_id, year, operating_activity FROM cashflow", conn
        )
    finally:
        conn.close()

    ratios["year_int"] = ratios["year"].apply(_int_year)
    market_cap["year_int"] = market_cap["year"].apply(_int_year)
    profitandloss["year_int"] = profitandloss["year"].apply(_int_year)

    baseline = (
        ratios.sort_values("year")
        .groupby("company_id", group_keys=False)
        .apply(_pick_baseline, include_groups=False)
        .reset_index()
    )

    frame = baseline.merge(
        companies.rename(columns={"id": "company_master_id"}),
        left_on="company_id",
        right_on="company_master_id",
        how="left",
    ).drop(columns=["company_master_id"])
    frame = frame.merge(sectors, on="company_id", how="left")

    frame = frame.merge(
        market_cap[
            [
                "company_id",
                "year_int",
                "pe_ratio",
                "pb_ratio",
                "dividend_yield_pct",
                "market_cap_crore",
            ]
        ],
        on=["company_id", "year_int"],
        how="left",
    )
    frame = frame.merge(
        profitandloss[
            [
                "company_id",
                "year",
                "sales",
                "net_profit",
                "operating_profit",
                "other_income",
            ]
        ],
        on=["company_id", "year"],
        how="left",
        suffixes=("", "_pl"),
    )
    frame = frame.merge(
        balancesheet[
            ["company_id", "year", "equity_capital", "reserves", "borrowings"]
        ],
        on=["company_id", "year"],
        how="left",
    )
    frame = frame.merge(
        cashflow[["company_id", "year", "operating_activity"]],
        on=["company_id", "year"],
        how="left",
    )

    # ---- ROCE (EBIT / capital employed; EBIT = op profit + other income).
    roce = []
    for _, row in frame.iterrows():
        op_profit = _num(row.get("operating_profit"))
        other_income = _num(row.get("other_income"))
        ebit = None if op_profit is None else op_profit + (other_income or 0.0)
        roce.append(
            return_on_capital_employed(
                ebit,
                _num(row.get("equity_capital")),
                _num(row.get("reserves")),
                _num(row.get("borrowings")),
            )
        )
    frame["return_on_capital_employed_pct"] = roce

    # ---- Per-company time series for the derived growth metrics.
    revenue_series = {}
    for company_id, group in profitandloss.groupby("company_id"):
        series = {
            int(g["year_int"]): _num(g["sales"])
            for _, g in group.iterrows()
            if g["year_int"] is not None and _num(g["sales"]) is not None
        }
        revenue_series[company_id] = series

    fcf_series = {}
    for company_id, group in ratios.groupby("company_id"):
        series = {
            int(g["year_int"]): _num(g["free_cash_flow_cr"])
            for _, g in group.iterrows()
            if g["year_int"] is not None and _num(g["free_cash_flow_cr"]) is not None
        }
        fcf_series[company_id] = series

    de_history = {}
    for company_id, group in ratios.groupby("company_id"):
        history = sorted(
            (g["year"], _num(g["debt_to_equity"]))
            for _, g in group.iterrows()
            if _num(g["debt_to_equity"]) is not None
        )
        de_history[company_id] = history

    three_yr = []
    fcf_cagrs = []
    de_declining = []
    cfo_pat = []

    for _, row in frame.iterrows():
        company_id = row["company_id"]
        year = row["year"]
        iyear = _int_year(year)

        growth, _ = cagr_ending_at(revenue_series.get(company_id, {}), iyear, 3)
        three_yr.append(growth)

        fcf_growth, _ = cagr_ending_at(fcf_series.get(company_id, {}), iyear, 5)
        fcf_cagrs.append(fcf_growth)

        de_declining.append(_is_declining(de_history.get(company_id, []), year))

        cfo_value = _num(row.get("cash_from_operations_cr"))
        pat_value = _num(row.get("net_profit"))
        if cfo_value is not None and pat_value is not None and abs(pat_value) >= 1e-9:
            cfo_pat.append(cfo_value / pat_value)
        else:
            cfo_pat.append(None)

    frame["revenue_cagr_3yr"] = three_yr
    frame["fcf_cagr_5yr"] = fcf_cagrs
    frame["de_declining"] = de_declining
    frame["cfo_pat_ratio"] = cfo_pat
    frame["fcf_positive"] = frame["free_cash_flow_cr"].apply(
        lambda v: _num(v) is not None and _num(v) > 0
    )

    return frame


def _is_declining(history, current_year):
    """True when D/E decreased from the previous year to the current."""
    if len(history) < 2:
        return False
    current = None
    previous = None
    for year, value in history:
        if year == current_year:
            current = value
        elif year < current_year:
            previous = value
    if current is None or previous is None:
        return False
    return current < previous


# ============================================================
# COMPOSITE QUALITY SCORE (Day 17)
# ============================================================


def _winsorize_bounds(series):
    """Return (P10, P90) of a numeric series with missing values."""
    present = pd.to_numeric(series, errors="coerce").dropna()
    if present.empty:
        return None, None
    return present.quantile(0.10), present.quantile(0.90)


def _scale_with_bounds(series, p_low, p_high):
    """Clip a series to [P10, P90] and scale to 0-100. NaN -> NaN."""
    series = pd.to_numeric(series, errors="coerce")
    if p_low is None or p_high is None or p_high <= p_low:
        return pd.Series([None] * len(series), index=series.index)
    clipped = series.clip(lower=p_low, upper=p_high)
    scaled = (clipped - p_low) / (p_high - p_low) * 100.0
    return scaled.where(series.notna())


def compute_component_scores(frame, bounds_by_sector=False):
    """
    Compute the ten 0-100 component scores.

    bounds_by_sector=False -> P10/P90 winsorisation across the whole
    universe. bounds_by_sector=True -> winsorisation within each
    broad_sector (sector-relative normalisation).
    """

    scores = pd.DataFrame(index=frame.index)
    has_sector = "broad_sector" in frame.columns

    for score_name, metric in COMPONENT_METRICS.items():
        if metric not in frame.columns:
            scores[score_name] = None
            continue

        if not bounds_by_sector or not has_sector:
            p_low, p_high = _winsorize_bounds(frame[metric])
            scores[score_name] = _scale_with_bounds(frame[metric], p_low, p_high)
        else:
            result = pd.Series([None] * len(frame), index=frame.index)
            for _, group in frame.groupby("broad_sector"):
                p_low, p_high = _winsorize_bounds(group[metric])
                result.loc[group.index] = _scale_with_bounds(
                    group[metric], p_low, p_high
                )
            scores[score_name] = result

    # FCF positive is a flag, not a ratio - never winsorised.
    if "fcf_positive" in frame.columns:
        flag_values = frame["fcf_positive"]
    else:
        flag_values = frame.get("free_cash_flow_cr").apply(
            lambda v: _num(v) is not None and _num(v) > 0
        )
    scores["fcf_pos_score"] = flag_values.apply(lambda v: 100.0 if v else 0.0)

    # D/E: inverse - a lower D/E gives a higher score.
    scores["de_score"] = 100.0 - scores["de_score"]

    return scores


def composite_from_scores(scores):
    """Weighted mean over the available component scores (0-100)."""

    columns = list(QUALITY_WEIGHTS)
    weights = pd.Series(QUALITY_WEIGHTS)
    weighted = scores[columns].mul(weights, axis=1)
    present_weight = scores[columns].notna().mul(weights).sum(axis=1)

    composite = weighted.sum(axis=1).where(present_weight > 0, None)
    composite = composite / present_weight.where(present_weight > 0, None)
    return composite.round(1)


def compute_composite_score(frame):
    """
    Add `composite_quality_score` (global winsorisation) and
    `composite_quality_score_sector` (within-sector winsorisation).
    """

    result = frame.copy()
    global_scores = compute_component_scores(result, bounds_by_sector=False)
    sector_scores = compute_component_scores(result, bounds_by_sector=True)
    result["composite_quality_score"] = composite_from_scores(global_scores)
    result["composite_quality_score_sector"] = composite_from_scores(sector_scores)
    return result


# ============================================================
# FILTER CORE (Day 15)
# ============================================================


def _resolve_filter(config, filter_spec):
    metric_key = filter_spec["metric"]
    metric_config = config["metrics"].get(metric_key, {})
    return (
        metric_config.get("column", metric_key),
        filter_spec.get("operator", ">"),
        filter_spec["value"],
        bool(metric_config.get("skip_financials", False)),
        bool(metric_config.get("debt_free_passes", False)),
    )


def _is_bool_scalar(value):
    """True for Python bools and numpy bool scalars."""
    if isinstance(value, bool):
        return True
    dtype = getattr(value, "dtype", None)
    return dtype is not None and "bool" in str(dtype)


def _evaluate(value, operator, threshold):
    """Compare one value against a threshold. Missing values always fail."""

    if isinstance(threshold, bool):
        if not _is_bool_scalar(value):
            return False
        if operator in ("==", "="):
            return bool(value) == threshold
        if operator == "!=":
            return bool(value) != threshold
        return False

    if value is None or pd.isna(value):
        return False

    try:
        numeric = float(value)
        target = float(threshold)
    except (TypeError, ValueError):
        return False

    if operator in (">",):
        return numeric > target
    if operator in (">=",):
        return numeric >= target
    if operator in ("<",):
        return numeric < target
    if operator in ("<=",):
        return numeric <= target
    if operator in ("==", "="):
        return abs(numeric - target) < 1e-9
    if operator == "!=":
        return abs(numeric - target) >= 1e-9
    return False


def apply_filters(frame, config, filter_specs):
    """
    Apply a list of preset filters to the feature frame.

    Returns the companies passing every filter. Financials are skipped
    automatically for D/E filters; Debt Free companies pass any ICR
    filter.
    """

    mask = pd.Series(True, index=frame.index)

    for filter_spec in filter_specs:
        column, operator, threshold, skip_financials, debt_free_passes = (
            _resolve_filter(config, filter_spec)
        )

        if column not in frame.columns:
            mask &= False
            continue

        financial = frame.get("broad_sector") == FINANCIALS_SECTOR
        is_de_filter = column == "debt_to_equity"
        # The Financials carve-out applies only to D/E *max* filters
        # (D/E < X / D/E <= X). An exact-zero ("==") D/E test still
        # applies to Financials.
        de_skip_applies = is_de_filter and skip_financials and operator in ("<", "<=")

        for idx in frame.index:
            if de_skip_applies and financial.loc[idx]:
                continue

            if (
                debt_free_passes
                and column == "interest_coverage"
                and frame.loc[idx, "icr_label"] == "Debt Free"
            ):
                continue

            if not _evaluate(frame.loc[idx, column], operator, threshold):
                mask.loc[idx] = False

    return frame[mask]


def run_preset(frame, config, preset_key):
    """
    Run one preset: apply its filters then sort by composite score
    (highest quality first). Guarantees the composite column exists.
    """

    if "composite_quality_score" not in frame.columns:
        frame = compute_composite_score(frame)

    preset = config["presets"][preset_key]
    filtered = apply_filters(frame, config, preset["filters"])
    sorted_frame = filtered.sort_values("composite_quality_score", ascending=False)

    return {
        "key": preset_key,
        "name": preset.get("name", preset_key),
        "description": preset.get("description", ""),
        "filters": preset["filters"],
        "frame": sorted_frame,
    }


def main():
    """Run all presets and write output/screener_output.xlsx."""

    from src.screener.export import write_screener_workbook

    config = load_config()
    db_path = Path(config.get("db_path", "db/nifty100.db"))
    frame = load_feature_frame(db_path)
    frame = compute_composite_score(frame)

    results = {key: run_preset(frame, config, key) for key in config["presets"]}
    write_screener_workbook(
        results, all_frame=frame, path=SCREENER_OUTPUT_PATH, config=config
    )

    print("=" * 60)
    print("NIFTY100 SCREENER (Sprint 3)")
    print("=" * 60)
    for key, result in results.items():
        print(f"  {result['name']:22s}: {len(result['frame']):3d} companies")
    print(f"\n  Output: {SCREENER_OUTPUT_PATH}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    main()
