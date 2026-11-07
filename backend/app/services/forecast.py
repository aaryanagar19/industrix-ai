from __future__ import annotations

import time
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.ml import registry
from app.ml.common import zscore
from app.ml.forecasting.inference import PARAMS, forecast_batch, uncertainty
from app.ml.forecasting.lstm import CHANNELS, HORIZON, WINDOW
from app.ml.inference import risk as risk_inf
from app.models import Machine, SensorReading
from app.services.common import iso
from app.services import risk as risk_svc

_cache: dict = {}


def hourly_series(db: Session, m: Machine, hours: int = 96) -> tuple[pd.DataFrame, dict]:
    since = utcnow() - timedelta(hours=hours)
    rows = db.query(SensorReading.timestamp, SensorReading.temperature, SensorReading.vibration, SensorReading.pressure, SensorReading.load_pct).filter(
        SensorReading.machine_id == m.id, SensorReading.timestamp >= since).order_by(SensorReading.timestamp).all()
    if not rows:
        return pd.DataFrame(columns=PARAMS), {"hours_available": 0, "raw_points": 0}
    df = pd.DataFrame(rows, columns=["timestamp"] + PARAMS).set_index("timestamp")
    h = df.resample("1h").mean()
    valid = int(h.dropna(how="all").shape[0])
    h = h.interpolate(limit=3)
    return h, {"hours_available": valid, "raw_points": len(df), "missing_hours": int(h.isna().any(axis=1).sum())}


def to_z(h: pd.DataFrame, m: Machine) -> pd.DataFrame:
    z = pd.DataFrame(index=h.index)
    for c, p in zip(CHANNELS, PARAMS):
        z[c] = (h[p] - m.baseline[p]["mean"]) / m.baseline[p]["std"]
    return z


def sufficiency(info: dict, h: pd.DataFrame) -> dict:
    meta = registry.forecast_meta()
    need, rec = meta.get("min_history_hours", WINDOW), meta.get("recommended_history_hours", 48)
    tail_ok = len(h) >= WINDOW and not h.tail(WINDOW).isna().any().any()
    n = info["hours_available"]
    if n < need or not tail_ok:
        return {"status": "insufficient", "message": f"Only {n} hours of continuous history available; at least {need} contiguous hours are required. No forecast is shown rather than an unreliable one."}
    if n < rec:
        return {"status": "limited", "message": f"{n} hours of history available; {rec}+ recommended. Treat the forecast as low-confidence."}
    return {"status": "ok", "message": f"{n} hours of history available."}


def forecast_machine(db: Session, m: Machine) -> dict:
    h, info = hourly_series(db, m)
    suff = sufficiency(info, h)
    out = {"machine_id": m.id, "machine_code": m.code, "generated_at": iso(utcnow()), "data_sufficiency": suff, "model_version": registry.forecast_meta().get("version"),
           "history": [], "forecast": [], "early_warnings": [], "units": {"temperature": "°C", "vibration": "mm/s", "pressure": "bar", "load_pct": "%"},
           "disclaimer": "Statistical forecast from a model trained on synthetic data; not a guarantee of future behaviour."}
    for ts, row in h.tail(48).iterrows():
        out["history"].append({"timestamp": iso(ts.to_pydatetime()), **{p: (None if pd.isna(row[p]) else round(float(row[p]), 3)) for p in PARAMS}})
    if suff["status"] == "insufficient":
        return out
    z = to_z(h, m)
    zf = forecast_batch({m.id: z})[m.id]
    sig = uncertainty()
    last = h.index[-1]
    for k in range(HORIZON):
        pt = {"hour": k + 1, "timestamp": iso((last + timedelta(hours=k + 1)).to_pydatetime())}
        for c, p in zip(range(len(PARAMS)), PARAMS):
            mu, sd = m.baseline[p]["mean"], m.baseline[p]["std"]
            v = mu + sd * float(zf[k, c]); band = 1.96 * sd * float(sig[k, c])
            pt[p] = round(v, 3); pt[f"{p}_lower"] = round(v - band, 3); pt[f"{p}_upper"] = round(v + band, 3)
        out["forecast"].append(pt)
    # early warnings: predicted deviation >= 2.5σ at any hour, or >=2σ for 3 consecutive hours
    for c, p in enumerate(PARAMS):
        col = zf[:, c] if p != "pressure" else np.abs(zf[:, c])
        hit = np.where(col >= 2.5)[0]
        run = next((i for i in range(len(col) - 2) if (col[i:i + 3] >= 2.0).all()), None)
        first = hit[0] if len(hit) else run
        if first is not None:
            out["early_warnings"].append({"parameter": p, "first_hour": int(first) + 1, "predicted_value": out["forecast"][first][p],
                                          "message": f"Forecast {p} may leave its normal range around +{first + 1}h (predicted {out['forecast'][first][p]} {out['units'][p]})."})
    zl = np.abs(z.tail(6).values).mean()
    out["health_indicator"] = {"current": round(float(np.clip(100 - 18 * zl, 0, 100)), 1),
                               "forecast_24h": round(float(np.clip(100 - 18 * np.abs(zf).mean(), 0, 100)), 1),
                               "definition": "Heuristic index: 100 minus 18 x mean |deviation from baseline| (σ). Not a model output."}
    return out


def predicted_risk_all(db: Session, machines: list[Machine]) -> dict:
    """Applies the accident-risk model to the LSTM forecast values for every machine (cached 2 min)."""
    key = tuple(m.id for m in machines)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    series, ok = {}, []
    for m in machines:
        h, info = hourly_series(db, m)
        if sufficiency(info, h)["status"] != "insufficient":
            series[m.id] = to_z(h, m); ok.append(m)
    result = {"hours": [], "fleet_mean": [], "fleet_max": [], "machines": {}, "machines_included": len(ok), "machines_total": len(machines)}
    if not ok:
        _cache[key] = (time.time(), result)
        return result
    zf = forecast_batch(series)
    start = utcnow().replace(minute=0, second=0, microsecond=0)
    per = {}
    for m in ok:
        ctx = risk_svc.machine_context(db, m)
        last = db.query(SensorReading).filter(SensorReading.machine_id == m.id).order_by(SensorReading.timestamp.desc()).first()
        rows = []
        for k in range(HORIZON):
            rows.append({"temperature_dev": float(zf[m.id][k, 0]), "vibration_dev": float(zf[m.id][k, 1]), "pressure_dev": float(zf[m.id][k, 2]),
                         "load_pct": float(np.clip(m.baseline["load_pct"]["mean"] + m.baseline["load_pct"]["std"] * zf[m.id][k, 3], 0, 100)),
                         "shift_hours": last.shift_hours if last else None, "production_intensity": last.production_intensity if last else None,
                         "weather_severity": last.weather_severity if last else None, "temperature_trend": 0.0, "vibration_trend": 0.0, **ctx})
        per[m.id] = risk_inf.predict_proba(rows)
    result["hours"] = [iso(start + timedelta(hours=k + 1)) for k in range(HORIZON)]
    arr = np.stack(list(per.values()))
    result["fleet_mean"] = [round(float(x), 4) for x in arr.mean(axis=0)]
    result["fleet_max"] = [round(float(x), 4) for x in arr.max(axis=0)]
    result["machines"] = {str(i): [round(float(x), 4) for x in v] for i, v in per.items()}
    result["note"] = "Accident model applied to LSTM-forecast sensor values with current maintenance/inspection context. Analytical estimate only."
    _cache[key] = (time.time(), result)
    return result
