"""Isolation Forest on machine-relative deviations (temperature, vibration, pressure, load)."""
from __future__ import annotations

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.common import models_dir
from app.ml.training.data_gen import generate_dataset

from app.ml.anomaly_detection.detector import ANOM_FEATURES, CHANNELS, MIN_ABS_Z, Z_GUARD, add_max_abs, evaluate


def train_anomaly(df: pd.DataFrame | None = None, seed: int = 42, fast: bool = False) -> dict:
    df = df if df is not None else generate_dataset(n_machines=12 if fast else 24, days=45 if fast else 90, seed=seed)
    df = df.sort_values("timestamp")
    cut = df["timestamp"].quantile(0.8)
    # fit on a healthy reference period (no active degradation episode) -- standard practice for unsupervised baselining
    healthy = df[(df.timestamp < cut) & (df.get("degradation_level", 0) < 0.05)]
    train = add_max_abs(healthy[CHANNELS].dropna())
    test_raw = df[df.timestamp >= cut][CHANNELS].dropna()
    test = add_max_abs(test_raw)
    iso = IsolationForest(n_estimators=200, contamination=0.005, random_state=seed, n_jobs=1).fit(train[ANOM_FEATURES])
    dec_train = iso.decision_function(train[ANOM_FEATURES])
    sev = {"medium": 0.0, "high": float(np.quantile(dec_train, 0.003)), "critical": float(np.quantile(dec_train, 0.0005))}

    def rate(x):
        return float(evaluate(x[CHANNELS], iso, sev)["flagged"].mean())

    held = df[df.timestamp >= cut].dropna(subset=CHANNELS)
    healthy_rate = rate(held[held.degradation_level < 0.05])
    degr_rate = rate(held[held.degradation_level > 0.6])
    rng = np.random.default_rng(seed)
    results = {}
    base = test_raw.sample(min(3000, len(test_raw)), random_state=seed).copy()
    base = base[(base.abs() <= 1.5).all(axis=1)]  # inject into clean points only
    injections = {
        "temperature_spike_+5σ": {"temperature_dev": 5}, "vibration_surge_+5σ": {"vibration_dev": 5},
        "pressure_instability_±5σ": {"pressure_dev": 5}, "load_overload_+4σ": {"load_dev": 4},
        "combined_mild_+2.5σ_on_all": {"temperature_dev": 2.5, "vibration_dev": 2.5, "pressure_dev": 2.5, "load_dev": 2.5},
        "combined_mild_+2σ_temp_vib": {"temperature_dev": 2.0, "vibration_dev": 2.0},
    }
    for name, inj in injections.items():
        x = base.copy()
        for k, v in inj.items():
            x[k] = x[k] + v * (rng.choice([-1, 1], len(x)) if k == "pressure_dev" else 1)
        results[name] = round(rate(x), 4)
    meta = {"version": f"anomaly-iforest-{datetime.utcnow():%Y%m%d%H%M}", "trained_at": datetime.utcnow().isoformat() + "Z",
            "data_origin": "synthetic", "rows_train": len(train), "contamination": 0.005, "training_set": "healthy reference period (latent degradation < 0.05)", "min_abs_z": MIN_ABS_Z,
            "severity_thresholds": sev, "flag_rate_healthy_periods_heldout": round(healthy_rate, 4), "flag_rate_during_severe_degradation_heldout": round(degr_rate, 4), "z_guard": Z_GUARD,
            "detection_rate_on_injected_anomalies": results,
            "note": "Hybrid detector (Isolation Forest + z-score guard). Flag rate on healthy periods is the false-alarm rate; flag rate during degradation is the detection rate. "
                    "Detection rates are on synthetically injected deviations, not on real faults."}
    joblib.dump({"model": iso, "features": ANOM_FEATURES, "severity": sev, "version": meta["version"], "min_abs_z": MIN_ABS_Z}, models_dir() / "anomaly_model.joblib")
    (models_dir() / "metrics_anomaly.json").write_text(json.dumps(meta, indent=2))
    return meta
