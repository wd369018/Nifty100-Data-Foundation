"""Day 31 cash flow intelligence builder tests (DB-backed)."""

import sqlite3

import pandas as pd
import pytest

from src.analytics.cashflow_kpis import (
    CFI_COLUMNS,
    build_cashflow_intelligence_frame,
    build_distress_alerts,
)


def _make_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sectors (company_id TEXT, broad_sector TEXT)")
    conn.execute(
        "CREATE TABLE cashflow (company_id TEXT, year TEXT, "
        "operating_activity REAL, investing_activity REAL, "
        "financing_activity REAL)"
    )
    conn.execute(
        "CREATE TABLE profitandloss (company_id TEXT, year TEXT, "
        "net_profit REAL, operating_profit REAL, sales REAL)"
    )
    conn.execute(
        "CREATE TABLE balancesheet (company_id TEXT, year TEXT, " "borrowings REAL)"
    )

    conn.execute("INSERT INTO sectors VALUES (?, ?)", ("A", "Industrials"))
    conn.execute("INSERT INTO sectors VALUES (?, ?)", ("B", "Financials"))
    conn.execute("INSERT INTO sectors VALUES (?, ?)", ("C", "Energy"))

    # Company A: clean +,-,- pattern, healthy CFO, deleveraging.
    rows = [
        ("A", "2020-03", 100.0, -20.0, -40.0),
        ("A", "2021-03", 120.0, -25.0, -35.0),
        ("A", "2022-03", 140.0, -30.0, -30.0),
        ("A", "2023-03", 160.0, -35.0, -25.0),
        ("A", "2024-03", 180.0, -40.0, -20.0),
    ]
    conn.executemany("INSERT INTO cashflow VALUES (?, ?, ?, ?, ?)", rows)
    conn.executemany(
        "INSERT INTO profitandloss VALUES (?, ?, ?, ?, ?)",
        [
            ("A", "2020-03", 100.0, 150.0, 800.0),
            ("A", "2021-03", 110.0, 160.0, 860.0),
            ("A", "2022-03", 120.0, 170.0, 920.0),
            ("A", "2023-03", 130.0, 180.0, 990.0),
            ("A", "2024-03", 140.0, 190.0, 1060.0),
        ],
    )
    conn.executemany(
        "INSERT INTO balancesheet VALUES (?, ?, ?)",
        [
            ("A", "2020-03", 500.0),
            ("A", "2021-03", 480.0),
            ("A", "2022-03", 450.0),
            ("A", "2023-03", 400.0),
            ("A", "2024-03", 350.0),
        ],
    )

    # Company B: distress (-,+,+) in the latest year.
    conn.executemany(
        "INSERT INTO cashflow VALUES (?, ?, ?, ?, ?)",
        [
            ("B", "2023-03", 50.0, -10.0, -5.0),
            ("B", "2024-03", -20.0, 5.0, 30.0),
        ],
    )
    conn.executemany(
        "INSERT INTO profitandloss VALUES (?, ?, ?, ?, ?)",
        [
            ("B", "2023-03", 40.0, 55.0, 300.0),
            ("B", "2024-03", 10.0, 20.0, 280.0),
        ],
    )
    conn.executemany(
        "INSERT INTO balancesheet VALUES (?, ?, ?)",
        [("B", "2023-03", 100.0), ("B", "2024-03", 120.0)],
    )

    # Company C: no cash flow history at all.
    conn.commit()
    conn.close()


def test_frame_shape_and_columns(tmp_path):
    db_path = tmp_path / "cfi.db"
    _make_db(db_path)

    frame = build_cashflow_intelligence_frame(db_path=db_path)

    assert list(frame.columns) == CFI_COLUMNS
    assert sorted(frame["company_id"]) == ["A", "B", "C"]


def test_company_c_without_cashflow_is_null(tmp_path):
    db_path = tmp_path / "cfi.db"
    _make_db(db_path)

    row = (
        build_cashflow_intelligence_frame(db_path=db_path)
        .set_index("company_id")
        .loc["C"]
    )

    assert pd.isna(row["cfo_quality_label"])
    assert pd.isna(row["capex_intensity_pct"])
    assert pd.isna(row["capital_allocation_label"])
    assert bool(row["distress_flag"]) is False


def test_company_a_flags_and_quality(tmp_path):
    db_path = tmp_path / "cfi.db"
    _make_db(db_path)

    frame = build_cashflow_intelligence_frame(db_path=db_path)
    a = frame.set_index("company_id").loc["A"]

    # CFO/PAT = 180/140 for the latest year -> quality well above 1.
    assert a["cfo_quality_label"] == "High Quality"
    # Capex = -40 on sales 1060 -> 3.77% -> Moderate.
    assert a["capex_label"] == "Moderate"
    assert a["capex_intensity_pct"] == pytest.approx(
        abs(-40.0) / 1060.0 * 100.0, abs=0.02
    )
    # (+,-,-) with CFO/PAT = 180/140 = 1.29 -> Shareholder Returns.
    assert a["capital_allocation_label"] == "Shareholder Returns"
    # CFF negative 5 years running and borrowings declining -> deleveraging.
    assert bool(a["deleveraging_flag"]) is True
    assert bool(a["distress_flag"]) is False


def test_company_b_distress(tmp_path):
    db_path = tmp_path / "cfi.db"
    _make_db(db_path)

    frame = build_cashflow_intelligence_frame(db_path=db_path)
    b = frame.set_index("company_id").loc["B"]
    assert bool(b["distress_flag"]) is True
    assert bool(b["deleveraging_flag"]) is False


def test_build_distress_alerts_contents(tmp_path):
    db_path = tmp_path / "cfi.db"
    _make_db(db_path)

    frame = build_cashflow_intelligence_frame(db_path=db_path)
    alerts = build_distress_alerts(frame, db_path=db_path)

    assert list(alerts["company_id"]) == ["B"]
    assert alerts.iloc[0]["cfo_operating"] == -20.0
    assert alerts.iloc[0]["cff_financing"] == 30.0
    assert alerts.iloc[0]["latest_net_profit"] == 10.0
