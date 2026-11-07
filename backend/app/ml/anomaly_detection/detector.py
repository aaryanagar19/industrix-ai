"""Hybrid anomaly detector.

* Isolation Forest (multivariate) -> unusual COMBINATIONS of readings.
* Z-score guard rail (|z| >= Z_GUARD) -> large single-channel excursions. Isolation Forests cannot score points
  beyond the training range any worse than the most extreme training point, so a univariate guard is required.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CHANNELS = ["temperature_dev", "vibration_dev", "pressure_dev", "load_dev"]
PARAM_NAMES = {"temperature_dev": "temperature", "vibration_dev": "vibration", "pressure_dev": "pressure", "load_dev": "load_pct"}
ANOM_FEATURES = CHANNELS + ["max_abs_dev"]
MIN_ABS_Z, Z_GUARD = 2.0, 3.5


def add_max_abs(x: pd.DataFrame) -> pd.DataFrame:
    x = x[CHANNELS].copy()
    x["max_abs_dev"] = x[CHANNELS].abs().max(axis=1)
    return x


def evaluate(x: pd.DataFrame, iso, sev: dict) -> pd.DataFrame:
    """Return per-row: flagged (bool), score (0..1), severity, parameter (most deviant channel)."""
    x = add_max_abs(x)
    dec = iso.decision_function(x[ANOM_FEATURES])
    mz = x["max_abs_dev"].values
    flagged = ((dec < 0) & (mz >= MIN_ABS_Z)) | (mz >= Z_GUARD)
    score = np.maximum(np.clip((0.05 - dec) / 0.15, 0, 1), np.clip((mz - 2) / 6, 0, 1))
    severity = np.where((dec <= sev["critical"]) | (mz >= 6), "critical", np.where((dec <= sev["high"]) | (mz >= 4.5), "high", "medium"))
    param = np.array([PARAM_NAMES[c] for c in CHANNELS])[np.nan_to_num(x[CHANNELS].abs().values).argmax(axis=1)]
    return pd.DataFrame({"flagged": flagged, "score": score.round(4), "severity": severity, "parameter": param, "decision": dec.round(4), "max_abs_dev": mz.round(3)}, index=x.index)
