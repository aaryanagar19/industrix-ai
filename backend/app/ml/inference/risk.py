from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.ml import registry
from app.ml.common import CATEGORIES, PRIORITY, RISK_FEATURES


def effective_thresholds(db_override: dict | None = None) -> dict:
    """Priority: DB setting > environment variable > thresholds learned during training."""
    t = dict(registry.risk_bundle()["thresholds"])
    s = get_settings()
    for k, v in (("moderate", s.risk_threshold_moderate), ("high", s.risk_threshold_high), ("critical", s.risk_threshold_critical)):
        if v is not None:
            t[k] = v
    if db_override:
        t.update({k: float(v) for k, v in db_override.items() if k in t})
    return t


def categorize(p: float, thr: dict) -> str:
    return "Critical" if p >= thr["critical"] else "High" if p >= thr["high"] else "Moderate" if p >= thr["moderate"] else "Low"


def predict_proba(rows: list[dict]) -> np.ndarray:
    b = registry.risk_bundle()
    X = pd.DataFrame([{f: (np.nan if r.get(f) is None else r.get(f)) for f in RISK_FEATURES} for r in rows])[RISK_FEATURES]
    raw = b["pipeline"].predict_proba(X)[:, 1]
    return np.clip(b["calibrator"].predict(raw), 0, 1)


def data_quality(features: dict, reading_age_s: float | None = None, stale_after: int | None = None) -> dict:
    b = registry.risk_bundle()
    warnings, level = [], "ok"
    missing = [f for f in RISK_FEATURES if features.get(f) is None or (isinstance(features.get(f), float) and np.isnan(features[f]))]
    if missing:
        warnings.append(f"Missing inputs imputed with training medians: {', '.join(missing)}")
        level = "degraded"
    ood = []
    for f, v in features.items():
        st = b["feature_stats"].get(f)
        if st is None or v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        rng = max(st["max"] - st["min"], 1e-9)
        if v < st["min"] - 0.25 * rng or v > st["max"] + 0.25 * rng:
            ood.append(f)
    if ood:
        warnings.append(f"Out-of-distribution inputs (outside range seen in training): {', '.join(ood)}. Prediction may be unreliable.")
        level = "poor" if level != "poor" else level
    stale_after = stale_after or get_settings().stale_reading_seconds
    if reading_age_s is not None and reading_age_s > stale_after:
        warnings.append(f"Stale reading: latest sensor data is {int(reading_age_s)} s old (limit {stale_after} s).")
        level = "poor"
    return {"status": level, "warnings": warnings, "missing": missing, "out_of_distribution": ood}


def assess(features: dict, thr: dict, reading_age_s: float | None = None) -> dict:
    p = float(predict_proba([features])[0])
    cat = categorize(p, thr)
    dq = data_quality(features, reading_age_s)
    ths = [thr["moderate"], thr["high"], thr["critical"]]
    near = any(abs(p - t) / t < 0.10 for t in ths)
    if near:
        dq["warnings"].append("Prediction is within 10% of a category threshold; treat the category as uncertain.")
    return {"probability": round(p, 4), "category": cat, "priority": PRIORITY[cat], "model_version": registry.risk_bundle()["version"],
            "data_quality": dq, "borderline": near}
