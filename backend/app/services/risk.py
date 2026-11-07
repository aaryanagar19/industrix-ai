"""Builds model inputs from DB state and runs the accident-risk model."""
from __future__ import annotations

import time
from datetime import timedelta

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.ml.common import zscore
from app.ml.inference import risk as risk_inf
from app.models import InspectionRecord, Incident, Machine, MaintenanceRecord, RiskPrediction, SensorReading
from app.services.common import get_setting

_ctx_cache: dict[int, tuple[float, dict]] = {}
INSP = {"pass": 0, "conditional": 1, "fail": 2}


def machine_context(db: Session, m: Machine, now=None) -> dict:
    hit = _ctx_cache.get(m.id)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    now = now or utcnow()
    open_due = db.query(func.min(MaintenanceRecord.due_date)).filter(
        MaintenanceRecord.machine_id == m.id, MaintenanceRecord.status.in_(["scheduled", "in_progress"]), MaintenanceRecord.due_date < now).scalar()
    delay = max((now - open_due).total_seconds() / 86400, 0.0) if open_due else 0.0
    prev = db.query(func.count(Incident.id)).filter(Incident.machine_id == m.id, Incident.occurred_at >= now - timedelta(days=90)).scalar() or 0
    insp = db.query(InspectionRecord).filter(InspectionRecord.machine_id == m.id).order_by(InspectionRecord.inspected_at.desc()).first()
    ctx = {"equipment_age_years": round(m.age_years, 2), "maintenance_delay_days": round(delay, 2), "previous_incidents": int(prev),
           "inspection_status": INSP.get(insp.status, 0) if insp else 0}
    _ctx_cache[m.id] = (time.time(), ctx)
    return ctx


def clear_context_cache(machine_id: int | None = None):
    _ctx_cache.pop(machine_id, None) if machine_id else _ctx_cache.clear()


def trend_features(db: Session, m: Machine, now) -> dict:
    lo, hi = now - timedelta(hours=3), now - timedelta(minutes=30)
    row = db.query(func.avg(SensorReading.temperature), func.avg(SensorReading.vibration)).filter(
        SensorReading.machine_id == m.id, SensorReading.timestamp >= lo, SensorReading.timestamp <= hi).one()
    return {"t": row[0], "v": row[1]}


def build_features(db: Session, m: Machine, r: dict) -> dict:
    """r: raw reading dict (temperature, vibration, pressure, load_pct, shift_hours, production_intensity, weather_severity, timestamp)."""
    b = m.baseline or {}
    tdev, vdev = zscore(r.get("temperature"), b, "temperature"), zscore(r.get("vibration"), b, "vibration")
    avg = trend_features(db, m, r.get("timestamp") or utcnow())
    ttr = tdev - zscore(avg["t"], b, "temperature") if avg["t"] is not None else np.nan
    vtr = vdev - zscore(avg["v"], b, "vibration") if avg["v"] is not None else np.nan
    f = {"temperature_dev": tdev, "vibration_dev": vdev, "pressure_dev": zscore(r.get("pressure"), b, "pressure"), "load_pct": r.get("load_pct"),
         "shift_hours": r.get("shift_hours"), "production_intensity": r.get("production_intensity"), "weather_severity": r.get("weather_severity"),
         "temperature_trend": ttr, "vibration_trend": vtr, **machine_context(db, m)}
    return {k: (None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)) for k, v in f.items()}


def thresholds(db: Session) -> dict:
    return risk_inf.effective_thresholds(get_setting(db, "risk_thresholds"))


def prediction_dict(p: RiskPrediction, machine: Machine | None = None) -> dict:
    from app.services.common import iso
    return {"id": p.id, "machine_id": p.machine_id, "machine_code": machine.code if machine else None, "machine_name": machine.name if machine else None,
            "timestamp": iso(p.timestamp), "probability": p.probability, "category": p.category, "priority": p.priority, "model_version": p.model_version,
            "data_quality": p.data_quality, "features": p.features,
            "disclaimer": "Decision-support estimate of event likelihood in the next ~6 hours; not a certified safety controller."}
