"""Tests for the Trellis forecast pipeline.

Run from the repository root:
    pip install pandas pytest joblib xgboost
    cd model
    PYTHONPATH=. pytest tests/ -v
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_predictor_table_exists():
    p = REPO_ROOT / "data" / "predictors" / "trellis_ward_month_predictors.csv"
    assert p.exists(), f"predictor table not found at {p}"


def test_predictor_table_has_expected_shape():
    p = REPO_ROOT / "data" / "predictors" / "trellis_ward_month_predictors.csv"
    with open(p) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    # 51 wards × 136 months expected after multi-year retrain
    assert len(rows) == 6936, f"expected 6936 rows, got {len(rows)}"
    # Expected key columns
    expected = {
        "lganame",
        "wardname",
        "year",
        "month",
        "no2_umol_m2",
        "rainfall_mm",
        "t2m_mean",
        "pop_under5",
        "fac_phc",
        "flare_total_bcm_13yr",
    }
    missing = expected - set(reader.fieldnames or rows[0].keys())
    assert not missing, f"missing columns: {missing}"


def test_forecast_json_has_51_wards():
    p = REPO_ROOT / "mvp" / "forecast_may_2026.json"
    fc = json.loads(p.read_text())
    assert len(fc) == 51


def test_forecast_json_schema():
    p = REPO_ROOT / "mvp" / "forecast_may_2026.json"
    fc = json.loads(p.read_text())
    required = {"lganame", "wardname", "no2_forecast_umol_m2", "tier", "forecast_year", "forecast_month"}
    for row in fc:
        missing = required - set(row.keys())
        assert not missing, f"row {row.get('wardname')}: missing {missing}"
        assert row["tier"] in {"likely", "possible", "watch"}
        if row["no2_forecast_umol_m2"] is not None:
            # Sanity: NO2 forecast must be a positive μmol/m² value
            assert 0 < row["no2_forecast_umol_m2"] < 200


def test_forecast_lga_set_matches_pilot():
    p = REPO_ROOT / "mvp" / "forecast_may_2026.json"
    fc = json.loads(p.read_text())
    lgas = {f["lganame"] for f in fc}
    expected = {"Warri South", "Warri South-West", "Burutu", "Bomadi", "Patani"}
    assert lgas == expected, f"unexpected LGAs: {lgas - expected}, missing: {expected - lgas}"


def test_skill_report_lifts_above_persistence():
    """Headline claim: model beats persistence on all three targets."""
    p = REPO_ROOT / "model" / "skill_report_multiyear.json"
    if not p.exists():
        pytest.skip("multi-year skill report not present (re-run train_model.py)")
    skill = json.loads(p.read_text())
    for target in ("no2_umol_m2", "rainfall_mm", "t2m_mean"):
        s = skill[target]
        # Skill must be positive — model better than persistence baseline
        assert s["skill_vs_persistence"] > 0, (
            f"{target} skill is {s['skill_vs_persistence']:.2%}, model didn't beat persistence"
        )


def test_trained_models_present():
    """Trained model joblib files exist locally after training.

    Joblib files are gitignored, so they will be absent in CI; this test
    skips in that case. Skill is verified separately by the JSON skill
    report which IS in the repo.
    """
    missing = []
    for target in ("no2_umol_m2", "rainfall_mm", "t2m_mean"):
        p = REPO_ROOT / "model" / f"model_{target}.joblib"
        if not p.exists():
            missing.append(p.name)
            continue
        assert p.stat().st_size > 1000, f"trained model too small: {p}"
    if missing:
        pytest.skip(f"trained-model artefacts absent (rebuild with model/train_model.py): {missing}")
