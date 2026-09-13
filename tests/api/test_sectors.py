"""Sector endpoints tests (Sprint 6, Day 42).

The DB holds 10 distinct broad_sector values (documented deviation from
the 11-sector spec assumption) so assertions follow the data.
"""

import sqlite3


def _distinct_sector_count():
    conn = sqlite3.connect("db/nifty100.db")
    try:
        return conn.execute(
            "SELECT COUNT(DISTINCT broad_sector) FROM sectors"
        ).fetchone()[0]
    finally:
        conn.close()


def test_sectors_returns_all_sectors(client):
    response = client.get("/api/v1/sectors")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == _distinct_sector_count() == len(payload["sectors"])


def test_sectors_have_kpi_summaries(client):
    payload = client.get("/api/v1/sectors").json()
    for sector in payload["sectors"]:
        assert "sector" in sector
        assert "company_count" in sector
        assert "median_roe" in sector


def test_sector_companies_filters_by_sector(client):
    response = client.get("/api/v1/sectors/Information Technology/companies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] > 0
    assert all(
        c["broad_sector"] == "Information Technology" for c in payload["companies"]
    )


def test_sector_companies_unknown_sector_404(client):
    response = client.get("/api/v1/sectors/NO_SUCH_SECTOR/companies")
    assert response.status_code == 404


def test_sectors_list_matches_db_values(client):
    conn = sqlite3.connect("db/nifty100.db")
    try:
        db_values = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT broad_sector FROM sectors"
            ).fetchall()
        }
    finally:
        conn.close()
    payload = client.get("/api/v1/sectors").json()
    api_values = {s["sector"] for s in payload["sectors"]}
    assert api_values == db_values
