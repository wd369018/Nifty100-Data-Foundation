import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics.peer import (
    _percent_rank,
    compute_peer_percentiles,
    peer_percentile_for,
    persist_peer_percentiles,
)

# ------------------------------------------------------------------
# _percent_rank (SQL PERCENT_RANK semantics)
# ------------------------------------------------------------------


def test_percent_rank_linear():
    values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    pct = _percent_rank(values, ascending=True)
    # (rank - 1) / (n - 1) with ascending sort.
    assert pct.tolist() == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0])


def test_percent_rank_high_value_best():
    """Ascending percentile: the highest value gets the best (1.0)."""
    values = pd.Series([5.0, 20.0, 10.0, 15.0])
    pct = _percent_rank(values, ascending=True)
    assert pct.loc[values.index[1]] == pytest.approx(1.0)  # 20.0
    assert pct.loc[values.index[0]] == pytest.approx(0.0)  # 5.0


def test_percent_rank_ties_min_rank():
    values = pd.Series([1.0, 1.0, 2.0])
    pct = _percent_rank(values, ascending=True)
    # Ties take the minimum rank (1, 1, 3).
    assert pct.iloc[0] == pytest.approx(0.0)
    assert pct.iloc[1] == pytest.approx(0.0)
    assert pct.iloc[2] == pytest.approx(1.0)


def test_percent_rank_single_value():
    values = pd.Series([42.0])
    pct = _percent_rank(values)
    assert np.isnan(pct.iloc[0])


def test_percent_rank_nan_kept():
    values = pd.Series([1.0, np.nan, 3.0])
    pct = _percent_rank(values)
    assert np.isnan(pct.iloc[1])
    assert not np.isnan(pct.iloc[0])


# ------------------------------------------------------------------
# compute_peer_percentiles
# ------------------------------------------------------------------


def _peer_frame():
    return pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "return_on_equity_pct": [10.0, 20.0, 30.0, 40.0],
            "debt_to_equity": [2.0, 1.0, 0.5, 0.1],
            "free_cash_flow_cr": [100.0, 200.0, 300.0, 400.0],
            "year": ["2024-03", "2024-03", "2024-03", "2024-03"],
        }
    )


def _peer_mapping():
    return pd.DataFrame(
        {
            "peer_group_name": ["Perf"] * 4,
            "company_id": ["A", "B", "C", "D"],
            "is_benchmark": [False, False, False, True],
        }
    )


def test_compute_peer_percentiles_schema():
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    assert list(result.columns) == [
        "company_id",
        "peer_group_name",
        "metric",
        "value",
        "percentile_rank",
        "year",
    ]
    metrics = set(result["metric"])
    assert "roe" in metrics and "de" in metrics and "fcf" in metrics


def test_roe_percentiles_higher_is_better():
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    roe = result[result["metric"] == "roe"].set_index("company_id")
    # D has the highest ROE (40) -> best percentile (1.0).
    assert roe.loc["D", "percentile_rank"] == pytest.approx(1.0)
    assert roe.loc["A", "percentile_rank"] == pytest.approx(0.0)
    assert roe.loc["B", "percentile_rank"] == pytest.approx(1 / 3, abs=1e-4)
    assert roe.loc["C", "percentile_rank"] == pytest.approx(2 / 3, abs=1e-4)


def test_de_percentiles_inverted_lower_is_better():
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    de = result[result["metric"] == "de"].set_index("company_id")
    # D has the lowest D/E (0.1) -> best percentile after inversion.
    assert de.loc["D", "percentile_rank"] == pytest.approx(1.0)
    assert de.loc["A", "percentile_rank"] == pytest.approx(0.0)
    assert de.loc["B", "percentile_rank"] == pytest.approx(1 / 3, abs=1e-4)
    assert de.loc["C", "percentile_rank"] == pytest.approx(2 / 3, abs=1e-4)


def test_peer_percentiles_years_carried():
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    assert (result["year"] == "2024-03").all()


def test_peer_group_with_single_company_skipped():
    frame = _peer_frame().head(1)
    mapping = pd.DataFrame(
        {"peer_group_name": ["Lonely"], "company_id": ["A"], "is_benchmark": [False]}
    )
    result = compute_peer_percentiles(frame, mapping)
    assert result.empty


def test_metric_all_nan_skipped():
    frame = _peer_frame().copy()
    frame["free_cash_flow_cr"] = np.nan
    result = compute_peer_percentiles(frame, _peer_mapping())
    assert "fcf" not in set(result["metric"])


# ------------------------------------------------------------------
# peer_percentile_for + persistence
# ------------------------------------------------------------------


def _tmp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE companies (id TEXT PRIMARY KEY)
        """)
    for cid in ["A", "B", "C", "D"]:
        conn.execute("INSERT INTO companies (id) VALUES (?)", (cid,))
    conn.commit()
    conn.close()
    return db_path


def test_persist_and_query(tmp_path):
    db_path = _tmp_db(tmp_path)
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    persist_peer_percentiles(result, db_path)

    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM peer_percentiles").fetchone()[0]
    conn.close()
    assert n == len(result)


def test_peer_percentile_for_no_group_message(tmp_path):
    db_path = _tmp_db(tmp_path)
    message = peer_percentile_for("UNKNOWN_COMPANY", db_path=db_path)
    assert "No peer group assigned" in message


def test_peer_percentile_for_lists_metrics(tmp_path):
    db_path = _tmp_db(tmp_path)
    result = compute_peer_percentiles(_peer_frame(), _peer_mapping())
    persist_peer_percentiles(result, db_path)

    message = peer_percentile_for("A", db_path=db_path)
    assert "roe" in message
    assert "de" in message
    assert "fcf" in message
