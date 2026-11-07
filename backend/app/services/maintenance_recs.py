"""Heuristic preventive-maintenance recommendations. score = 0.5*risk + 0.2*anomalies + 0.15*time since service + 0.1*inspection + 0.05*forecast warning."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import AnomalyRecord, InspectionRecord, Machine, MaintenanceRecord
from app.services import risk as risk_svc
from app.services.propagation import latest_prediction

LEVELS = [(0.75, "critical"), (0.5, "high"), (0.3, "medium"), (0.15, "low")]


def recommend(db: Session) -> list[dict]:
    thr, now, out = risk_svc.thresholds(db), utcnow(), []
    for m in db.query(Machine).filter(Machine.status != "offline").all():
        open_task = db.query(MaintenanceRecord).filter(MaintenanceRecord.machine_id == m.id, MaintenanceRecord.status.in_(["scheduled", "in_progress"])).first()
        p = latest_prediction(db, m.id)
        prob = p.probability if p else 0.0
        anom = db.query(func.count(AnomalyRecord.id)).filter(AnomalyRecord.machine_id == m.id, AnomalyRecord.timestamp >= now - timedelta(hours=24)).scalar() or 0
        last_done = db.query(func.max(MaintenanceRecord.completed_at)).filter(MaintenanceRecord.machine_id == m.id, MaintenanceRecord.status == "completed").scalar()
        days = (now - last_done).days if last_done else 90
        insp = db.query(InspectionRecord).filter(InspectionRecord.machine_id == m.id).order_by(InspectionRecord.inspected_at.desc()).first()
        isc = {"pass": 0, "conditional": 1, "fail": 2}.get(insp.status, 0) if insp else 0
        score = 0.5 * min(prob / thr["critical"], 1) + 0.2 * min(anom / 20, 1) + 0.15 * min(days / 60, 1) + 0.1 * isc / 2
        reasons = []
        if prob >= thr["moderate"]: reasons.append(f"Current accident-risk estimate {prob:.0%} ({p.category if p else '-'})")
        if anom: reasons.append(f"{anom} anomalies in the last 24 h")
        if days >= 30: reasons.append(f"{days} days since last completed maintenance")
        if isc: reasons.append(f"Latest inspection: {insp.status}")
        level = next((n for t, n in LEVELS if score >= t), None)
        if not level or not reasons or open_task:
            continue
        out.append({"machine_id": m.id, "machine_code": m.code, "machine_name": m.name, "priority": level, "score": round(score, 3), "reasons": reasons,
                    "suggested_title": f"Preventive inspection of {m.name}", "suggested_due_days": {"critical": 0, "high": 1, "medium": 7, "low": 14}[level]})
    return sorted(out, key=lambda r: -r["score"])


def effectiveness(db: Session, rec: MaintenanceRecord) -> dict | None:
    if rec.status != "completed" or not rec.completed_at:
        return None
    from app.models import RiskPrediction
    after = db.query(func.avg(RiskPrediction.probability), func.count(RiskPrediction.id)).filter(
        RiskPrediction.machine_id == rec.machine_id, RiskPrediction.timestamp > rec.completed_at, RiskPrediction.timestamp <= rec.completed_at + timedelta(hours=6)).one()
    if rec.risk_before is None or not after[1]:
        return None
    return {"risk_before": round(rec.risk_before, 4), "risk_after": round(float(after[0]), 4), "samples_after": after[1],
            "change_pct": round((float(after[0]) - rec.risk_before) / max(rec.risk_before, 1e-6) * 100, 1),
            "note": "Before/after comparison of model risk estimates (6h windows); does not prove the task caused the change."}
