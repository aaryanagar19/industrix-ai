from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml import registry
from app.ml.common import FEATURE_LABELS, RISK_FEATURES

_explainer = None


def _get():
    global _explainer
    if _explainer is None:
        import shap
        _explainer = shap.TreeExplainer(registry.risk_bundle()["pipeline"].named_steps["clf"])
    return _explainer


def _plain(feature: str, value, shap_v: float, normal) -> str:
    label = FEATURE_LABELS[feature].split(" (")[0].lower()
    direction = "raised" if shap_v > 0 else "lowered"
    if feature.endswith("_dev") or feature.endswith("_trend"):
        return f"{label.capitalize()} is {value:+.1f}σ from normal, which {direction} the estimated risk."
    return f"{FEATURE_LABELS[feature]} = {value:g} (typical {normal:g}) {direction} the estimated risk."


def explain(features: dict, top_k: int = 8) -> dict:
    b = registry.risk_bundle()
    X = pd.DataFrame([{f: (np.nan if features.get(f) is None else features.get(f)) for f in RISK_FEATURES}])[RISK_FEATURES]
    A = b["pipeline"].named_steps["imputer"].transform(X)
    sv = _get().shap_values(A)[0]
    base = float(np.ravel(_get().expected_value)[0])
    items = []
    for f, v, s in zip(RISK_FEATURES, A[0], sv):
        normal = b["feature_stats"][f]["median"]
        items.append({"feature": f, "label": FEATURE_LABELS[f], "value": round(float(v), 3), "typical_value": round(normal, 3),
                      "shap": round(float(s), 4), "direction": "increases_risk" if s > 0 else "decreases_risk", "explanation": _plain(f, float(v), float(s), normal)})
    items.sort(key=lambda d: -abs(d["shap"]))
    up = [i for i in items if i["shap"] > 0][:top_k]
    down = [i for i in items if i["shap"] < 0][:top_k]
    return {"base_value_logodds": round(base, 4), "contributions": items, "top_increasing": up, "top_decreasing": down,
            "summary": ("Main model-detected drivers: " + "; ".join(i["explanation"] for i in up[:3])) if up else "No input is pushing the estimate above the fleet average.",
            "disclaimer": "SHAP shows which inputs the model relied on (in log-odds units). It reflects statistical association learned from training data and is NOT proof of physical causation."}
