from datetime import timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func

from app.api.deps import DB, Pagination, bucket_expr, get_machine_or_404, paginate
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.ml import registry
from app.ml.anomaly_detection import detector
from app.ml.common import models_dir, zscore
from app.ml.explainability import shap_explainer
from app.ml.inference import risk as risk_inf
from app.models import AnomalyRecord, Machine, ModelVersion, RiskPrediction, SensorReading
from app.schemas.ops import AnomalyScanIn, ForecastIn, PredictIn, ThresholdsIn
from app.services import forecast as forecast_svc
from app.services import risk as risk_svc
from app.services.common import audit, iso, set_setting
from app.services.ingest import SUGGESTIONS, UNITS, anomaly_dict
from app.services.propagation import latest_prediction

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _need(model: str):
    if not registry.available().get(model):
        raise HTTPException(503, f"Model '{model}' is not trained. Run: python -m app.ml.training.train_all")


def baseline_comparison(m: Machine, feats: dict, reading: dict | None) -> list[dict]:
    out = []
    for key, dev in (("temperature", "temperature_dev"), ("vibration", "vibration_dev"), ("pressure", "pressure_dev"), ("load_pct", None)):
        b = m.baseline.get(key)
        if not b:
            continue
        val = (reading or {}).get(key)
        z = feats.get(dev) if dev else (None if val is None else (val - b["mean"]) / b["std"])
        out.append({"parameter": key, "value": val, "baseline_mean": b["mean"], "normal_low": round(b["mean"] - 2 * b["std"], 3), "normal_high": round(b["mean"] + 2 * b["std"], 3),
                    "deviation_sigma": None if z is None else round(float(z), 2), "unit": UNITS[key]})
    return out


@router.post("/predict")
def predict(body: PredictIn, db: DB, user=Depends(get_current_user)):
    _need("risk")
    m = get_machine_or_404(db, body.machine_id)
    last = db.query(SensorReading).filter(SensorReading.machine_id == m.id).order_by(SensorReading.timestamp.desc()).first()
    raw = {k: getattr(body, k) if getattr(body, k) is not None else (getattr(last, k, None) if last else None)
           for k in ("temperature", "vibration", "pressure", "load_pct", "shift_hours", "production_intensity", "weather_severity")}
    ts = utcnow()
    feats = risk_svc.build_features(db, m, {**raw, "timestamp": ts})
    for k in ("equipment_age_years", "maintenance_delay_days", "previous_incidents"):
        if getattr(body, k) is not None:
            feats[k] = float(getattr(body, k))
    if body.inspection_status:
        feats["inspection_status"] = float({"pass": 0, "conditional": 1, "fail": 2}[body.inspection_status])
    overridden = any(getattr(body, k) is not None for k in raw) or any(getattr(body, k) is not None for k in ("equipment_age_years", "maintenance_delay_days", "previous_incidents", "inspection_status"))
    age = None if (overridden or not last) else (ts - last.timestamp).total_seconds()
    thr = risk_svc.thresholds(db)
    a = risk_inf.assess(feats, thr, age)
    if overridden:
        a["data_quality"]["warnings"].insert(0, "What-if prediction: some inputs were manually overridden.")
    pred = RiskPrediction(machine_id=m.id, reading_id=last.id if last else None, timestamp=ts, probability=a["probability"], category=a["category"], priority=a["priority"],
                          model_version=a["model_version"], features=feats, data_quality=a["data_quality"])
    expl = None
    if body.explain:
        expl = shap_explainer.explain(feats)
        pred.contributions = expl
    db.add(pred); db.commit()
    audit(db, user, "predict", "machine", m.id, {"p": a["probability"], "whatif": overridden})
    return {**risk_svc.prediction_dict(pred, m), "borderline": a["borderline"], "thresholds": thr, "explanation": expl, "baseline_comparison": baseline_comparison(m, feats, raw)}


@router.get("/predictions")
def list_predictions(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), machine_id: int | None = None, category: str | None = None, hours: int | None = Query(None, ge=1, le=720)):
    q = db.query(RiskPrediction, Machine).join(Machine, Machine.id == RiskPrediction.machine_id)
    if machine_id: q = q.filter(RiskPrediction.machine_id == machine_id)
    if category: q = q.filter(RiskPrediction.category == category)
    if hours: q = q.filter(RiskPrediction.timestamp >= utcnow() - timedelta(hours=hours))
    total = q.count()
    rows = q.order_by(RiskPrediction.timestamp.desc()).offset(p.offset).limit(p.page_size).all()
    return {"items": [risk_svc.prediction_dict(pr, m) for pr, m in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.get("/explanations/{prediction_id}")
def explanation(prediction_id: int, db: DB, user=Depends(get_current_user)):
    _need("risk")
    pr = db.get(RiskPrediction, prediction_id)
    if not pr:
        raise HTTPException(404, "Prediction not found")
    m = db.get(Machine, pr.machine_id)
    if not pr.contributions:
        pr.contributions = shap_explainer.explain(pr.features)
        db.commit()
    rd = None
    if pr.reading_id:
        r = db.get(SensorReading, pr.reading_id)
        rd = {k: getattr(r, k) for k in ("temperature", "vibration", "pressure", "load_pct")} if r else None
    return {"prediction": risk_svc.prediction_dict(pr, m), "explanation": pr.contributions, "baseline_comparison": baseline_comparison(m, pr.features, rd)}


@router.post("/forecast")
def forecast(body: ForecastIn, db: DB, user=Depends(get_current_user)):
    _need("forecast")
    return forecast_svc.forecast_machine(db, get_machine_or_404(db, body.machine_id))


@router.post("/anomaly-detection")
def anomaly_scan(body: AnomalyScanIn, db: DB, user=Depends(require_roles("plant_manager", "safety_manager", "safety_officer", "maintenance_engineer"))):
    """Re-scan a machine's stored readings with the Isolation-Forest hybrid detector."""
    _need("anomaly")
    m = get_machine_or_404(db, body.machine_id)
    since = utcnow() - timedelta(hours=body.hours)
    rows = db.query(SensorReading).filter(SensorReading.machine_id == m.id, SensorReading.timestamp >= since).order_by(SensorReading.timestamp).all()
    if not rows:
        return {"machine_id": m.id, "scanned": 0, "flagged": 0, "events": [], "message": "No readings in the selected window."}
    step = max(len(rows) // 6000, 1)
    rows = rows[::step]
    ab = registry.anomaly_bundle()
    df = pd.DataFrame({"temperature_dev": [zscore(r.temperature, m.baseline, "temperature") for r in rows], "vibration_dev": [zscore(r.vibration, m.baseline, "vibration") for r in rows],
                       "pressure_dev": [zscore(r.pressure, m.baseline, "pressure") for r in rows], "load_dev": [zscore(r.load_pct, m.baseline, "load_pct") for r in rows]}).fillna(0.0)
    res = detector.evaluate(df, ab["model"], ab["severity"])
    events, last_t = [], {}
    for i, r in enumerate(rows):
        if not res.iloc[i]["flagged"]:
            continue
        param = res.iloc[i]["parameter"]
        if param in last_t and (r.timestamp - last_t[param]).total_seconds() < 600:
            continue  # collapse bursts into one event per 10 minutes
        last_t[param] = r.timestamp
        b = m.baseline[param]
        ev = {"machine_id": m.id, "machine_code": m.code, "timestamp": iso(r.timestamp), "parameter": param, "observed_value": getattr(r, param), "expected_low": round(b["mean"] - 3 * b["std"], 3),
              "expected_high": round(b["mean"] + 3 * b["std"], 3), "score": float(res.iloc[i]["score"]), "severity": res.iloc[i]["severity"], "suggestion": SUGGESTIONS[param], "unit": UNITS[param]}
        events.append(ev)
    saved = 0
    if body.persist:
        for ev in events:
            exists = db.query(AnomalyRecord.id).filter(AnomalyRecord.machine_id == m.id, AnomalyRecord.parameter == ev["parameter"],
                                                       AnomalyRecord.timestamp == pd.Timestamp(ev["timestamp"].rstrip("Z")).to_pydatetime()).first()
            if not exists:
                db.add(AnomalyRecord(machine_id=m.id, timestamp=pd.Timestamp(ev["timestamp"].rstrip("Z")).to_pydatetime(), parameter=ev["parameter"], observed_value=ev["observed_value"] or 0,
                                     expected_low=ev["expected_low"], expected_high=ev["expected_high"], score=ev["score"], severity=ev["severity"], suggestion=ev["suggestion"]))
                saved += 1
        db.commit()
    return {"machine_id": m.id, "machine_code": m.code, "scanned": len(rows), "flagged": int(res["flagged"].sum()), "events": events[-100:], "saved": saved,
            "model_version": ab["version"], "method": "Isolation Forest + z-score guard rail"}


@router.get("/anomalies")
def list_anomalies(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), machine_id: int | None = None, severity: str | None = None, hours: int | None = Query(None, ge=1, le=2160),
                   acknowledged: bool | None = None, parameter: str | None = None):
    q = db.query(AnomalyRecord, Machine).join(Machine, Machine.id == AnomalyRecord.machine_id)
    if machine_id: q = q.filter(AnomalyRecord.machine_id == machine_id)
    if severity: q = q.filter(AnomalyRecord.severity == severity)
    if parameter: q = q.filter(AnomalyRecord.parameter == parameter)
    if acknowledged is not None: q = q.filter(AnomalyRecord.acknowledged == acknowledged)
    if hours: q = q.filter(AnomalyRecord.timestamp >= utcnow() - timedelta(hours=hours))
    total = q.count()
    rows = q.order_by(AnomalyRecord.timestamp.desc()).offset(p.offset).limit(p.page_size).all()
    return {"items": [anomaly_dict(a, m) for a, m in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.patch("/anomalies/{anomaly_id}/acknowledge")
def ack_anomaly(anomaly_id: int, db: DB, user=Depends(require_roles("plant_manager", "safety_manager", "safety_officer", "maintenance_engineer"))):
    a = db.get(AnomalyRecord, anomaly_id)
    if not a:
        raise HTTPException(404, "Anomaly not found")
    a.acknowledged = True
    db.commit()
    audit(db, user, "ack_anomaly", "anomaly", a.id)
    return anomaly_dict(a)


@router.get("/anomalies/trend")
def anomaly_trend(db: DB, user=Depends(get_current_user), hours: int = Query(168, ge=1, le=2160), machine_id: int | None = None):
    bucket = 3600 if hours <= 72 else 86400
    b = bucket_expr(db, AnomalyRecord.timestamp, bucket).label("b")
    q = db.query(func.min(AnomalyRecord.timestamp), AnomalyRecord.severity, func.count(AnomalyRecord.id)).filter(AnomalyRecord.timestamp >= utcnow() - timedelta(hours=hours))
    if machine_id: q = q.filter(AnomalyRecord.machine_id == machine_id)
    series: dict = {}
    for t, sev, n in q.group_by(b, AnomalyRecord.severity).all():
        key = iso(t.replace(minute=0, second=0, microsecond=0) if bucket == 3600 else t.replace(hour=0, minute=0, second=0, microsecond=0))
        series.setdefault(key, {"bucket": key, "medium": 0, "high": 0, "critical": 0})[sev] = n
    by_param = {p: n for p, n in db.query(AnomalyRecord.parameter, func.count(AnomalyRecord.id)).filter(AnomalyRecord.timestamp >= utcnow() - timedelta(hours=hours)).group_by(AnomalyRecord.parameter)}
    return {"bucket_seconds": bucket, "series": sorted(series.values(), key=lambda s: s["bucket"]), "by_parameter": by_param}


@router.get("/model-performance")
def model_performance(db: DB, user=Depends(get_current_user)):
    risk, anomaly, fc, nlp = (registry.metrics(n) for n in ("risk", "anomaly", "forecast", "nlp"))
    return {"available": registry.available(), "risk": risk, "anomaly": anomaly, "forecast": fc, "nlp": nlp,
            "active_thresholds": risk_svc.thresholds(db) if registry.available()["risk"] else None,
            "threshold_method": "moderate = highest threshold catching >=90% of validation positives; high = F2-optimal; critical = lowest threshold with precision >= 50%. Calibrated probabilities, validation split only.",
            "data_origin_warning": "All models were trained and evaluated on SYNTHETIC data produced by app/ml/training/data_gen.py. These figures demonstrate the pipeline and must not be read as real-world safety performance.",
            "versions": [{"name": v.name, "kind": v.kind, "version": v.version, "trained_at": iso(v.trained_at), "data_origin": v.data_origin, "is_active": v.is_active} for v in db.query(ModelVersion).order_by(ModelVersion.trained_at.desc()).limit(20)]}


@router.get("/shap-summary.png")
def shap_png(user=Depends(get_current_user)):
    p = models_dir() / "shap_summary.png"
    if not p.exists():
        raise HTTPException(404, "SHAP summary not generated yet")
    return FileResponse(p, media_type="image/png")


@router.get("/thresholds")
def get_thresholds(db: DB, user=Depends(get_current_user)):
    _need("risk")
    return {"active": risk_svc.thresholds(db), "trained": registry.risk_bundle()["thresholds"]}


@router.put("/thresholds")
def put_thresholds(body: ThresholdsIn, db: DB, user=Depends(require_roles("safety_manager"))):
    if not (body.moderate < body.high < body.critical):
        raise HTTPException(422, "Thresholds must satisfy moderate < high < critical")
    set_setting(db, "risk_thresholds", body.model_dump())
    audit(db, user, "update_thresholds", "settings", "risk_thresholds", body.model_dump())
    return {"active": risk_svc.thresholds(db)}


@router.get("/predicted-risk")
def predicted_risk(db: DB, user=Depends(get_current_user), facility_id: int | None = None):
    _need("forecast"); _need("risk")
    q = db.query(Machine).filter(Machine.status == "running")
    if facility_id: q = q.filter(Machine.facility_id == facility_id)
    return forecast_svc.predicted_risk_all(db, q.all())
