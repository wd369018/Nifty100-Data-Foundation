"""Health endpoint tests (Sprint 6, Day 42)."""

from src.api import PRIMARY_TABLES


def test_health_returns_200(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_status_ok(client):
    payload = client.get("/api/v1/health").json()
    assert payload["status"] == "ok"


def test_health_has_version(client):
    payload = client.get("/api/v1/health").json()
    assert isinstance(payload["version"], str)
    assert payload["version"]


def test_health_uptime_non_negative(client):
    payload = client.get("/api/v1/health").json()
    assert payload["uptime_seconds"] >= 0


def test_health_reports_all_ten_tables(client):
    payload = client.get("/api/v1/health").json()
    row_counts = payload["db_row_counts"]
    assert set(PRIMARY_TABLES) == set(row_counts.keys())


def test_health_table_counts_positive(client):
    payload = client.get("/api/v1/health").json()
    for count in payload["db_row_counts"].values():
        assert count > 0


def test_health_companies_count_matches_expected(client):
    payload = client.get("/api/v1/health").json()
    assert payload["db_row_counts"]["companies"] == 92


def test_health_content_type_json(client):
    response = client.get("/api/v1/health")
    assert "application/json" in response.headers["content-type"]
