"""
Nifty100 Financial Ratio Engine (Sprint 2, Day 12).

Computes the full KPI set for every (company_id, year) in the union of
the P&L, Balance Sheet and Cash Flow tables, then populates the
`financial_ratios` table (1,100+ rows, no all-null KPI column).

Also produces:
- output/capital_allocation.csv   (Day 11)
- output/ratio_edge_cases.log     (Day 13 cross-checks)

Run after a full load:
    python -m src.analytics.engine

Design:
- Universe = union of P&L / BS / CF company-years (>= 1100 rows).
- Formula KPIs (NPM, OPM, ROE, ROA, D/E, ICR, turnover, FCF, ...)
  come from the three statements via src.analytics.ratios.
- CAGR columns (5y) come from src.analytics.cagr with flags.
- CFO quality / capital allocation come from src.analytics.cashflow_kpis.
- Source-provided values the statements cannot reproduce
  (book_value_per_share, capex_cr) are merged from the source
  financial_ratios file via the freshly-loaded table.
- Cross-checks (OPM mismatch, ROCE/ROE vs reported) are logged to
  output/ratio_edge_cases.log (Day 13).
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import cagr_ending_at
from src.analytics.cashflow_kpis import cfo_quality_score
from src.analytics.ratios import (
    FINANCIALS_SECTOR,
    OPM_TOLERANCE_PP,
    asset_turnover,
    cross_check_opm,
    debt_to_equity,
    high_leverage_flag,
    icr_warning_flag,
    interest_coverage,
    interest_coverage_label,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_equity,
    roce_sector_benchmark,
)

DB_PATH = Path("db/nifty100.db")
OUTPUT_DIR = Path("output")
CAP_ALLOC_FILE = OUTPUT_DIR / "capital_allocation.csv"
EDGE_CASES_FILE = OUTPUT_DIR / "ratio_edge_cases.log"

YEAR_INT = "year_int"
CASH_FLOW_COLUMN = "cash_flow"

# Source-provided columns the statements cannot reproduce.
SOURCE_ONLY_COLUMNS = [
    "book_value_per_share",
    "capex_cr",
    "free_cash_flow_cr",
]

FINANCIAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    net_profit_margin_pct NUMERIC,
    operating_profit_margin_pct NUMERIC,
    return_on_equity_pct NUMERIC,
    return_on_assets_pct NUMERIC,
    debt_to_equity NUMERIC,
    interest_coverage NUMERIC,
    asset_turnover NUMERIC,
    free_cash_flow_cr NUMERIC,
    capex_cr NUMERIC,
    earnings_per_share NUMERIC,
    book_value_per_share NUMERIC,
    dividend_payout_ratio_pct NUMERIC,
    total_debt_cr NUMERIC,
    cash_from_operations_cr NUMERIC,
    revenue_cagr_5yr NUMERIC,
    pat_cagr_5yr NUMERIC,
    eps_cagr_5yr NUMERIC,
    composite_quality_score NUMERIC,
    high_leverage_flag TEXT,
    icr_label TEXT,
    icr_warning_flag TEXT,
    revenue_cagr_5yr_flag TEXT,
    pat_cagr_5yr_flag TEXT,
    eps_cagr_5yr_flag TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE (company_id, year)
);
"""


def _int_year(year_value):
    """Convert 'YYYY-MM' TEXT year to integer year (YYYY)."""
    s = str(year_value)
    if not s or len(s) < 4:
        return None
    try:
        return int(s[:4])
    except ValueError:
        return None


def load_statements(conn):
    """Load all statement and reference tables from SQLite."""

    def read(name):
        df = pd.read_sql_query(f"SELECT * FROM {name}", conn)
        if name in ("profitandloss", "balancesheet", "cashflow"):
            df[YEAR_INT] = df["year"].apply(_int_year)
        return df

    return {
        name: read(name)
        for name in (
            "companies",
            "sectors",
            "profitandloss",
            "balancesheet",
            "cashflow",
            "financial_ratios",
        )
    }


def build_universe(tables):
    """
    Build the population universe: union of (company_id, year) pairs
    from P&L, BS and CF tables.
    """

    frames = [
        tables[name][["company_id", "year"]].drop_duplicates()
        for name in ("profitandloss", "balancesheet", "cashflow")
    ]
    universe = pd.concat(frames, ignore_index=True).drop_duplicates()
    universe = universe.sort_values(["company_id", "year"]).reset_index(drop=True)
    universe[YEAR_INT] = universe["year"].apply(_int_year)
    return universe


def _num(value):
    """Return float or None for a possibly-NaN numeric value."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _scalar(frame, column):
    """Return a scalar value from a squeezed series/row safely."""
    value = frame.get(column)
    if hasattr(value, "to_list"):
        value = value.iloc[0] if hasattr(value, "iloc") else value
    return value


def compute_ratios_row_by_row(universe, tables):
    """
    Compute per-row KPIs from the three statements.

    Returns:
        pandas.DataFrame: universe plus computed KPI columns.
        list[dict]: OPM cross-check edge cases.
    """

    pl = tables["profitandloss"].set_index(["company_id", "year"], drop=False)
    bs = tables["balancesheet"].set_index(["company_id", "year"], drop=False)
    cf = tables["cashflow"].set_index(["company_id", "year"], drop=False)
    sectors = tables["sectors"].set_index("company_id", drop=False)

    rows = []
    edge_cases = []

    for row in universe.itertuples(index=False):
        key = (row.company_id, row.year)

        p = pl.loc[key] if key in pl.index else None
        b = bs.loc[key] if key in bs.index else None
        c = cf.loc[key] if key in cf.index else None

        out = {
            "company_id": row.company_id,
            "year": row.year,
            YEAR_INT: row.year_int,
        }

        # ---- Sector context ------------------------------------------------
        broad_sector = None
        if row.company_id in sectors.index:
            sector_row = sectors.loc[row.company_id]
            value = sector_row.get("broad_sector")
            if hasattr(value, "to_list"):
                value = value.iloc[0] if hasattr(value, "iloc") else value
            if value is not None and pd.notna(value):
                broad_sector = str(value)

        out["broad_sector"] = broad_sector

        # ---- P&L -----------------------------------------------------------
        sales = op_profit = other_income = interest = None
        net_profit = eps = dividend_payout = None

        if p is not None:
            sales = _num(_scalar(p, "sales"))
            op_profit = _num(_scalar(p, "operating_profit"))
            other_income = _num(_scalar(p, "other_income"))
            interest = _num(_scalar(p, "interest"))
            net_profit = _num(_scalar(p, "net_profit"))
            eps = _num(_scalar(p, "eps"))
            dividend_payout = _num(_scalar(p, "dividend_payout"))

        out["sales"] = sales
        out["net_profit"] = net_profit
        out["earnings_per_share"] = eps
        out["dividend_payout_ratio_pct"] = dividend_payout
        out["net_profit_margin_pct"] = net_profit_margin(net_profit, sales)
        out["operating_profit_margin_pct"] = operating_profit_margin(op_profit, sales)

        opm_reported = _num(_scalar(p, "opm_percentage")) if p is not None else None
        mismatch, diff_pp = cross_check_opm(
            out["operating_profit_margin_pct"], opm_reported
        )
        if mismatch:
            # Reported values far outside any plausible operating margin
            # are source-data artefacts (already flagged as DQ-03 in
            # Sprint 1) rather than formula discrepancies.
            if opm_reported is not None and not _is_plausible_opm(opm_reported):
                category = "opm_source_data_artefact"
            else:
                category = "opm_cross_check"
            edge_cases.append(
                {
                    "category": category,
                    "company_id": row.company_id,
                    "year": row.year,
                    "detail": (
                        f"computed OPM {out['operating_profit_margin_pct']:.2f}% vs "
                        f"reported {opm_reported:.2f}% (diff {diff_pp:.2f}pp > "
                        f"{OPM_TOLERANCE_PP}pp)"
                    ),
                }
            )

        # ---- Balance Sheet --------------------------------------------------
        if b is not None:
            equity_capital = _num(_scalar(b, "equity_capital"))
            reserves = _num(_scalar(b, "reserves"))
            borrowings = _num(_scalar(b, "borrowings"))
            total_assets = _num(_scalar(b, "total_assets"))

            out["total_debt_cr"] = borrowings
            out["return_on_equity_pct"] = return_on_equity(
                net_profit, equity_capital, reserves
            )
            out["return_on_assets_pct"] = return_on_assets(net_profit, total_assets)
            out["debt_to_equity"] = debt_to_equity(borrowings, equity_capital, reserves)
            out["asset_turnover"] = asset_turnover(sales, total_assets)
        else:
            equity_capital = reserves = borrowings = None
            out["total_debt_cr"] = None
            out["return_on_equity_pct"] = None
            out["return_on_assets_pct"] = None
            out["debt_to_equity"] = None
            out["asset_turnover"] = None

        # ---- Cash flow -------------------------------------------------------
        cash_flow = {"operating": None, "investing": None, "financing": None}
        if c is not None:
            operating_activity = _num(_scalar(c, "operating_activity"))
            investing_activity = _num(_scalar(c, "investing_activity"))
            financing_activity = _num(_scalar(c, "financing_activity"))

            cash_flow = {
                "operating": operating_activity,
                "investing": investing_activity,
                "financing": financing_activity,
            }
            out["cash_from_operations_cr"] = operating_activity
        else:
            out["cash_from_operations_cr"] = None

        out[CASH_FLOW_COLUMN] = cash_flow

        # ---- Leverage / coverage ----------------------------------------------
        out["high_leverage_flag"] = high_leverage_flag(
            out["debt_to_equity"], broad_sector
        )
        icr = interest_coverage(op_profit, other_income, interest)
        out["interest_coverage"] = icr
        out["icr_label"] = interest_coverage_label(icr)
        out["icr_warning_flag"] = icr_warning_flag(icr)

        # ---- ROCE (sector-relative for Financials) ------------------------------
        # EBIT ~ operating_profit + other_income per Day 08 design.
        ebit = None
        if op_profit is not None:
            ebit = op_profit + (other_income if other_income is not None else 0.0)

        roce, roce_method = roce_sector_benchmark(
            ebit,
            equity_capital,
            reserves,
            borrowings,
            broad_sector,
        )
        out["return_on_capital_employed_pct"] = roce
        out["capital_employed_method"] = roce_method

        rows.append(out)

    result = pd.DataFrame(rows)
    return result, edge_cases


def compute_cagrs(result, tables):
    """
    Compute trailing 5-year CAGR for sales, PAT and EPS per row.

    For every (company, year) the CAGR is measured over the window
    ending at that year (the 2024 row uses 2019..2024).
    """

    pl = tables["profitandloss"].dropna(subset=[YEAR_INT])

    series_map = {"revenue": {}, "pat": {}, "eps": {}}

    for company_id, group in pl.groupby("company_id"):
        revenue_series = {}
        pat_series = {}
        eps_series = {}

        for _, g in group.iterrows():
            iyear = int(g[YEAR_INT])
            sales = _num(g.get("sales"))
            pat = _num(g.get("net_profit"))
            eps = _num(g.get("eps"))

            if sales is not None:
                revenue_series[iyear] = sales
            if pat is not None:
                pat_series[iyear] = pat
            if eps is not None:
                eps_series[iyear] = eps

        series_map["revenue"][company_id] = revenue_series
        series_map["pat"][company_id] = pat_series
        series_map["eps"][company_id] = eps_series

    column_map = {
        "revenue": "revenue_cagr_5yr",
        "pat": "pat_cagr_5yr",
        "eps": "eps_cagr_5yr",
    }

    for kind, column in column_map.items():
        flag_column = column + "_flag"
        result[column] = None
        result[flag_column] = None

    for row_index in result.index:
        company_id = result.at[row_index, "company_id"]
        iyear = result.at[row_index, YEAR_INT]
        if iyear is None:
            continue

        for kind, column in column_map.items():
            series = series_map[kind].get(company_id, {})
            value, flag = cagr_ending_at(series, int(iyear), 5)
            result.at[row_index, column] = value
            result.at[row_index, column + "_flag"] = flag

    return result


def compute_cfo_quality(result, tables):
    """
    Compute trailing 5-year CFO quality score (average CFO/PAT ratio)
    per row, using the last 5 fiscal years ending at each row's year.
    """

    pl = tables["profitandloss"].dropna(subset=[YEAR_INT])
    cf = tables["cashflow"].dropna(subset=[YEAR_INT])

    result["cfo_quality_score"] = None

    # Build per-company aligned cfo/pat values by year.
    company_cfo = {}
    company_pat = {}

    for company_id, group in cf.groupby("company_id"):
        company_cfo[company_id] = {
            int(g[YEAR_INT]): _num(g.get("operating_activity"))
            for _, g in group.iterrows()
        }

    for company_id, group in pl.groupby("company_id"):
        company_pat[company_id] = {
            int(g[YEAR_INT]): _num(g.get("net_profit")) for _, g in group.iterrows()
        }

    for row_index in result.index:
        company_id = result.at[row_index, "company_id"]
        iyear = result.at[row_index, YEAR_INT]
        if iyear is None:
            continue

        cfo_by_year = company_cfo.get(company_id, {})
        pat_by_year = company_pat.get(company_id, {})

        # Window of years: (iyear-4) .. iyear.
        cfo_values = []
        pat_values = []
        for i in range(4, -1, -1):
            year = int(iyear) - i
            cfo_values.append(cfo_by_year.get(year))
            pat_values.append(pat_by_year.get(year))

        result.at[row_index, "cfo_quality_score"] = cfo_quality_score(
            cfo_values, pat_values, window_years=5
        )

    return result


def compute_composite_quality_score(result):
    """
    Composite quality score (0-100): unweighted mean of capped sub-scores.

    Sub-scores (each coerced to 0-100):
    - ROE:            capped at 40% (100 points at 40% ROE)
    - NPM:            capped at 20% (100 points at 20% net margin)
    - ROCE:           capped at 40% (100 points at 40% ROCE)
    - Revenue 5y CAGR: capped at 25% (100 points at 25% CAGR)
    - CFO quality:     used directly (0-2 clamped to 100 points)
    """

    sub_scores = []

    specs = [
        (result["return_on_equity_pct"], 40.0),
        (result["net_profit_margin_pct"], 20.0),
        (result["return_on_capital_employed_pct"], 40.0),
        (result["revenue_cagr_5yr"], 25.0),
        (result["cfo_quality_score"], 2.0),
    ]

    for series, scale in specs:
        sub_scores.append(series.clip(lower=0, upper=scale) / scale * 100.0)

    stacked = pd.concat(sub_scores, axis=1)
    result["composite_quality_score"] = stacked.mean(axis=1).round(1)

    return result


def merge_source_values(result, source):
    """
    Merge source-provided values (book_value_per_share, capex_cr,
    free_cash_flow_cr) from the source financial_ratios table.
    """

    if source is None or source.empty:
        return result

    source_map = source.set_index(["company_id", "year"])

    for column in SOURCE_ONLY_COLUMNS:
        if column not in source_map.columns or column in result.columns:
            continue

        result[column] = result.apply(
            lambda r: (
                _num(source_map.loc[(r["company_id"], r["year"]), column])
                if (r["company_id"], r["year"]) in source_map.index
                else None
            ),
            axis=1,
        )

    return result


def ensure_financial_ratios_table(conn):
    """Drop and recreate financial_ratios using the extended Sprint 2 schema."""
    conn.execute("DROP TABLE IF EXISTS financial_ratios")
    conn.execute(FINANCIAL_TABLE_SQL)
    conn.commit()


def persist(result, conn):
    """
    Upsert computed rows into financial_ratios.

    Returns:
        int: number of rows written.
    """

    columns = [
        "company_id",
        "year",
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "return_on_assets_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "capex_cr",
        "earnings_per_share",
        "book_value_per_share",
        "dividend_payout_ratio_pct",
        "total_debt_cr",
        "cash_from_operations_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "composite_quality_score",
        "high_leverage_flag",
        "icr_label",
        "icr_warning_flag",
        "revenue_cagr_5yr_flag",
        "pat_cagr_5yr_flag",
        "eps_cagr_5yr_flag",
    ]

    data = result[columns].copy()

    bool_columns = {"high_leverage_flag", "icr_warning_flag"}

    for column in data.columns:
        if column in bool_columns:
            data[column] = data[column].apply(
                lambda v: (
                    None if v is None or pd.isna(v) else "True" if bool(v) else "False"
                )
            )
        elif column not in ("company_id", "year"):
            data[column] = data[column].where(pd.notna(data[column]), None)

    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    update_sql = ", ".join(f"{column} = excluded.{column}" for column in columns[2:])

    conn.executemany(
        f"""
        INSERT INTO financial_ratios ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT(company_id, year) DO UPDATE SET {update_sql}
        """,
        data.itertuples(index=False, name=None),
    )
    conn.commit()
    return len(data)


def write_capital_allocation_csv(result, path=CAP_ALLOC_FILE):
    """Day 11: capital allocation pattern for every company-year."""

    rows = []
    for row in result.itertuples(index=False):
        cash_flow = getattr(row, CASH_FLOW_COLUMN)
        if not cash_flow:
            continue

        from src.analytics.cashflow_kpis import capital_allocation_pattern

        pattern = capital_allocation_pattern(
            cash_flow["operating"],
            cash_flow["investing"],
            cash_flow["financing"],
        )
        rows.append(
            {
                "company_id": row.company_id,
                "year": row.year,
                "cfo_sign": _sign(cash_flow["operating"]),
                "cfi_sign": _sign(cash_flow["investing"]),
                "cff_sign": _sign(cash_flow["financing"]),
                "pattern_label": pattern,
            }
        )

    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)

    return len(frame)


def _is_plausible_opm(percentage):
    """Operating margins beyond [-200%, 300%] are source-data artefacts."""
    if percentage is None:
        return True
    return -200.0 <= percentage <= 300.0


def _sign(value):
    if value is None:
        return ""
    return "+" if float(value) >= 0 else "-"


def _latest_reported(companies, company_id, column):
    match = companies[companies["id"] == company_id]
    if match.empty:
        return None
    value = match[column].iloc[0]
    if value is None or pd.isna(value):
        return None
    return float(value)


def write_edge_cases_log(result, edge_cases, tables, path=EDGE_CASES_FILE):
    """
    Day 13: write OPM/ROCE/ROE cross-check anomalies to a log file.

    Entries are categorised as opm_cross_check, roce_vs_reported or
    roe_vs_reported.
    """

    companies = tables["companies"]
    latest_per_company = result.sort_values(YEAR_INT, ascending=False).drop_duplicates(
        "company_id"
    )

    roce_cases = []
    roe_cases = []

    for _, row in latest_per_company.iterrows():
        company_id = row["company_id"]

        computed_roce = _num(row.get("return_on_capital_employed_pct"))
        reported_roce = _latest_reported(companies, company_id, "roce_percentage")
        if computed_roce is not None and reported_roce is not None:
            diff = abs(computed_roce - reported_roce)
            if diff > 5.0:
                roce_cases.append((company_id, computed_roce, reported_roce, diff))

        computed_roe = _num(row.get("return_on_equity_pct"))
        reported_roe = _latest_reported(companies, company_id, "roe_percentage")
        if computed_roe is not None and reported_roe is not None:
            diff = abs(computed_roe - reported_roe)
            if diff > 5.0:
                roe_cases.append((company_id, computed_roe, reported_roe, diff))

    lines = []
    lines.append("NIFTY100 RATIO ENGINE EDGE CASES (Sprint 2, Day 13)")
    lines.append("=" * 60)

    lines.append(f"\n[1] Reported OPM cross-check (tolerance {OPM_TOLERANCE_PP}pp):")
    genuine = [e for e in edge_cases if e["category"] == "opm_cross_check"]
    artefacts = [e for e in edge_cases if e["category"] == "opm_source_data_artefact"]
    lines.append(
        f"    total mismatches: {len(edge_cases)} "
        f"(genuine {len(genuine)}, source-data artefact {len(artefacts)})"
    )
    lines.append("\n    Genuine mismatches (reported value is a plausible margin):")
    for entry in genuine:
        lines.append(f"      {entry['company_id']} {entry['year']}: {entry['detail']}")
    lines.append(
        "\n    Source-data artefacts (reported value outside [-200%, 300%], "
        "blanket DQ-03 class in Sprint 1):"
    )
    for entry in artefacts:
        lines.append(f"      {entry['company_id']} {entry['year']}: {entry['detail']}")

    lines.append("\n[2] ROCE vs companies.roce_percentage (latest year, diff > 5%):")
    lines.append(f"    entries: {len(roce_cases)}")
    for company_id, computed, reported, diff in roce_cases:
        lines.append(
            f"    {company_id}: computed {computed:.2f}% vs reported "
            f"{reported:.2f}% (diff {diff:.2f}pp)"
        )

    lines.append("\n[3] ROE vs companies.roe_percentage (latest year, diff > 5%):")
    lines.append(f"    entries: {len(roe_cases)}")
    for company_id, computed, reported, diff in roe_cases:
        lines.append(
            f"    {company_id}: computed {computed:.2f}% vs reported "
            f"{reported:.2f}% (diff {diff:.2f}pp)"
        )

    lines.append("\n[4] Implausible computed ROE (source-data balance sheet anomaly):")
    absurd_roe = result[
        result["return_on_equity_pct"].notna()
        & (result["return_on_equity_pct"].abs() > 100.0)
    ].sort_values(["company_id", YEAR_INT])
    lines.append(f"    entries: {len(absurd_roe)}")
    for _, row in absurd_roe.iterrows():
        lines.append(
            f"      {row['company_id']} {row['year']}: ROE {row['return_on_equity_pct']:.1f}% "
            f"(BS equity+reserves small vs P&L profit - check source scale)"
        )

    financial_count = tables["sectors"]["broad_sector"].eq(FINANCIALS_SECTOR).sum()
    lines.append(
        f"\n[5] Financials carve-out: {int(financial_count)} companies in "
        f"broad_sector='{FINANCIALS_SECTOR}' -> D/E high-leverage flag "
        f"suppressed and ROCE reported as sector-relative."
    )

    lines.append("\n[6] Notes")
    lines.append(
        "  - Project doc lists 19 Financials (banks/NBFCs/insurance); the data "
        "holds the full Financials broad sector, which currently has "
        f"{int(financial_count)} companies. Carve-out applies to all."
    )
    lines.append(
        "  - Reported ROCE/ROE come from companies.xlsx (single latest snapshot); "
        "computed values are per fiscal year. Differences > 5pp are expected "
        "for companies whose reported snapshot is not the latest fiscal year."
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    """Run the full ratio engine pipeline."""

    logging.basicConfig(level=logging.INFO)
    conn = sqlite3.connect(DB_PATH)

    print("=" * 60)
    print("NIFTY100 FINANCIAL RATIO ENGINE")
    print("=" * 60)

    tables = load_statements(conn)
    universe = build_universe(tables)
    print(
        f"\nUniverse: {len(universe)} company-years "
        f"({universe['company_id'].nunique()} companies)"
    )

    result, edge_cases = compute_ratios_row_by_row(universe, tables)
    result = merge_source_values(result, tables["financial_ratios"])
    result = compute_cagrs(result, tables)
    result = compute_cfo_quality(result, tables)
    result = compute_composite_quality_score(result)

    ensure_financial_ratios_table(conn)
    count = persist(result, conn)

    cap_alloc_count = write_capital_allocation_csv(result)
    write_edge_cases_log(result, edge_cases, tables)

    print(f"  Ratios upserted:  {count}")
    print(f"  Capital allocation rows: {cap_alloc_count}")
    print(f"  Output: {CAP_ALLOC_FILE}")
    print(f"  Output: {EDGE_CASES_FILE}")

    conn.close()


if __name__ == "__main__":
    main()
