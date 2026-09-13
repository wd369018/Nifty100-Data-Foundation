"""Screener endpoint — threshold filters over the per-company feature frame."""

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.api import cached_feature_frame

router = APIRouter(prefix="/screener", tags=["screener"])

FILTER_PARAMS = {
    "min_roe": ("return_on_equity_pct", "gte"),
    "max_de": ("debt_to_equity", "lte"),
    "min_fcf": ("free_cash_flow_cr", "gte"),
    "min_rev_cagr_5yr": ("revenue_cagr_5yr", "gte"),
    "min_pat_cagr_5yr": ("pat_cagr_5yr", "gte"),
    "max_pe": ("pe_ratio", "lte"),
}


def _as_float(value, name):
    """Raise 400 when a query param is present but not numeric."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value for '{name}': not a number.",
        )


def _apply_operator(series, operator, threshold):
    if operator == "gte":
        return series >= threshold
    if operator == "lte":
        return series <= threshold
    return ~series.isna() & False


@router.get("")
def screener(
    min_roe: str | None = Query(None),
    max_de: str | None = Query(None),
    min_fcf: str | None = Query(None),
    sector: str | None = Query(None),
    min_rev_cagr_5yr: str | None = Query(None),
    min_pat_cagr_5yr: str | None = Query(None),
    max_pe: str | None = Query(None),
):
    """Rank companies passing every supplied filter (HTTP 400 on bad values)."""
    values = {
        "min_roe": _as_float(min_roe, "min_roe"),
        "max_de": _as_float(max_de, "max_de"),
        "min_fcf": _as_float(min_fcf, "min_fcf"),
        "min_rev_cagr_5yr": _as_float(min_rev_cagr_5yr, "min_rev_cagr_5yr"),
        "min_pat_cagr_5yr": _as_float(min_pat_cagr_5yr, "min_pat_cagr_5yr"),
        "max_pe": _as_float(max_pe, "max_pe"),
    }

    frame = cached_feature_frame()

    mask = pd.Series(True, index=frame.index)
    for name, (column, op) in FILTER_PARAMS.items():
        threshold = values[name]
        if threshold is None:
            continue
        mask &= _apply_operator(frame[column], op, threshold)

    if sector:
        mask &= frame["broad_sector"] == sector

    result = frame[mask].copy()
    result = result.sort_values("composite_quality_score", ascending=False)

    columns = [
        "company_id",
        "company_name",
        "broad_sector",
        "return_on_equity_pct",
        "debt_to_equity",
        "free_cash_flow_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "pe_ratio",
        "composite_quality_score",
    ]
    rows = result[columns].dropna(subset=["company_id"]).round(4)
    rows["company_name"] = rows["company_name"].str.split("\n").str[0].str.strip()

    records = [
        {
            k: (
                None
                if pd.isna(v)
                else (
                    float(v)
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                    else v
                )
            )
            for k, v in row.items()
        }
        for row in rows.to_dict(orient="records")
    ]

    return {
        "count": len(records),
        "filters": {k: v for k, v in values.items() if v is not None},
        "screened_company_ids": [r["company_id"] for r in records],
        "companies": records,
    }
