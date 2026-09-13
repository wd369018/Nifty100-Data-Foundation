"""NLP Analysis-text parser (Sprint 5, Day 29).

Reads the free-text CAGR / ROE fields inside data/raw/*analysis.xlsx and
converts them into structured rows using a regex, e.g.

    10 Years: 21%            ->  period_years=10, value_pct=21.0

Target fields:
    compounded_sales_growth, compounded_profit_growth,
    stock_price_cagr, roe

Outputs:
    output/analysis_parsed.csv     (company_id, metric_type, period_years, value_pct)
    output/parse_failures.csv      (entries that did not match the pattern)
    output/analysis_divergence.csv (parsed CAGR vs Ratio-Engine CAGR, |diff| > 5 pp)

Run:  python -m src.nlp.parser
"""

import glob
import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.cagr import cagr_ending_at

# Spec pattern: (\d+)\s*Years?:?\s*([\d.]+)%
# Sign superset: an optional minus is captured so '1 Year: -2%' keeps its sign
# (without it the value would silently flip from -2 to +2).
ANALYSIS_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*(-?[\d.]+)%")
ANALYSIS_XLSX_GLOB = "data/raw/*analysis.xlsx"
DB_PATH = Path("db/nifty100.db")

PARSED_PATH = Path("output/analysis_parsed.csv")
FAILURES_PATH = Path("output/parse_failures.csv")
DIVERGENCE_PATH = Path("output/analysis_divergence.csv")

TARGET_METRICS = [
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
]

# Parsed metric types vs the Ratio-Engine series used to cross-validate.
# 'roe' is a point value (not a CAGR) so it is not cross-validated here.
CROSSCHECK_METRICS = {
    "compounded_sales_growth": ("sales", "revenue"),
    "compounded_profit_growth": ("net_profit", "profit"),
}
DIVERGENCE_THRESHOLD_PP = 5.0


def find_analysis_file():
    """Locate the analysis workbook in data/raw/ (single file expected)."""
    matches = sorted(glob.glob(ANALYSIS_XLSX_GLOB))
    if not matches:
        return None
    return Path(matches[0])


def parse_text_entries(df_raw):
    """Parse every target metric text cell into structured rows.

    Returns (parsed_df, failures_df).  Rows whose text does not match the
    regex are collected into the failures frame instead.
    """
    rows = []
    failures = []

    for _, row in df_raw.iterrows():
        company_id = row.get("company_id")
        if company_id is None or (
            isinstance(company_id, float) and pd.isna(company_id)
        ):
            continue
        company_id = str(company_id).strip()
        for metric in TARGET_METRICS:
            text = row.get(metric)
            if text is None or (isinstance(text, float) and pd.isna(text)):
                continue
            text = str(text).strip()
            match = ANALYSIS_PATTERN.search(text)
            if match is None:
                failures.append(
                    {"company_id": company_id, "metric_type": metric, "text": text}
                )
                continue
            rows.append(
                {
                    "company_id": company_id,
                    "metric_type": metric,
                    "period_years": int(match.group(1)),
                    "value_pct": float(match.group(2)),
                }
            )

    parsed = pd.DataFrame(rows)
    failures = pd.DataFrame(failures)
    return parsed, failures


# ------------------------------------------------------------------
# Cross-validation against the Ratio Engine
# ------------------------------------------------------------------


def _series_by_year(df, value_col):
    """{int_year: value} for a per-company frame ordered by year."""
    series = {}
    for _, r in df.iterrows():
        year = str(r["year"])[:4]
        try:
            series[int(year)] = float(r[value_col])
        except (TypeError, ValueError):
            continue
    return series


def _computed_cagrs(db_path):
    """Per-company {metric: {window: cagr}} from the live DB series."""
    conn = sqlite3.connect(db_path)
    try:
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit FROM profitandloss "
            "ORDER BY company_id, year",
            conn,
        )
    finally:
        conn.close()

    result = {}
    for company_id, group in pl.groupby("company_id"):
        sales = _series_by_year(group, "sales")
        profit = _series_by_year(group, "net_profit")
        latest = max(sales) if sales else None
        entry = {}
        for metric, (col, kind) in CROSSCHECK_METRICS.items():
            series = sales if col == "sales" else profit
            values = {}
            for window in (3, 5, 10):
                if not series or latest is None:
                    values[window] = (None, "INSUFFICIENT")
                    continue
                value, flag = cagr_ending_at(series, latest, window)
                values[window] = (value, flag)
            entry[metric] = values
        result[company_id] = entry
    return result


def cross_validate(parsed, db_path=DB_PATH):
    """Compare parsed CAGR values against the Ratio Engine's recomputation.

    Parsed rows whose period is invalid (not 3/5/10) or whose computed CAGR
    is unavailable (loss-making start, insufficient history) are skipped.
    Rows with |parsed - computed| > 5 pp are returned for manual review.
    """
    computed = _computed_cagrs(db_path)
    rows = []

    for _, row in parsed.iterrows():
        metric = row["metric_type"]
        if metric not in CROSSCHECK_METRICS:
            continue
        window = int(row["period_years"])
        if window not in (3, 5, 10):
            continue
        iso_series, _ = (
            computed.get(row["company_id"], {})
            .get(metric, {})
            .get(window, (None, None))
        )
        if iso_series is None:
            continue
        parsed_pct = float(row["value_pct"])
        diff = abs(parsed_pct - float(iso_series))
        if diff > DIVERGENCE_THRESHOLD_PP:
            rows.append(
                {
                    "company_id": row["company_id"],
                    "metric_type": metric,
                    "period_years": window,
                    "parsed_pct": parsed_pct,
                    "computed_pct": round(float(iso_series), 2),
                    "abs_diff_pct": round(diff, 2),
                }
            )

    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# I/O
# ------------------------------------------------------------------


def main():
    print("=" * 60)
    print("NLP ANALYSIS-TEXT PARSER (Sprint 5, Day 29)")
    print("=" * 60)

    source = find_analysis_file()
    if source is None:
        print(f"  No analysis workbook found at {ANALYSIS_XLSX_GLOB}")
        return 1

    df_raw = pd.read_excel(source, sheet_name=0, header=1)
    parsed, failures = parse_text_entries(df_raw)

    PARSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    parsed.to_csv(PARSED_PATH, index=False)
    failures.to_csv(FAILURES_PATH, index=False)

    divergence = cross_validate(parsed)
    divergence.to_csv(DIVERGENCE_PATH, index=False)

    print(f"  Source            : {source}")
    print(f"  Raw records       : {len(df_raw)}")
    print(f"  Parsed rows       : {len(parsed)}")
    print(f"  Parse failures    : {len(failures)}")
    print(f"  Divergence > 5pp  : {len(divergence)}")
    print(f"\n  Parsed            : {PARSED_PATH}")
    print(f"  Failures          : {FAILURES_PATH}")
    print(f"  Divergence        : {DIVERGENCE_PATH}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
