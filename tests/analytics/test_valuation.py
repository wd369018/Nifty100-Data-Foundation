import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics.valuation import (
    CAUTION_MULTIPLE,
    DISCOUNT_MULTIPLE,
    OUTPUT_COLUMNS,
    _pct_of,
    build_valuation_frame,
    clean_company_name,
    flag_for,
    write_outputs,
)

# ------------------------------------------------------------------
# flag_for
# ------------------------------------------------------------------


def test_flag_for_happy_paths():
    assert flag_for(40.0, 20.0) == "Caution"  # 40 > 20 * 1.5
    assert flag_for(10.0, 20.0) == "Discount"  # 10 < 20 * 0.7
    assert flag_for(20.0, 20.0) == "Fair"


def test_flag_for_boundaries_are_exclusive():
    # Exactly on the boundary is still Fair (strict inequalities).
    assert flag_for(20.0 * CAUTION_MULTIPLE, 20.0) == "Fair"
    assert flag_for(20.0 * DISCOUNT_MULTIPLE, 20.0) == "Fair"
    # A hair past the boundary flips the flag.
    assert flag_for(20.0 * CAUTION_MULTIPLE + 1e-6, 20.0) == "Caution"
    assert flag_for(20.0 * DISCOUNT_MULTIPLE - 1e-6, 20.0) == "Discount"


@pytest.mark.parametrize(
    "pe,median",
    [
        (None, 20.0),
        (30.0, None),
        (None, None),
        (np.nan, 20.0),
        (30.0, np.nan),
        (30.0, 0.0),
        ("not a number", 20.0),
    ],
)
def test_flag_for_missing_or_zero_inputs(pe, median):
    assert flag_for(pe, median) is None


# ------------------------------------------------------------------
# clean_company_name
# ------------------------------------------------------------------


def test_clean_company_name_strips_description_after_newline():
    assert clean_company_name(
        "Hindustan Unilever Ltd\n" "Chain of Indian private hospitals"
    ) == ("Hindustan Unilever Ltd")


def test_clean_company_name_trims_whitespace():
    assert clean_company_name("  Apollo Hospitals  \n") == "Apollo Hospitals"


# ------------------------------------------------------------------
# _pct_of
# ------------------------------------------------------------------


def test_pct_of_basic():
    assert _pct_of(50.0, 200.0) == pytest.approx(25.0)


def test_pct_of_guard_clauses():
    assert _pct_of(None, 100.0) is None
    assert _pct_of(50.0, None) is None
    assert _pct_of(50.0, 0.0) is None
    assert _pct_of(np.nan, 100.0) is None


# ------------------------------------------------------------------
# build_valuation_frame (integration against a minimal DB)
# ------------------------------------------------------------------


def _make_db(path: Path):
    conn = sqlite3.connect(path)

    conn.executescript("""
        CREATE TABLE companies (
            id TEXT PRIMARY KEY,
            company_name TEXT
        );
        CREATE TABLE sectors (
            company_id TEXT,
            broad_sector TEXT
        );
        CREATE TABLE financial_ratios (
            company_id TEXT,
            year TEXT,
            return_on_equity_pct REAL,
            free_cash_flow_cr REAL,
            debt_to_equity REAL,
            net_profit_margin_pct REAL,
            operating_profit_margin_pct REAL,
            return_on_assets_pct REAL,
            interest_coverage REAL,
            asset_turnover REAL
        );
        CREATE TABLE market_cap (
            company_id TEXT,
            year INTEGER,
            pe_ratio REAL,
            pb_ratio REAL,
            dividend_yield_pct REAL,
            market_cap_crore REAL,
            ev_ebitda REAL
        );
        CREATE TABLE profitandloss (
            company_id TEXT,
            year TEXT,
            sales REAL,
            net_profit REAL,
            operating_profit REAL,
            other_income REAL
        );
        CREATE TABLE balancesheet (
            company_id TEXT,
            year TEXT,
            equity_capital REAL,
            reserves REAL,
            borrowings REAL
        );
        CREATE TABLE cashflow (
            company_id TEXT,
            year TEXT,
            operating_activity REAL
        );
        """)

    conn.executemany(
        "INSERT INTO companies (id, company_name) VALUES (?, ?)",
        [
            ("A", "Alpha Co"),
            ("B", "Beta Ltd\nChain of private hospitals"),
            ("C", "Gamma"),
            ("D", "Delta"),
        ],
    )
    conn.executemany(
        "INSERT INTO sectors (company_id, broad_sector) VALUES (?, ?)",
        [
            ("A", "FIN"),
            ("B", "FIN"),
            ("C", "FIN"),
            ("D", "ENE"),
        ],
    )
    # Baseline (2024) financial ratios for every company.
    conn.executemany(
        "INSERT INTO financial_ratios "
        "(company_id, year, return_on_equity_pct, free_cash_flow_cr, "
        "debt_to_equity, net_profit_margin_pct, operating_profit_margin_pct, "
        "return_on_assets_pct, interest_coverage, asset_turnover) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("A", "2024-03", 20.0, 100.0, 0.5, 10.0, 15.0, 8.0, 5.0, 1.2),
            ("B", "2024-03", 15.0, 200.0, 1.0, 8.0, 12.0, 6.0, 4.0, 1.0),
            ("C", "2024-03", 18.0, 300.0, 0.8, 9.0, 13.0, 7.0, 6.0, 1.1),
            ("D", "2024-03", 12.0, 100.0, 0.6, 7.0, 11.0, 5.0, 3.0, 0.9),
        ],
    )
    # P&L / balance sheet / cash flow rows for the baseline year.
    conn.executemany(
        "INSERT INTO profitandloss "
        "(company_id, year, sales, net_profit, operating_profit, other_income) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("A", "2024-03", 10000.0, 1000.0, 1500.0, 0.0),
            ("B", "2024-03", 8000.0, 700.0, 1000.0, 0.0),
            ("C", "2024-03", 9000.0, 800.0, 1200.0, 0.0),
            ("D", "2024-03", 5000.0, 400.0, 600.0, 0.0),
        ],
    )
    conn.executemany(
        "INSERT INTO balancesheet "
        "(company_id, year, equity_capital, reserves, borrowings) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("A", "2024-03", 1000.0, 2000.0, 1000.0),
            ("B", "2024-03", 800.0, 1500.0, 800.0),
            ("C", "2024-03", 900.0, 1800.0, 900.0),
            ("D", "2024-03", 600.0, 1000.0, 500.0),
        ],
    )
    conn.executemany(
        "INSERT INTO cashflow (company_id, year, operating_activity) "
        "VALUES (?, ?, ?)",
        [
            ("A", "2024-03", 1100.0),
            ("B", "2024-03", 800.0),
            ("C", "2024-03", 900.0),
            ("D", "2024-03", 450.0),
        ],
    )
    # Market cap history 2019-2024.
    mc = {
        "A": {"pe": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0], "mcap": 4000.0},
        "B": {"pe": [5.0, 5.0, 5.0, 5.0, 5.0, 10.0], "mcap": 2000.0},
        "C": {"pe": [20.0] * 6, "mcap": 6000.0},
        "D": {"pe": [15.0] * 6, "mcap": 1500.0},
    }
    rows = []
    for cid, data in mc.items():
        for i, pe in enumerate(data["pe"]):
            rows.append((cid, 2019 + i, pe, pe / 2.0, 1.0, data["mcap"], pe * 1.4))
    conn.executemany(
        "INSERT INTO market_cap "
        "(company_id, year, pe_ratio, pb_ratio, dividend_yield_pct, "
        "market_cap_crore, ev_ebitda) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )

    conn.commit()
    conn.close()


def test_build_valuation_frame_flags(tmp_path):
    db_path = tmp_path / "val.db"
    _make_db(db_path)

    out = build_valuation_frame(db_path=db_path)

    assert list(out.columns) == OUTPUT_COLUMNS
    assert sorted(out["company_id"]) == ["A", "B", "C", "D"]

    flags = out.set_index("company_id")["flag"]
    # FIN sector median P/E = median(40, 10, 20) = 20.
    assert flags["A"] == "Caution"  # 40 > 30
    assert flags["B"] == "Discount"  # 10 < 14
    assert flags["C"] == "Fair"
    # ENE sector median = 15 (single member).
    assert flags["D"] == "Fair"

    assert out.set_index("company_id").loc["B", "company_name"] == "Beta Ltd"
    for cid in ["A", "B", "C", "D"]:
        assert out.set_index("company_id").loc[cid, "sector"] in {"FIN", "ENE"}


def test_build_valuation_frame_fcf_yield(tmp_path):
    db_path = tmp_path / "val.db"
    _make_db(db_path)

    out = build_valuation_frame(db_path=db_path)
    yields = out.set_index("company_id")["fcf_yield_pct"]
    assert yields["A"] == pytest.approx(100.0 / 4000.0 * 100.0)
    assert yields["B"] == pytest.approx(200.0 / 2000.0 * 100.0)
    assert yields["C"] == pytest.approx(300.0 / 6000.0 * 100.0)
    assert yields["D"] == pytest.approx(100.0 / 1500.0 * 100.0)


def test_build_valuation_frame_pe_5yr_median(tmp_path):
    db_path = tmp_path / "val.db"
    _make_db(db_path)

    out = build_valuation_frame(db_path=db_path)
    pe_medians = out.set_index("company_id")["pe_5yr_median"]
    assert pe_medians["A"] == pytest.approx((30.0 + 40.0) / 2.0)
    assert pe_medians["B"] == pytest.approx(5.0)
    assert pe_medians["C"] == pytest.approx(20.0)
    assert pe_medians["D"] == pytest.approx(15.0)


def test_build_valuation_frame_vs_sector_median_pct(tmp_path):
    db_path = tmp_path / "val.db"
    _make_db(db_path)

    out = build_valuation_frame(db_path=db_path)
    vs = out.set_index("company_id")["pe_vs_sector_median_pct"]
    assert vs["A"] == pytest.approx(60.0 / 20.0 * 100.0)
    assert vs["B"] == pytest.approx(10.0 / 20.0 * 100.0)
    assert vs["C"] == pytest.approx(20.0 / 20.0 * 100.0)
    assert vs["D"] == pytest.approx(15.0 / 15.0 * 100.0)


def test_write_outputs(tmp_path):
    db_path = tmp_path / "val.db"
    _make_db(db_path)
    frame = build_valuation_frame(db_path=db_path)

    summary = tmp_path / "summary.xlsx"
    flags = tmp_path / "flags.csv"
    total, flagged = write_outputs(frame, summary_path=summary, flags_path=flags)

    assert total == 4
    # A (Caution) and B (Discount) only.
    assert flagged == 2

    written = pd.read_excel(summary)
    assert list(written.columns) == OUTPUT_COLUMNS
    assert len(written) == 4

    flag_csv = pd.read_csv(flags)
    assert set(flag_csv["flag"]) == {"Caution", "Discount"}
    assert len(flag_csv) == 2
