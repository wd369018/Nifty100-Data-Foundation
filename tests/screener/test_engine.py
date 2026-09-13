import numpy as np
import pandas as pd
import pytest

from src.screener.engine import (
    _evaluate,
    _resolve_filter,
    _scale_with_bounds,
    _winsorize_bounds,
    apply_filters,
    composite_from_scores,
    compute_component_scores,
    compute_composite_score,
    load_config,
    load_feature_frame,
    run_preset,
)


def _minimal_config():
    return {
        "metrics": {
            "roe": {"column": "return_on_equity_pct"},
            "de": {"column": "debt_to_equity", "skip_financials": True},
            "icr": {"column": "interest_coverage", "debt_free_passes": True},
            "fcf": {"column": "free_cash_flow_cr"},
        },
        "presets": {},
    }


def _minimal_frame():
    return pd.DataFrame(
        {
            "company_id": ["A", "B", "C", "D"],
            "return_on_equity_pct": [20.0, 10.0, 30.0, 25.0],
            "debt_to_equity": [0.5, 1.5, None, 0.8],
            "interest_coverage": [5.0, 2.0, None, 8.0],
            "icr_label": ["Good", "Poor", "Debt Free", "Excellent"],
            "free_cash_flow_cr": [100.0, -50.0, 200.0, 150.0],
            "broad_sector": ["Financials", "Energy", "Financials", "Energy"],
        }
    )


# ------------------------------------------------------------------
# _evaluate
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,op,threshold,expected",
    [
        (10.0, ">", 5.0, True),
        (10.0, ">", 10.0, False),
        (10.0, ">=", 10.0, True),
        (10.0, "<", 11.0, True),
        (10.0, "<=", 10.0, True),
        (10.0, "==", 10.0, True),
        (10.0, "==", 10.0000000005, True),
        (10.0, "!=", 11.0, True),
        (10.0, ">", "abc", False),
        (None, ">", 5.0, False),
        (np.nan, ">", 5.0, False),
    ],
)
def test_evaluate_numeric(value, op, threshold, expected):
    assert _evaluate(value, op, threshold) is expected


def test_evaluate_python_bool():
    assert _evaluate(True, "==", True)
    assert not _evaluate(True, "==", False)
    assert _evaluate(False, "!=", True)


def test_evaluate_numpy_bool():
    """numpy.bool_ / numpy.bool scalars (pandas 3.0) must compare correctly."""
    assert _evaluate(np.bool_(True), "==", True)
    assert not _evaluate(np.bool_(True), "==", False)
    assert not _evaluate(np.bool_(True), ">", True)


def test_evaluate_missing_fails():
    assert not _evaluate(None, ">", 5)


# ------------------------------------------------------------------
# filter resolution / apply_filters
# ------------------------------------------------------------------


def test_resolve_filter_defaults():
    config = _minimal_config()
    spec = {"metric": "roe", "operator": ">", "value": 15.0}
    column, op, value, skip_fin, debt_free = _resolve_filter(config, spec)
    assert (column, op, value) == ("return_on_equity_pct", ">", 15.0)
    assert skip_fin is False
    assert debt_free is False


def test_resolve_filter_flags():
    config = _minimal_config()
    de_spec = {"metric": "de", "operator": "<", "value": 1.0}
    *_, skip_fin, _ = _resolve_filter(config, de_spec)
    assert skip_fin is True

    icr_spec = {"metric": "icr", "operator": ">", "value": 3.0}
    *_, skip_fin, debt_free = _resolve_filter(config, icr_spec)
    assert skip_fin is False
    assert debt_free is True


def test_apply_filters_basic():
    config = _minimal_config()
    specs = [{"metric": "roe", "operator": ">", "value": 15.0}]
    result = apply_filters(_minimal_frame(), config, specs)
    assert set(result["company_id"]) == {"A", "C", "D"}


def test_apply_filters_skips_financials_for_de_max():
    """D/E < X must not fail Financials companies."""
    config = _minimal_config()
    specs = [{"metric": "de", "operator": "<", "value": 1.0}]
    result = apply_filters(_minimal_frame(), config, specs)
    # A (D/E 0.5) passes; C is Financials so D/E ignored -> passes;
    # B (1.5) and D (0.8, not Financials) -> B fails, D passes.
    assert set(result["company_id"]) == {"A", "C", "D"}


def test_apply_filters_de_equality_still_applies_to_financials():
    """An exact-zero D/E test still applies to the Financials sector."""
    config = _minimal_config()
    specs = [{"metric": "de", "operator": "==", "value": 0.5}]
    result = apply_filters(_minimal_frame(), config, specs)
    # A: 0.5 == 0.5 passes. C: Financials but "==" so D/E None fails.
    assert set(result["company_id"]) == {"A"}


def test_apply_filters_debt_free_passes_icr():
    """'Debt Free' companies pass any ICR minimum."""
    config = _minimal_config()
    specs = [{"metric": "icr", "operator": ">", "value": 3.0}]
    result = apply_filters(_minimal_frame(), config, specs)
    # A (5.0), C (Debt Free, None), D (8.0) pass; B (2.0) fails.
    assert set(result["company_id"]) == {"A", "C", "D"}


def test_apply_filters_unknown_metric_fails_all():
    config = _minimal_config()
    specs = [{"metric": "not_a_metric", "operator": ">", "value": 0.0}]
    result = apply_filters(_minimal_frame(), config, specs)
    assert result.empty


# ------------------------------------------------------------------
# Composite score
# ------------------------------------------------------------------


def test_winsorize_bounds():
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, None])
    p_low, p_high = _winsorize_bounds(series)
    assert p_low is not None and p_high is not None
    assert p_low < p_high
    assert 0.9 < p_low < 2.1
    assert 3.9 < p_high < 5.1


def test_scale_with_bounds():
    series = pd.Series([0.0, 40.0, 60.0, 100.0])
    scaled = _scale_with_bounds(series, 0.0, 100.0)
    assert scaled.tolist() == pytest.approx([0.0, 40.0, 60.0, 100.0])


def test_scale_with_bounds_degenerate():
    series = pd.Series([5.0, 5.0, 5.0])
    scaled = _scale_with_bounds(series, 5.0, 5.0)
    assert scaled.isna().all()


def test_component_scores_range():
    frame = _minimal_frame()
    scores = compute_component_scores(frame)
    for col in scores.columns:
        present = scores[col].dropna()
        if not present.empty:
            assert present.between(0, 100).all()


def test_de_score_inverted():
    frame = _minimal_frame()
    scores = compute_component_scores(frame)
    # A has D/E 0.5, B has D/E 1.5 -> A must score higher on de_score.
    assert scores.loc[0, "de_score"] > scores.loc[1, "de_score"]


def test_composite_from_scores_weighted_mean():
    scores = pd.DataFrame(
        {
            "roe_score": [100.0],
            "roce_score": [100.0],
            "npm_score": [100.0],
            "fcf_cagr_score": [100.0],
            "cfo_pat_score": [100.0],
            "fcf_pos_score": [100.0],
            "rev_cagr_score": [100.0],
            "pat_cagr_score": [100.0],
            "de_score": [100.0],
            "icr_score": [100.0],
        }
    )
    composite = composite_from_scores(scores)
    assert composite.iloc[0] == pytest.approx(100.0)


def test_composite_from_scores_missing_component():
    scores = pd.DataFrame(
        {
            "roe_score": [100.0],
            "roce_score": [100.0],
            "npm_score": [100.0],
            "fcf_cagr_score": [100.0],
            "cfo_pat_score": [100.0],
            "fcf_pos_score": [100.0],
            "rev_cagr_score": [100.0],
            "pat_cagr_score": [100.0],
            "de_score": [100.0],
            "icr_score": [None],
        }
    )
    composite = composite_from_scores(scores)
    # ICR weight is 5 of 100; missing -> reweighted mean still 100.
    assert composite.iloc[0] == pytest.approx(100.0)


def test_compute_composite_score_adds_columns():
    frame = _minimal_frame()
    comp = compute_composite_score(frame)
    assert "composite_quality_score" in comp.columns
    assert "composite_quality_score_sector" in comp.columns
    assert comp["composite_quality_score"].notna().sum() > 0


def test_composite_score_between_0_and_100():
    frame = compute_composite_score(load_feature_frame())
    score = frame["composite_quality_score"]
    present = score.dropna()
    assert present.between(0, 100).all()


# ------------------------------------------------------------------
# Presets against the real database
# ------------------------------------------------------------------


def test_all_presets_return_5_to_50():
    config = load_config()
    frame = load_feature_frame()
    frame = compute_composite_score(frame)

    for key in config["presets"]:
        result = run_preset(frame, config, key)
        assert 5 <= len(result["frame"]) <= 50, f"{key}: {len(result['frame'])}"


def test_presets_respect_their_own_thresholds():
    config = load_config()
    frame = compute_composite_score(load_feature_frame())

    qc = run_preset(frame, config, "quality_compounder")["frame"]
    assert (qc["return_on_equity_pct"] > 15).all()
    assert (qc["free_cash_flow_cr"] > 0).all()
    assert (qc["revenue_cagr_5yr"] > 10).all()
    # D/E capacity filter skips the Financials sector by design, so only
    # non-financial companies are bound by the D/E < 1 threshold.
    non_financial = qc[qc["broad_sector"] != "Financials"]
    assert (non_financial["debt_to_equity"] < 1).all()


def test_quality_compounder_sorted_by_composite():
    config = load_config()
    frame = compute_composite_score(load_feature_frame())
    qc = run_preset(frame, config, "quality_compounder")["frame"]
    scores = qc["composite_quality_score"].tolist()
    assert scores == sorted(scores, reverse=True)
