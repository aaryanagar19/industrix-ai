import numpy as np
import pandas as pd

from app.ml import registry
from app.ml.common import RISK_FEATURES
from app.ml.inference import risk as risk_inf
from app.ml.nlp.pipeline import analyze_text
from app.ml.training.data_gen import generate_dataset
from app.ml.training.train_risk import chronological_split, choose_thresholds


def test_dataset_reproducible_and_valid():
    a, b = generate_dataset(3, 5, seed=1), generate_dataset(3, 5, seed=1)
    pd.testing.assert_frame_equal(a, b)
    assert set(RISK_FEATURES) <= set(a.columns) and a.accident_next_6h.isin([0, 1]).all()
    assert a[RISK_FEATURES].isna().any().any()   # missing values exist to exercise imputation


def test_chronological_split_has_no_overlap_or_leakage():
    df = generate_dataset(4, 20, seed=3)
    tr, va, te = chronological_split(df)
    assert tr.timestamp.max() < va.timestamp.min() <= va.timestamp.max() < te.timestamp.min()
    assert (va.timestamp.min() - tr.timestamp.max()) >= pd.Timedelta(hours=6)   # purge gap covers label horizon


def test_thresholds_ordered_and_recall_target():
    rng = np.random.default_rng(0)
    y = (rng.random(5000) < 0.1).astype(int)
    p = np.clip(0.05 + 0.4 * y * rng.random(5000) + 0.05 * rng.random(5000), 0, 1)
    t = choose_thresholds(y, p)
    assert t["moderate"] < t["high"] < t["critical"]
    assert (p[y == 1] >= t["moderate"]).mean() >= 0.88


def test_categorize_boundaries():
    t = {"moderate": 0.1, "high": 0.2, "critical": 0.4}
    assert [risk_inf.categorize(p, t) for p in (0.05, 0.1, 0.2, 0.4)] == ["Low", "Moderate", "High", "Critical"]


def test_inference_handles_missing_and_monotonic_signal():
    base = dict(temperature_dev=0.0, vibration_dev=0.0, pressure_dev=0.0, load_pct=60, equipment_age_years=5, maintenance_delay_days=0, previous_incidents=0, shift_hours=3,
                production_intensity=0.6, weather_severity=0.3, inspection_status=0, temperature_trend=0.0, vibration_trend=0.0)
    hot = {**base, "temperature_dev": 4.0, "vibration_dev": 4.0}
    p0, p1 = risk_inf.predict_proba([base, hot])
    assert 0 <= p0 < p1 <= 1
    missing = {**base, "temperature_dev": None, "vibration_trend": None}
    assert 0 <= risk_inf.predict_proba([missing])[0] <= 1
    assert "temperature_dev" in risk_inf.data_quality(missing)["missing"]


def test_out_of_distribution_and_stale_warnings():
    f = dict(temperature_dev=40.0, vibration_dev=0, pressure_dev=0, load_pct=60, equipment_age_years=5, maintenance_delay_days=0, previous_incidents=0, shift_hours=3,
             production_intensity=0.6, weather_severity=0.3, inspection_status=0, temperature_trend=0, vibration_trend=0)
    dq = risk_inf.data_quality(f, reading_age_s=999)
    assert "temperature_dev" in dq["out_of_distribution"] and dq["status"] == "poor" and any("Stale" in w for w in dq["warnings"])


def test_models_saved_with_honest_metadata():
    m = registry.metrics("risk")
    assert m["data_origin"] == "synthetic" and "xgboost" in m["models"] and "random_forest" in m["models"]
    assert m["models"]["xgboost"]["at_thresholds"]["moderate"]["recall"] >= 0.5
    assert registry.metrics("forecast")["test_metrics"]["persistence_baseline"]


def test_nlp_entities_hazards_urgency():
    a = analyze_text("Smoke and a small fire were seen at CN-01. Evacuate the bay immediately. Inspect wiring and replace the cable.", [{"code": "CN-01", "name": "CNC Mill"}])
    assert "CN-01" in a["machines"]["codes"] and "fire" in a["hazards"] and a["urgency"] == "high" and a["follow_up_actions"]
    routine = analyze_text("Routine lubrication of the compressor completed, all readings normal.")
    assert routine["urgency"] == "low" and routine["incident_type"] == "routine_maintenance"
