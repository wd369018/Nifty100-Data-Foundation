"""Day 30 pros/cons generator tests (unit, no DB)."""

import pandas as pd

from src.nlp.pros_cons_generator import (
    evaluate_company,
    margin_confidence,
    trailing_run,
)


def _bundle(ratios=None, pl=None, bs=None, cf=None, mc=None, sector="Materials"):
    return {
        "ratios": pd.DataFrame(ratios or []),
        "pl": pd.DataFrame(pl or []),
        "bs": pd.DataFrame(bs or []),
        "cf": pd.DataFrame(cf or []),
        "mc": pd.DataFrame(mc or []),
        "sector": sector,
    }


def test_margin_confidence_threshold_baseline():
    assert margin_confidence(15.0, 15.0) == 60.0
    assert margin_confidence(10.0, 10.0, higher_is_better=False) == 60.0


def test_margin_confidence_grows_beyond_threshold():
    low = margin_confidence(16.0, 15.0)
    high = margin_confidence(30.0, 15.0)
    assert high > low > 60.0
    # Saturates at full_span_ratio multiples beyond the threshold.
    assert margin_confidence(1000.0, 15.0) == 80.0


def test_margin_confidence_inverse_rule():
    nearer = margin_confidence(8.0, 10.0, higher_is_better=False)
    farther = margin_confidence(2.0, 10.0, higher_is_better=False)
    assert farther > nearer > 60.0


def test_trailing_run_streak():
    assert trailing_run([5.0, 6.0, 7.0], lambda v: v > 4.0) == 3
    assert trailing_run([1.0, 5.0, 6.0, 7.0], lambda v: v > 4.0) == 3
    assert trailing_run([], lambda v: v > 4.0) == 0


def test_trailing_run_stops_at_none():
    assert trailing_run([None, 5.0, 6.0], lambda v: v > 4.0) == 2


def test_evaluate_company_successful_company():
    bundle = _bundle(
        ratios=[
            {
                "year": "2022-03",
                "return_on_equity_pct": 21.0,
                "free_cash_flow_cr": 50.0,
                "debt_to_equity": 0.1,
                "revenue_cagr_5yr": 18.0,
                "operating_profit_margin_pct": 26.0,
                "pat_cagr_5yr": 22.0,
                "interest_coverage": 12.0,
                "icr_label": None,
                "earnings_per_share": 10.0,
                "eps_cagr_5yr": 16.0,
                "dividend_payout_ratio_pct": 40.0,
                "capex_cr": 20.0,
            },
            {
                "year": "2023-03",
                "return_on_equity_pct": 22.0,
                "free_cash_flow_cr": 55.0,
                "debt_to_equity": 0.1,
                "revenue_cagr_5yr": 18.0,
                "operating_profit_margin_pct": 26.0,
                "pat_cagr_5yr": 22.0,
                "interest_coverage": 12.0,
                "icr_label": None,
                "earnings_per_share": 11.0,
                "eps_cagr_5yr": 16.0,
                "dividend_payout_ratio_pct": 40.0,
                "capex_cr": 20.0,
            },
            {
                "year": "2024-03",
                "return_on_equity_pct": 23.0,
                "free_cash_flow_cr": 60.0,
                "debt_to_equity": 0.1,
                "revenue_cagr_5yr": 18.0,
                "operating_profit_margin_pct": 26.0,
                "pat_cagr_5yr": 22.0,
                "interest_coverage": 12.0,
                "icr_label": None,
                "earnings_per_share": 12.0,
                "eps_cagr_5yr": 16.0,
                "dividend_payout_ratio_pct": 40.0,
                "capex_cr": 20.0,
            },
        ],
        pl=[
            {
                "year": "2024-03",
                "sales": 1000.0,
                "net_profit": 120.0,
                "operating_profit": 260.0,
                "other_income": 10.0,
                "depreciation": 40.0,
            },
        ],
        bs=[
            {
                "year": "2024-03",
                "borrowings": 100.0,
                "investments": 50.0,
                "total_assets": 2000.0,
                "equity_capital": 100.0,
                "reserves": 900.0,
            },
        ],
    )

    pros, cons = evaluate_company("XYZ", bundle)

    assert len(pros) >= 1
    assert len(cons) >= 1
    assert all(pid.startswith("pro_") for pid, _, _ in pros)
    assert all(cid.startswith("con_") for cid, _, _ in cons)
    # Pros are all genuine signals for a company this strong.
    assert not any(pid.startswith(("pro_fb", "con_fb")) for pid, _, _ in pros)
    # ROE streak of 3 -> pro_01 fires with 60% + confidence.
    assert any(pid == "pro_01" for pid, _, _ in pros)


def test_evaluate_company_fcf_streak_con():
    bundle = _bundle(
        ratios=[
            {
                "year": f"20{i:02d}-03",
                "free_cash_flow_cr": -5.0,
                "return_on_equity_pct": 5.0,
                "debt_to_equity": 1.0,
                "operating_profit_margin_pct": 10.0,
                "capex_cr": 20.0,
            }
            for i in range(20, 25)
        ],
        pl=[{"year": "2024-03", "net_profit": 30.0}],
    )
    pros, cons = evaluate_company("XYZ", bundle)
    assert any(cid == "con_02" for cid, _, _ in cons)


def test_evaluate_company_fallback_coverage():
    bundle = _bundle(
        ratios=[
            {
                "year": "2024-03",
                "return_on_equity_pct": 10.0,
                "free_cash_flow_cr": 5.0,
                "debt_to_equity": 0.05,
                "revenue_cagr_5yr": 6.0,
                "operating_profit_margin_pct": 12.0,
                "pat_cagr_5yr": 8.0,
                "interest_coverage": 8.0,
                "earnings_per_share": 5.0,
                "eps_cagr_5yr": 4.0,
                "dividend_payout_ratio_pct": 20.0,
                "capex_cr": 2.0,
            },
        ],
        pl=[
            {
                "year": "2024-03",
                "sales": 200.0,
                "net_profit": 25.0,
                "operating_profit": 30.0,
                "other_income": 0.0,
                "depreciation": 4.0,
            }
        ],
        bs=[
            {
                "year": "2024-03",
                "borrowings": 10.0,
                "investments": 0.0,
                "total_assets": 300.0,
                "equity_capital": 50.0,
                "reserves": 150.0,
            }
        ],
        cf=[{"year": "2024-03", "financing_activity": -15.0}],
    )
    pros, cons = evaluate_company("XYZ", bundle)
    assert len(pros) == 1
    assert len(cons) == 1
    assert pros[0][0] == "pro_fb_1"  # net profit positive
    # borrowings 0.05x < 0.25 -> con_fb_1 skipped; Capex does not exceed FCF;
    # financing CFF < 0; revenue CAGR defined -> con_fb_4 fires.
    assert cons[0][0] == "con_fb_4"


def test_evaluate_company_con_fb1_needs_material_debt():
    bundle = _bundle(
        ratios=[
            {
                "year": "2024-03",
                "return_on_equity_pct": 10.0,
                "free_cash_flow_cr": 5.0,
                "debt_to_equity": 0.30,
                "revenue_cagr_5yr": 6.0,
                "operating_profit_margin_pct": 12.0,
                "pat_cagr_5yr": 8.0,
                "interest_coverage": 8.0,
                "earnings_per_share": 5.0,
                "eps_cagr_5yr": 4.0,
                "dividend_payout_ratio_pct": 20.0,
                "capex_cr": 2.0,
            },
        ],
        pl=[
            {
                "year": "2024-03",
                "sales": 200.0,
                "net_profit": 25.0,
                "operating_profit": 30.0,
                "other_income": 0.0,
                "depreciation": 4.0,
            }
        ],
        bs=[
            {
                "year": "2024-03",
                "borrowings": 60.0,
                "investments": 0.0,
                "total_assets": 300.0,
                "equity_capital": 50.0,
                "reserves": 150.0,
            }
        ],
        cf=[{"year": "2024-03", "financing_activity": -15.0}],
    )
    pros, cons = evaluate_company("XYZ", bundle)
    assert len(pros) == 1
    # D/E 0.30 > 0.25 -> borrowings fallback fires with ratio text.
    assert cons[0][0] == "con_fb_1"
    assert "0.30" in cons[0][1] or "0.3" in cons[0][1]


def test_financial_sector_skips_high_denied_con():
    bundle = _bundle(
        ratios=[
            {"year": "2024-03", "debt_to_equity": 8.0},
        ],
        sector="Financials",
    )
    _, cons = evaluate_company("XYZ", bundle)
    assert not any(cid == "con_01" for cid, _, _ in cons)
