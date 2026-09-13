"""Company endpoints tests (Sprint 6, Day 42)."""


def test_companies_list_returns_all(client):
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 92
    assert len(payload["companies"]) == 92


def test_companies_list_has_required_fields(client):
    payload = client.get("/api/v1/companies").json()
    row = payload["companies"][0]
    for key in ("id", "company_name", "broad_sector", "market_cap_category"):
        assert key in row


def test_companies_search_filter(client):
    payload = client.get("/api/v1/companies", params={"search": "TCS"}).json()
    assert payload["count"] >= 1
    assert all(
        "TCS" in c["id"] or "TCS" in c["company_name"] for c in payload["companies"]
    )


def test_companies_sector_filter(client):
    payload = client.get(
        "/api/v1/companies", params={"sector": "Information Technology"}
    ).json()
    assert payload["count"] >= 1
    assert all(
        c["broad_sector"] == "Information Technology" for c in payload["companies"]
    )


def test_company_profile_valid_ticker(client):
    response = client.get("/api/v1/companies/TCS")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["id"] == "TCS"
    assert body["company"]["company_name"]
    assert body["year"] is not None


def test_company_profile_unknown_ticker_404(client):
    response = client.get("/api/v1/companies/INVALID_TICKER_XYZ")
    assert response.status_code == 404


def test_company_pl_history(client):
    response = client.get("/api/v1/companies/TCS/pl")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 5
    assert rows[0]["company_id"] == "TCS"
    assert "sales" in rows[0]


def test_company_bs_history(client):
    response = client.get("/api/v1/companies/TCS/bs")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 5
    assert "total_assets" in rows[0]


def test_company_cashflow_history(client):
    response = client.get("/api/v1/companies/TCS/cashflow")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 5
    assert "operating_activity" in rows[0]


def test_company_ratios_year_filter(client):
    response = client.get("/api/v1/companies/TCS/ratios", params={"year": "2024"})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert all(r["year"].startswith("2024") for r in rows)


def test_company_tearsheet_returns_pdf(client):
    response = client.get("/api/v1/companies/TCS/tearsheet")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert len(response.content) > 30_000


def test_company_tearsheet_missing_404(client):
    response = client.get("/api/v1/companies/INVALID_TICKER_XYZ/tearsheet")
    assert response.status_code == 404
