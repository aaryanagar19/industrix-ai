"""Shared ML constants: machine-type baselines, feature definitions, normalisation helpers.

All models work on MACHINE-RELATIVE deviations (z-scores against each machine's own baseline) so one
global model can serve machines whose absolute units differ (e.g. 6 bar vs 140 bar)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.core.config import get_settings

SENSORS = ["temperature", "vibration", "pressure", "load_pct"]

# mean/std of NORMAL operation per machine type (units: degC, mm/s, bar, %)
MACHINE_TYPES: dict[str, dict[str, dict[str, float]]] = {
    "cnc_mill": {"temperature": (62, 3), "vibration": (2.1, 0.30), "pressure": (6.5, 0.30), "load_pct": (60, 8)},
    "lathe": {"temperature": (58, 3), "vibration": (2.4, 0.35), "pressure": (6.0, 0.30), "load_pct": (55, 9)},
    "grinder": {"temperature": (66, 3.5), "vibration": (3.0, 0.40), "pressure": (5.5, 0.30), "load_pct": (58, 8)},
    "hydraulic_press": {"temperature": (70, 4), "vibration": (3.2, 0.40), "pressure": (140, 6), "load_pct": (62, 9)},
    "furnace": {"temperature": (410, 12), "vibration": (1.2, 0.20), "pressure": (2.2, 0.15), "load_pct": (70, 7)},
    "boiler": {"temperature": (185, 6), "vibration": (1.5, 0.25), "pressure": (12, 0.6), "load_pct": (68, 7)},
    "compressor": {"temperature": (82, 4), "vibration": (3.6, 0.45), "pressure": (8.5, 0.35), "load_pct": (64, 8)},
    "chiller": {"temperature": (7, 0.8), "vibration": (2.2, 0.30), "pressure": (4.2, 0.25), "load_pct": (60, 8)},
    "pump": {"temperature": (55, 3), "vibration": (2.6, 0.35), "pressure": (5.0, 0.25), "load_pct": (58, 8)},
    "conveyor": {"temperature": (45, 3), "vibration": (1.8, 0.30), "pressure": (3.0, 0.20), "load_pct": (66, 9)},
    "robot": {"temperature": (48, 2.5), "vibration": (1.4, 0.25), "pressure": (5.0, 0.25), "load_pct": (62, 8)},
    "packaging": {"temperature": (40, 2.5), "vibration": (1.6, 0.25), "pressure": (4.5, 0.25), "load_pct": (64, 9)},
}


def baseline_for(machine_type: str, jitter: float = 0.0, rng: np.random.Generator | None = None) -> dict:
    spec = MACHINE_TYPES.get(machine_type, MACHINE_TYPES["cnc_mill"])
    out = {}
    for k, (m, s) in spec.items():
        f = 1.0 + (rng.normal(0, jitter) if rng is not None and jitter else 0.0)
        out[k] = {"mean": round(float(m * f), 4), "std": round(float(s), 4)}
    return out


RISK_FEATURES = [
    "temperature_dev", "vibration_dev", "pressure_dev", "load_pct",
    "equipment_age_years", "maintenance_delay_days", "previous_incidents", "shift_hours",
    "production_intensity", "weather_severity", "inspection_status",
    "temperature_trend", "vibration_trend",
]

FEATURE_LABELS = {
    "temperature_dev": "Temperature vs. machine baseline",
    "vibration_dev": "Vibration vs. machine baseline",
    "pressure_dev": "Pressure vs. machine baseline",
    "load_pct": "Machine load (%)",
    "equipment_age_years": "Equipment age (years)",
    "maintenance_delay_days": "Maintenance overdue (days)",
    "previous_incidents": "Incidents in last 90 days",
    "shift_hours": "Hours into current shift",
    "production_intensity": "Production intensity (0-1)",
    "weather_severity": "Weather severity (0-1)",
    "inspection_status": "Latest inspection (0 pass, 1 conditional, 2 fail)",
    "temperature_trend": "Temperature trend (σ above 3h mean)",
    "vibration_trend": "Vibration trend (σ above 3h mean)",
}

PRIORITY = {
    "Low": "P4 - Routine monitoring",
    "Moderate": "P3 - Review within 24 hours",
    "High": "P2 - Investigate within 1 hour",
    "Critical": "P1 - Immediate review by authorised safety personnel",
}
CATEGORIES = ["Low", "Moderate", "High", "Critical"]


def models_dir() -> Path:
    p = Path(get_settings().models_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def zscore(value, baseline: dict | None, key: str):
    """Deviation (in std units) of `value` from machine baseline. NaN-safe."""
    if value is None or baseline is None or key not in baseline:
        return np.nan
    b = baseline[key]
    return (float(value) - b["mean"]) / b["std"] if b["std"] else np.nan


class PlattCalibrator:
    """Sigmoid (Platt) calibration on the logit of the raw model probability. Continuous output (unlike isotonic's step
    function), which keeps risk-category thresholds meaningful."""

    def __init__(self):
        from sklearn.linear_model import LogisticRegression
        self.lr = LogisticRegression(C=1e6, max_iter=1000)

    @staticmethod
    def _logit(p):
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def fit(self, raw, y):
        self.lr.fit(self._logit(raw), y)
        return self

    def predict(self, raw):
        return self.lr.predict_proba(self._logit(raw))[:, 1]
