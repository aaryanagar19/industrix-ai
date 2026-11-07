from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml import registry
from app.ml.forecasting.lstm import CHANNELS, HORIZON, WINDOW, add_time_features

PARAMS = ["temperature", "vibration", "pressure", "load_pct"]


def forecast_batch(hourly_z: dict[int, pd.DataFrame]) -> dict[int, np.ndarray]:
    """hourly_z: machine_id -> DataFrame (index hourly DatetimeIndex, columns CHANNELS, >= WINDOW rows). Returns (HORIZON, 4) z forecasts."""
    if not hourly_z:
        return {}
    model = registry.forecast_model()
    ids = list(hourly_z)
    X = np.stack([add_time_features(hourly_z[i][CHANNELS].values[-WINDOW:], hourly_z[i].index[-WINDOW:]) for i in ids])
    pred = model.predict(X, verbose=0)
    return {i: pred[k] for k, i in enumerate(ids)}


def uncertainty() -> np.ndarray:
    meta = registry.forecast_meta()
    return np.array(meta["residual_sigma"]) if meta else np.ones((HORIZON, len(CHANNELS)))
