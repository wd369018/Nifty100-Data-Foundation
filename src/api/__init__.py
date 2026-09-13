"""Nifty100 REST API package (Sprint 6)."""

import os
import sqlite3
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("NIFTY100_DB", ROOT / "db" / "nifty100.db"))
TEARSHEET_DIR = Path(
    os.environ.get("NIFTY100_TEARSHEET_DIR", ROOT / "reports" / "tearsheets")
)

# The 10 core tables reported by /health.
PRIMARY_TABLES = [
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "financial_ratios",
    "market_cap",
    "sectors",
    "peer_groups",
    "peer_percentiles",
    "documents",
]


def get_conn():
    """Open a read-only SQLite connection with row access by name."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def table_row_counts(conn=None):
    """Return {table_name: row_count} for the 10 primary tables."""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in PRIMARY_TABLES
        }
    finally:
        if own_conn:
            conn.close()


def query_all(sql, params=()):
    """Run a SELECT and return a list of dicts."""
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def query_first(sql, params=()):
    """Run a SELECT and return the first row as a dict (None if empty)."""
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


@lru_cache(maxsize=1)
def cached_feature_frame():
    """One row per company at its latest screening year, cached for the
    life of the process (the dataset is static for a running API)."""
    from src.screener.engine import compute_composite_score, load_feature_frame

    return compute_composite_score(load_feature_frame(db_path=DB_PATH))
