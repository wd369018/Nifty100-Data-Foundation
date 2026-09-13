"""Health endpoint — DB row counts, uptime and version."""

import time

from fastapi import APIRouter

from src.api import PRIMARY_TABLES, table_row_counts

router = APIRouter(tags=["health"])

START_TIME = time.time()
APP_VERSION = "0.6.0"


@router.get("/health")
def health():
    """Return service health, DB row counts and uptime."""
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "db_row_counts": table_row_counts(),
        "tables": PRIMARY_TABLES,
    }
