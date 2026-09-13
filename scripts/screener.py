"""
Nifty100 Fast-Growth Screener (Sprint 2, Day 14).

Identifies high-quality compounders using the latest available
financial year per company:

    Return on Equity (ROE) > 15%
    Debt-to-Equity (D/E)   < 1

Prints the screener output and writes output/screener_result.csv.

Run after the ratio engine:
    python -m src.analytics.engine
    python scripts/screener.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Allow running as `python scripts/screener.py` directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analytics.engine import DB_PATH

OUTPUT = Path("output/screener_result.csv")


def run_screener(conn):
    """
    Return the screener DataFrame using the latest year with ROE data.

    Uses the latest fiscal year that has a computed ROE for each
    company (P&L coverage lags the balance sheet for some companies).
    """

    query = """
    WITH ranked AS (
        SELECT
            fr.company_id,
            fr.year,
            fr.return_on_equity_pct,
            fr.debt_to_equity,
            fr.net_profit_margin_pct,
            fr.composite_quality_score,
            fr.revenue_cagr_5yr,
            s.broad_sector,
            s.sub_sector,
            c.company_name,
            ROW_NUMBER() OVER (
                PARTITION BY fr.company_id ORDER BY fr.year DESC
            ) AS rn
        FROM financial_ratios fr
        JOIN sectors s ON s.company_id = fr.company_id
        JOIN companies c ON c.id = fr.company_id
        WHERE fr.return_on_equity_pct IS NOT NULL
    )
    SELECT company_id, year, company_name, broad_sector, sub_sector,
           return_on_equity_pct, debt_to_equity, net_profit_margin_pct,
           revenue_cagr_5yr, composite_quality_score
    FROM ranked
    WHERE rn = 1
      AND return_on_equity_pct > 15
      AND debt_to_equity IS NOT NULL
      AND debt_to_equity < 1
    ORDER BY return_on_equity_pct DESC
    """

    return pd.read_sql_query(query, conn)


def main():
    conn = sqlite3.connect(DB_PATH)

    result = run_screener(conn)
    print("=" * 60)
    print("NIFTY100 SCREENER: ROE > 15% AND D/E < 1")
    print("=" * 60)
    print(f"\nCompanies found: {len(result)}")

    if not result.empty:
        print("\n" + result.to_string(index=False))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)
    print(f"\nSaved: {OUTPUT}")

    conn.close()


if __name__ == "__main__":
    main()
