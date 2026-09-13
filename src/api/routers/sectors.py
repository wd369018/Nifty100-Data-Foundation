"""Sector endpoints — aggregate sector stats and per-sector company lists."""

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api import cached_feature_frame, query_all

router = APIRouter(prefix="/sectors", tags=["sectors"])


def _clean_records(records):
    """Replace NaN values with None so JSON serialisation never fails."""
    cleaned = []
    for row in records:
        item = {}
        for k, v in row.items():
            if isinstance(v, (float, int, np.floating)) and pd.isna(v):
                item[k] = None
            elif isinstance(v, np.generic):
                item[k] = v.item()
            else:
                item[k] = v
        cleaned.append(item)
    return cleaned


@router.get("")
def list_sectors():
    """Return every sector with company_count and median ROE/PE/D/E."""
    frame = cached_feature_frame()
    agg = (
        frame.groupby("broad_sector")
        .agg(
            company_count=("company_id", "count"),
            median_roe=("return_on_equity_pct", "median"),
            median_pe=("pe_ratio", "median"),
            median_de=("debt_to_equity", "median"),
        )
        .round(4)
        .reset_index()
        .rename(columns={"broad_sector": "sector"})
        .sort_values("sector")
    )
    sectors = _clean_records(agg.to_dict(orient="records"))

    # Market-cap category split per sector.
    cat_rows = query_all(
        "SELECT broad_sector, market_cap_category, COUNT(*) AS n "
        "FROM sectors GROUP BY broad_sector, market_cap_category "
        "ORDER BY broad_sector"
    )
    cats = {}
    for row in cat_rows:
        cats.setdefault(row["broad_sector"], {})[row["market_cap_category"]] = row["n"]
    for s in sectors:
        s["market_cap_categories"] = cats.get(s["sector"], {})

    return {"count": len(sectors), "sectors": sectors}


@router.get("/{sector}/companies")
def sector_companies(sector: str):
    """Return all companies in a sector with latest-year KPIs (404 if unknown)."""
    known = query_all("SELECT DISTINCT broad_sector FROM sectors")
    known_names = {r["broad_sector"] for r in known}
    if sector not in known_names:
        raise HTTPException(status_code=404, detail=f"Unknown sector: {sector}")

    frame = cached_feature_frame()
    frame = frame[frame["broad_sector"] == sector].copy()
    frame["company_name"] = frame["company_name"].str.split("\n").str[0].str.strip()

    columns = [
        "company_id",
        "company_name",
        "broad_sector",
        "year",
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "composite_quality_score",
    ]
    rows = _clean_records(frame[columns].round(4).to_dict(orient="records"))
    return {"sector": sector, "count": len(rows), "companies": rows}
