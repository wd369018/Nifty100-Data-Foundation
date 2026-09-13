"""Peer endpoints — group members with percentile ranks and radar data."""

import pandas as pd
from fastapi import APIRouter, HTTPException

from src.analytics.peer import RADAR_KEYS, RADAR_LABELS
from src.api import query_all
from src.screener.engine import compute_composite_score, load_feature_frame

router = APIRouter(tags=["peers"])


def _known_groups():
    return {
        r["peer_group_name"]
        for r in query_all("SELECT DISTINCT peer_group_name FROM peer_groups")
    }


@router.get("/peers/{group_name}")
def peers_in_group(group_name: str):
    """Return all companies in a peer group with percentile ranks (404 if unknown)."""
    groups = _known_groups()
    if group_name not in groups:
        raise HTTPException(status_code=404, detail=f"Unknown peer group: {group_name}")

    members = query_all(
        "SELECT g.company_id, g.is_benchmark, c.company_name, s.broad_sector "
        "FROM peer_groups g "
        "JOIN companies c ON c.id = g.company_id "
        "LEFT JOIN sectors s ON s.company_id = g.company_id "
        "WHERE g.peer_group_name = ? ORDER BY g.company_id",
        [group_name],
    )
    percentiles = query_all(
        "SELECT company_id, metric, percentile_rank, value FROM peer_percentiles "
        "WHERE peer_group_name = ?",
        [group_name],
    )
    pct_map = {}
    for row in percentiles:
        pct_map.setdefault(row["company_id"], {})[row["metric"]] = {
            "percentile_rank": row["percentile_rank"],
            "value": row["value"],
        }

    companies = []
    for m in members:
        metric_rows = []
        for metric, data in sorted(pct_map.get(m["company_id"], {}).items()):
            metric_rows.append(
                {
                    "metric": metric,
                    "value": data["value"],
                    "percentile_rank": data["percentile_rank"],
                }
            )
        companies.append(
            {
                "company_id": m["company_id"],
                "company_name": (m["company_name"] or "").split("\n")[0].strip(),
                "broad_sector": m["broad_sector"],
                "is_benchmark": bool(m["is_benchmark"]),
                "metrics": metric_rows,
            }
        )

    return {
        "peer_group_name": group_name,
        "count": len(companies),
        "companies": companies,
    }


@router.get("/companies/{ticker}/peers/compare")
def peers_compare(ticker: str):
    """Radar data — 8 axis values for the company + group average + benchmark."""
    from src.api.routers.companies import _require_ticker

    company_id = _require_ticker(ticker)

    group_row = query_all(
        "SELECT peer_group_name FROM peer_groups WHERE company_id = ?", [company_id]
    )
    if not group_row:
        raise HTTPException(status_code=404, detail=f"No peer group for {ticker}")
    group_name = group_row[0]["peer_group_name"]

    members = query_all(
        "SELECT company_id FROM peer_groups WHERE peer_group_name = ?", [group_name]
    )
    ids = [m["company_id"] for m in members]

    frame = compute_composite_score(load_feature_frame())
    group_frame = frame[frame["company_id"].isin(ids)].copy()

    # Benchmark = the flagged company in the group, else group median company.
    benchmark = query_all(
        "SELECT company_id FROM peer_groups "
        "WHERE peer_group_name = ? AND is_benchmark = 1 "
        "ORDER BY company_id LIMIT 1",
        [group_name],
    )
    benchmark_id = benchmark[0]["company_id"] if benchmark else ids[0]

    def _vals(cid):
        row = group_frame[group_frame["company_id"] == cid]
        if row.empty:
            return {key: None for key in RADAR_KEYS}
        return {
            key: (None if pd.isna(row.iloc[0][key]) else float(row.iloc[0][key]))
            for key in RADAR_KEYS
        }

    avg_val = {
        key: float(group_frame[key].mean()) if group_frame[key].notna().any() else None
        for key in RADAR_KEYS
    }

    return {
        "company_id": company_id,
        "peer_group_name": group_name,
        "labels": list(RADAR_LABELS),
        "company_values": _vals(company_id),
        "peer_group_average": avg_val,
        "benchmark_company_id": benchmark_id,
        "benchmark_values": _vals(benchmark_id),
    }
