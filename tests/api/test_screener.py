"""Screener endpoint tests + dashboard-API integration (Sprint 6, Day 42)."""

import pandas as pd

from src.screener.engine import compute_composite_score, load_feature_frame


def test_screener_roe_filter(client):
    response = client.get("/api/v1/screener", params={"min_roe": "15"})
    assert response.status_code == 200
    payload = response.json()
    assert (
        payload["count"]
        == len(payload["companies"])
        == len(payload["screened_company_ids"])
    )
    assert payload["count"] > 0
    assert all(c["return_on_equity_pct"] >= 15 for c in payload["companies"])


def test_screener_max_de_filter(client):
    payload = client.get("/api/v1/screener", params={"max_de": "0.5"}).json()
    assert all(c["debt_to_equity"] <= 0.5 for c in payload["companies"])


def test_screener_sector_filter(client):
    payload = client.get("/api/v1/screener", params={"sector": "Energy"}).json()
    assert payload["count"] > 0
    assert all(c["broad_sector"] == "Energy" for c in payload["companies"])


def test_screener_combined_filters_are_intersective(client):
    base = client.get("/api/v1/screener", params={"min_roe": "15"}).json()[
        "screened_company_ids"
    ]
    with_pe = client.get(
        "/api/v1/screener", params={"min_roe": "15", "max_pe": "30"}
    ).json()["screened_company_ids"]
    assert set(with_pe) <= set(base)


def test_screener_sorted_by_composite_desc(client):
    payload = client.get("/api/v1/screener", params={"min_roe": "15"}).json()
    scores = [c["composite_quality_score"] for c in payload["companies"]]
    assert scores == sorted(scores, reverse=True)


def test_screener_invalid_number_returns_400(client):
    response = client.get("/api/v1/screener", params={"min_roe": "abc"})
    assert response.status_code == 400


def test_screener_empty_string_param_is_ignored(client):
    response = client.get("/api/v1/screener", params={"min_roe": ""})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 92


def test_screener_no_filters_returns_all(client):
    payload = client.get("/api/v1/screener").json()
    assert payload["count"] == 92


def test_integration_dashboard_vs_api_quality_preset(client):
    """Streamlit 'Quality' preset applied through the dashboard feature
    frame must produce the same company set as the API screener."""
    preset = {"roe_min": 15.0, "de_max": 1.0, "fcf_min": 0.0, "rev_cagr_min": 10.0}

    frame = compute_composite_score(load_feature_frame())
    mask = pd.Series(True, index=frame.index)
    mask &= frame["return_on_equity_pct"] >= preset["roe_min"]
    mask &= frame["debt_to_equity"] <= preset["de_max"]
    mask &= frame["free_cash_flow_cr"] >= preset["fcf_min"]
    mask &= frame["revenue_cagr_5yr"] >= preset["rev_cagr_min"]
    dashboard_ids = set(frame[mask]["company_id"])

    payload = client.get(
        "/api/v1/screener",
        params={
            "min_roe": str(preset["roe_min"]),
            "max_de": str(preset["de_max"]),
            "min_fcf": str(preset["fcf_min"]),
            "min_rev_cagr_5yr": str(preset["rev_cagr_min"]),
        },
    ).json()
    api_ids = set(payload["screened_company_ids"])

    assert dashboard_ids == api_ids
    assert api_ids  # non-trivial preset must match something
