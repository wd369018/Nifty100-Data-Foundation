"""Portfolio stats endpoint — P10..P90 percentile table for the 10 core KPIs."""

import pandas as pd
from fastapi import APIRouter

from src.analytics.descriptive import CORE_KPIS, PERCENTILES, portfolio_stats

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/stats")
def portfolio_stats_endpoint():
    """Return P10 through P90, mean and std for the 10 core KPIs (all 92 companies)."""
    from src.analytics.descriptive import load_kpi_frame

    frame = load_kpi_frame()
    stats = portfolio_stats(frame, kpis=CORE_KPIS, percentiles=PERCENTILES)

    # Re-key percentiles to stable string names for JSON.
    records = []
    for _, row in stats.iterrows():
        record = {
            "kpi": row["kpi"],
            "n": int(row["n"]),
            "mean": _clean(row["mean"]),
            "std": _clean(row["std"]),
        }
        for pct in PERCENTILES:
            record[f"p{int(pct * 100)}"] = _clean(row[f"p{int(pct * 100)}"])
        records.append(record)
    return {"count": len(records), "kpis": records}


def _clean(value):
    """Convert a scalar to a Python float (JSON-safe) or None."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)
