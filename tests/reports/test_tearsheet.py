"""Day 33/34 tearsheet generator tests."""

import pandas as pd
import pytest

from src.reports.tearsheet import (
    build_tearsheet_pdf,
    chart_balance_sheet,
    chart_cashflow_waterfall,
    chart_revenue_profit,
    chart_roe_roce,
    compute_kpis,
    generate_one,
)


def _company():
    pl = pd.DataFrame(
        [
            {
                "year": "2022-03",
                "sales": 800.0,
                "net_profit": 100.0,
                "operating_profit": 220.0,
                "other_income": 8.0,
                "depreciation": 40.0,
                "interest": 10.0,
            },
            {
                "year": "2023-03",
                "sales": 900.0,
                "net_profit": 120.0,
                "operating_profit": 260.0,
                "other_income": 9.0,
                "depreciation": 45.0,
                "interest": 9.0,
            },
            {
                "year": "2024-03",
                "sales": 1000.0,
                "net_profit": 150.0,
                "operating_profit": 300.0,
                "other_income": 10.0,
                "depreciation": 50.0,
                "interest": 8.0,
            },
        ]
    )
    bs = pd.DataFrame(
        [
            {
                "year": "2022-03",
                "equity_capital": 100.0,
                "reserves": 600.0,
                "borrowings": 250.0,
                "investments": 60.0,
                "total_assets": 1200.0,
            },
            {
                "year": "2023-03",
                "equity_capital": 100.0,
                "reserves": 750.0,
                "borrowings": 230.0,
                "investments": 70.0,
                "total_assets": 1350.0,
            },
            {
                "year": "2024-03",
                "equity_capital": 100.0,
                "reserves": 900.0,
                "borrowings": 200.0,
                "investments": 80.0,
                "total_assets": 1500.0,
            },
        ]
    )
    cf = pd.DataFrame(
        [
            {
                "year": "2024-03",
                "operating_activity": 220.0,
                "investing_activity": -80.0,
                "financing_activity": -60.0,
            },
        ]
    )
    return {
        "company_id": "TEST",
        "company_name": "Test Corp Ltd",
        "sector": "Materials",
        "pl": pl,
        "bs": bs,
        "cf": cf,
    }


def test_compute_kpis():
    kpis = compute_kpis(_company())
    assert kpis["revenue"] == 1000.0
    assert kpis["net_profit"] == 150.0
    assert kpis["opm"] == pytest.approx(30.0)
    assert kpis["roe"] == pytest.approx(15.0)  # 150/(100+900)
    assert kpis["roce"] == pytest.approx(30.0)  # 360/(1000+200)
    assert kpis["de"] == pytest.approx(0.2)
    assert kpis["year"] == "2024-03"


def test_all_charts_build():
    company = _company()
    assert chart_revenue_profit(company) is not None
    assert chart_roe_roce(company) is not None
    assert chart_balance_sheet(company) is not None
    assert chart_cashflow_waterfall(company) is not None


def test_build_tearsheet_pdf_two_pages():
    pdf = build_tearsheet_pdf(
        _company(), pros=["Solid ROE"], cons=[], pattern="Reinvestor"
    )
    assert pdf is not None
    assert pdf.startswith(b"%PDF")


def test_build_tearsheet_pdf_none_without_cashflow():
    company = _company()
    company["cf"] = pd.DataFrame()  # no cash flow -> no waterfall
    pdf = build_tearsheet_pdf(company, pros=[], cons=[])
    assert pdf is None


def test_generate_one_writes_file(tmp_path):
    path, size, reason = generate_one("TCS", out_dir=tmp_path)
    assert reason is None
    assert path is not None
    assert path.exists()
    # Exit criterion: every tearsheet >= 30 KB.
    assert size >= 30_000


def test_generate_one_skips_pnb(tmp_path):
    path, size, reason = generate_one("PNB", out_dir=tmp_path)
    assert path is None
    assert "years" in (reason or "")


def test_generate_one_skips_atgl(tmp_path):
    path, _, reason = generate_one("ATGL", out_dir=tmp_path)
    assert path is None
    assert reason is not None
