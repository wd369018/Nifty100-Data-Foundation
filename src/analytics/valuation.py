"""Valuation Module — Sprint 4, Day 26.

Computes valuation multiples and sector-relative valuation flags for
the full 92-company universe:

- FCF yield  = free_cash_flow / latest market cap x 100.
- P/E flags  = P/E vs the broad-sector median P/E (latest year):
      P/E > sector_median x 1.5  -> Caution
      P/E < sector_median x 0.7  -> Discount
      otherwise                  -> Fair

Outputs:
- output/valuation_summary.xlsx — every company with its multiples.
- output/valuation_flags.csv   — companies flagged Caution or Discount.

Run:
    python -m src.analytics.valuation
"""

import sqlite3
from pathlib import Path

import pandas as pd

from src.screener.engine import load_feature_frame

DB_PATH = Path("db/nifty100.db")
SUMMARY_PATH = Path("output/valuation_summary.xlsx")
FLAGS_PATH = Path("output/valuation_flags.csv")

CAUTION_MULTIPLE = 1.5
DISCOUNT_MULTIPLE = 0.7

OUTPUT_COLUMNS = [
    "company_id",
    "company_name",
    "sector",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "fcf_yield_pct",
    "pe_5yr_median",
    "pe_vs_sector_median_pct",
    "flag",
]


def flag_for(
    pe_ratio,
    sector_median_pe,
    caution_multiple=CAUTION_MULTIPLE,
    discount_multiple=DISCOUNT_MULTIPLE,
):
    """Classify a P/E against the sector median.

    Returns 'Caution', 'Discount', 'Fair' or None when the inputs are
    missing or the sector median is zero.
    """

    if pe_ratio is None or sector_median_pe is None:
        return None
    try:
        pe = float(pe_ratio)
        median = float(sector_median_pe)
    except (TypeError, ValueError):
        return None
    if pd.isna(pe) or pd.isna(median) or median == 0:
        return None
    if pe > median * caution_multiple:
        return "Caution"
    if pe < median * discount_multiple:
        return "Discount"
    return "Fair"


def clean_company_name(value):
    """Strip line breaks and the stray description text after a newline."""
    text = str(value).strip()
    return text.split("\n")[0].strip()


def _pct_of(numerator, denominator):
    if numerator is None or denominator is None:
        return None
    try:
        n = float(numerator)
        d = float(denominator)
    except (TypeError, ValueError):
        return None
    if pd.isna(n) or pd.isna(d) or d == 0:
        return None
    return n / d * 100.0


def build_valuation_frame(db_path=DB_PATH):
    """Compute the full valuation summary DataFrame (92 rows)."""

    conn = sqlite3.connect(db_path)
    try:
        market_cap = pd.read_sql_query(
            "SELECT company_id, year, market_cap_crore, pe_ratio, pb_ratio, "
            "ev_ebitda FROM market_cap",
            conn,
        )
    finally:
        conn.close()

    # Baseline feature frame: latest screening year per company (2024).
    frame = load_feature_frame(db_path=db_path)
    frame["company_name"] = frame["company_name"].apply(clean_company_name)

    latest_year = int(market_cap["year"].max())
    mc_latest = market_cap[market_cap["year"] == latest_year]

    pe_history = (
        market_cap.groupby("company_id")["pe_ratio"].median().rename("pe_5yr_median")
    )

    # The baseline frame already carries pe_ratio / pb_ratio from the
    # screening year inside load_feature_frame.  Drop those so the
    # merge below brings in the latest-year versions cleanly.
    drop_cols = [
        c
        for c in ["pe_ratio", "pb_ratio", "dividend_yield_pct", "market_cap_crore"]
        if c in frame.columns
    ]
    frame = frame.drop(columns=drop_cols)

    merged = frame.merge(
        mc_latest[
            ["company_id", "pe_ratio", "pb_ratio", "ev_ebitda", "market_cap_crore"]
        ],
        on="company_id",
        how="left",
    )
    merged = merged.merge(pe_history, on="company_id", how="left")

    merged["sector_median_pe"] = merged.groupby("broad_sector")["pe_ratio"].transform(
        "median"
    )

    merged["fcf_yield_pct"] = merged.apply(
        lambda r: _pct_of(r["free_cash_flow_cr"], r["market_cap_crore"]),
        axis=1,
    )
    merged["pe_vs_sector_median_pct"] = merged.apply(
        lambda r: _pct_of(r["pe_ratio"], r["sector_median_pe"]),
        axis=1,
    )
    merged["flag"] = merged.apply(
        lambda r: flag_for(r["pe_ratio"], r["sector_median_pe"]),
        axis=1,
    )

    out = pd.DataFrame(
        {
            "company_id": merged["company_id"],
            "company_name": merged["company_name"],
            "sector": merged["broad_sector"],
            "pe_ratio": merged["pe_ratio"],
            "pb_ratio": merged["pb_ratio"],
            "ev_ebitda": merged["ev_ebitda"],
            "fcf_yield_pct": merged["fcf_yield_pct"],
            "pe_5yr_median": merged["pe_5yr_median"],
            "pe_vs_sector_median_pct": merged["pe_vs_sector_median_pct"],
            "flag": merged["flag"],
        }
    )
    out = out.sort_values(
        ["pe_vs_sector_median_pct", "company_id"],
        ascending=[False, True],
        na_position="last",
    ).reset_index(drop=True)
    return out


def write_outputs(frame, summary_path=SUMMARY_PATH, flags_path=FLAGS_PATH):
    """Write valuation_summary.xlsx and valuation_flags.csv."""

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    flags_path.parent.mkdir(parents=True, exist_ok=True)

    frame[OUTPUT_COLUMNS].to_excel(summary_path, index=False)

    flagged = frame[frame["flag"].isin(["Caution", "Discount"])]
    flagged[OUTPUT_COLUMNS].to_csv(flags_path, index=False)

    return len(frame), len(flagged)


def main():
    print("=" * 60)
    print("VALUATION MODULE  (Sprint 4, Day 26)")
    print("=" * 60)

    frame = build_valuation_frame()
    total, flagged = write_outputs(frame)

    counts = frame["flag"].value_counts().to_dict()
    print(f"\n  Companies         : {total}")
    print(f"  Caution           : {counts.get('Caution', 0)}")
    print(f"  Discount          : {counts.get('Discount', 0)}")
    print(f"  Fair              : {counts.get('Fair', 0)}")
    print(f"  Missing flag      : {counts.get(None, 0)}")
    print(f"\n  Output            : {SUMMARY_PATH}")
    print(f"  Flags CSV         : {FLAGS_PATH} ({flagged} companies)")
    print("=" * 60)


if __name__ == "__main__":
    main()
