"""Sensor-ingestion pipeline: store reading -> features -> risk prediction -> anomaly detection -> notifications -> events."""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.ml import registry
from app.ml.anomaly_detection import detector
from app.ml.common import zscore
from app.ml.inference import risk as risk_inf
from app.models import AnomalyRecord, Machine, RiskPrediction, SensorReading
from app.services import risk as risk_svc
from app.services.common import iso, notif_dict, notify

SUGGESTIONS = {
    "temperature": "Check coolant level/flow and fan operation, look for blocked ventilation or friction sources, and compare with the equipment's rated temperature limit.",
    "vibration": "Inspect bearings, shaft alignment, mounting bolts and rotating balance; compare with the last vibration survey.",
    "pressure": "Inspect relief valves, seals, filters and the pressure regulator; check for leaks, blockage or supply instability.",
    "load_pct": "Review production scheduling for overload, verify motor/drive current against rated capacity.",
}
_last_pred_ts: dict[int, tuple] = {}
_last_anom: dict[tuple, float] = {}
PERSIST_EVERY_S = 10
UNITS = {"temperature": "°C", "vibration": "mm/s", "pressure": "bar", "load_pct": "%"}


def ingest_reading(db: Session, m: Machine, data: dict, source: str = "simulated") -> dict:
    """Returns {"reading":..., "prediction":..., "anomaly":..., "notifications":[...]} (JSON-ready)."""
    ts = data.get("timestamp") or utcnow()
    r = SensorReading(machine_id=m.id, timestamp=ts, temperature=data.get("temperature"), vibration=data.get("vibration"), pressure=data.get("pressure"),
                      load_pct=data.get("load_pct"), shift_hours=data.get("shift_hours"), production_intensity=data.get("production_intensity"),
                      weather_severity=data.get("weather_severity"), data_source=source)
    db.add(r)
    if m.status == "running":
        m.operating_hours = (m.operating_hours or 0) + 0.001
    db.commit()
    out: dict = {"reading": reading_dict(r, m), "prediction": None, "anomaly": None, "notifications": []}
    if not registry.available()["risk"]:
        return out

    feats = risk_svc.build_features(db, m, {**data, "timestamp": ts})
    age = max((utcnow() - ts).total_seconds(), 0)
    thr = risk_svc.thresholds(db)
    a = risk_inf.assess(feats, thr, age)
    prev = _last_pred_ts.get(m.id)
    persist = prev is None or (ts - prev[0]).total_seconds() >= PERSIST_EVERY_S or a["category"] != prev[1]
    pred = RiskPrediction(machine_id=m.id, reading_id=r.id, timestamp=ts, probability=a["probability"], category=a["category"], priority=a["priority"],
                          model_version=a["model_version"], features=feats, data_quality=a["data_quality"])
    if persist:
        db.add(pred); db.commit()
        _last_pred_ts[m.id] = (ts, a["category"])
        if prev and a["category"] in ("High", "Critical") and prev[1] != a["category"]:
            n = notify(db, f"{a['category']} accident risk: {m.code}", f"{m.name} risk estimate {a['probability']:.0%} ({a['priority']}). Review required by authorised personnel.",
                       "critical" if a["category"] == "Critical" else "warning", "risk", m.id, cooldown_s=120)
            if n:
                out["notifications"].append(notif_dict(n))
    out["prediction"] = risk_svc.prediction_dict(pred, m) if pred.id else {**risk_svc.prediction_dict(pred, m), "id": None}

    # anomaly detection
    if registry.available()["anomaly"] and m.baseline:
        ab = registry.anomaly_bundle()
        row = pd.DataFrame([{c: zscore(data.get(k), m.baseline, k) for c, k in
                             (("temperature_dev", "temperature"), ("vibration_dev", "vibration"), ("pressure_dev", "pressure"), ("load_dev", "load_pct"))}]).fillna(0.0)
        res = detector.evaluate(row, ab["model"], ab["severity"]).iloc[0]
        if bool(res["flagged"]):
            param = res["parameter"]
            key = (m.id, param)
            now_s = ts.timestamp()
            if now_s - _last_anom.get(key, 0) >= 120:
                _last_anom[key] = now_s
                bm, bs = m.baseline[param]["mean"], m.baseline[param]["std"]
                rec = AnomalyRecord(machine_id=m.id, reading_id=r.id, timestamp=ts, parameter=param, observed_value=float(data.get(param) or 0),
                                    expected_low=round(bm - 3 * bs, 3), expected_high=round(bm + 3 * bs, 3), score=float(res["score"]), severity=str(res["severity"]),
                                    suggestion=SUGGESTIONS[param] + " Have a qualified technician verify on site.")
                db.add(rec); db.commit()
                out["anomaly"] = anomaly_dict(rec, m)
                if rec.severity in ("high", "critical"):
                    n = notify(db, f"{rec.severity.title()} anomaly: {m.code} {param}", f"{param} reading {rec.observed_value:.2f}{UNITS[param]} outside expected {rec.expected_low}-{rec.expected_high}.",
                               "critical" if rec.severity == "critical" else "warning", "anomaly", m.id, cooldown_s=120)
                    if n:
                        out["notifications"].append(notif_dict(n))
    return out


def reading_dict(r: SensorReading, m: Machine | None = None) -> dict:
    return {"id": r.id, "machine_id": r.machine_id, "machine_code": m.code if m else None, "timestamp": iso(r.timestamp), "temperature": r.temperature,
            "vibration": r.vibration, "pressure": r.pressure, "load_pct": r.load_pct, "shift_hours": r.shift_hours, "production_intensity": r.production_intensity,
            "weather_severity": r.weather_severity, "data_source": r.data_source}


def anomaly_dict(a: AnomalyRecord, m: Machine | None = None) -> dict:
    return {"id": a.id, "machine_id": a.machine_id, "machine_code": m.code if m else None, "machine_name": m.name if m else None, "timestamp": iso(a.timestamp),
            "parameter": a.parameter, "observed_value": a.observed_value, "expected_low": a.expected_low, "expected_high": a.expected_high, "unit": UNITS.get(a.parameter, ""),
            "score": a.score, "severity": a.severity, "suggestion": a.suggestion, "acknowledged": a.acknowledged}
