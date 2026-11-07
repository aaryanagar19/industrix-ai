"""Multivariate LSTM forecaster (24h history -> next 24 hourly steps) on machine-relative z-scores."""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from app.ml.common import models_dir
from app.ml.training.data_gen import generate_dataset

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
CHANNELS = ["temperature_dev", "vibration_dev", "pressure_dev", "load_dev"]
WINDOW, HORIZON = 24, 24
N_IN = len(CHANNELS) + 2  # + sin/cos hour-of-day


def add_time_features(values: np.ndarray, index: pd.DatetimeIndex) -> np.ndarray:
    h = (index.hour.values + index.minute.values / 60) / 24 * 2 * np.pi
    return np.column_stack([values, np.sin(h), np.cos(h)]).astype("float32")


def make_windows(arr: np.ndarray, stride: int = 3):
    X, Y = [], []
    for i in range(0, len(arr) - WINDOW - HORIZON + 1, stride):
        X.append(arr[i:i + WINDOW])
        Y.append(arr[i + WINDOW:i + WINDOW + HORIZON, :len(CHANNELS)])
    return np.array(X, dtype="float32"), np.array(Y, dtype="float32")


def build_model(units: int = 64):
    import keras
    from keras import layers
    m = keras.Sequential([
        layers.Input((WINDOW, N_IN)), layers.LSTM(units), layers.Dense(96, activation="relu"),
        layers.Dense(HORIZON * len(CHANNELS)), layers.Reshape((HORIZON, len(CHANNELS))),
    ])
    m.compile(optimizer=keras.optimizers.Adam(2e-3), loss="huber")
    return m


def train_forecaster(df: pd.DataFrame | None = None, seed: int = 42, fast: bool = False, epochs: int | None = None) -> dict:
    import keras
    keras.utils.set_random_seed(seed)
    df = df if df is not None else generate_dataset(n_machines=12 if fast else 24, days=45 if fast else 90, seed=seed)
    parts = {"train": ([], []), "val": ([], []), "test": ([], [])}
    for _, g in df.groupby("machine_id"):
        g = g.sort_values("timestamp").set_index("timestamp")[CHANNELS]
        h = g.resample("1h").mean().interpolate(limit=3).dropna()   # properly ordered hourly series
        n = len(h)
        gap = WINDOW + HORIZON  # purge so no window straddles a split boundary
        hv = add_time_features(h.values, h.index)
        segs = {"train": hv[: int(n * 0.65)], "val": hv[int(n * 0.65) + gap: int(n * 0.80)], "test": hv[int(n * 0.80) + gap:]}
        for k, seg in segs.items():
            if len(seg) > WINDOW + HORIZON:
                x, y = make_windows(seg, stride=3 if k == "train" else 6)
                parts[k][0].append(x); parts[k][1].append(y)
    Xtr, Ytr = (np.concatenate(p) for p in parts["train"]); Xva, Yva = (np.concatenate(p) for p in parts["val"]); Xte, Yte = (np.concatenate(p) for p in parts["test"])
    model = build_model()
    cb = [keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True, monitor="val_loss")]
    hist = model.fit(Xtr, Ytr, validation_data=(Xva, Yva), epochs=epochs or (12 if fast else 30), batch_size=64, verbose=0, callbacks=cb)
    pred = model.predict(Xte, verbose=0)
    persist = np.repeat(Xte[:, -1:, :len(CHANNELS)], HORIZON, axis=1)
    zero = np.zeros_like(Yte)  # 'always at baseline' climatology-style reference
    mae = lambda a, b: np.abs(a - b).mean(axis=(0, 1))
    rmse = lambda a, b: np.sqrt(((a - b) ** 2).mean(axis=(0, 1)))
    resid_sigma = (pred - Yte).std(axis=0)  # (HORIZON, channels) used for uncertainty bands
    meta = {
        "version": f"forecast-lstm-{datetime.utcnow():%Y%m%d%H%M}", "trained_at": datetime.utcnow().isoformat() + "Z",
        "data_origin": "synthetic", "window": WINDOW, "horizon": HORIZON, "channels": CHANNELS, "units": "std-deviations from machine baseline",
        "samples": {"train": len(Xtr), "validation": len(Xva), "test": len(Xte)}, "epochs_run": len(hist.history["loss"]),
        "test_metrics": {
            "lstm": {"mae": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), mae(pred, Yte)))), "rmse": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), rmse(pred, Yte))))},
            "baseline_zero": {"mae": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), mae(zero, Yte)))), "rmse": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), rmse(zero, Yte))))},
            "persistence_baseline": {"mae": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), mae(persist, Yte)))), "rmse": dict(zip(CHANNELS, map(lambda v: round(float(v), 4), rmse(persist, Yte))))},
        },
        "residual_sigma": resid_sigma.round(4).tolist(),
        "min_history_hours": WINDOW, "recommended_history_hours": 48,
        "note": "Metrics are on a chronological held-out segment of SYNTHETIC data, in z-score units. The persistence baseline repeats the last observed value; baseline_zero predicts the machine always sits at its normal baseline.",
    }
    model.save(models_dir() / "forecast_lstm.keras")
    (models_dir() / "metrics_forecast.json").write_text(json.dumps(meta, indent=2))
    return meta
