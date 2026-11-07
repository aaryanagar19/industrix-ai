"""Lazy, cached loading of serialised model artifacts from MODELS_DIR."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import joblib

from app.ml.common import models_dir

_lock = threading.Lock()
_cache: dict = {}


class ModelNotAvailable(RuntimeError):
    pass


def _path(name: str) -> Path:
    return models_dir() / name


def _get(key, loader):
    with _lock:
        if key not in _cache:
            _cache[key] = loader()
        return _cache[key]


def risk_bundle() -> dict:
    p = _path("risk_model.joblib")
    if not p.exists():
        raise ModelNotAvailable("risk_model.joblib missing - run: python -m app.ml.training.train_all")
    return _get("risk", lambda: joblib.load(p))


def anomaly_bundle() -> dict:
    p = _path("anomaly_model.joblib")
    if not p.exists():
        raise ModelNotAvailable("anomaly_model.joblib missing - run training")
    return _get("anomaly", lambda: joblib.load(p))


def forecast_model():
    p = _path("forecast_lstm.keras")
    if not p.exists():
        raise ModelNotAvailable("forecast_lstm.keras missing - run training")

    def load():
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        import keras
        return keras.saving.load_model(p, compile=False)

    return _get("forecast", load)


def forecast_meta() -> dict:
    return metrics("forecast")


def metrics(name: str) -> dict:
    p = _path(f"metrics_{name}.json")
    return json.loads(p.read_text()) if p.exists() else {}


def available() -> dict:
    return {n: _path(f).exists() for n, f in {"risk": "risk_model.joblib", "anomaly": "anomaly_model.joblib",
                                              "forecast": "forecast_lstm.keras", "nlp": "nlp_classifier.joblib"}.items()}


def reset():
    with _lock:
        _cache.clear()
