from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import bucket_expr
from app.core.db import utcnow
from app.models import AnomalyRecord, Department, Facility, Incident, Machine, MaintenanceRecord, RiskPrediction
from app.services import risk as risk_svc
from app.services.common import iso


def latest_pred_map(db: Session, ids: list[int]) -> dict[int, RiskPrediction]:
    if not ids:
        return {}
    sub = db.query(func.max(RiskPrediction.id)).filter(RiskPrediction.machine_id.in_(ids)).group_by(RiskPrediction.machine_id)
    return {p.machine_id: p for p in db.query(RiskPrediction).filter(RiskPrediction.id.in_(sub))}


def scoped_machines(db: Session, facility_id=None, department_id=None, machine_id=None, allowed_ids: list[int] | None = None) -> list[Machine]:
    q = db.query(Machine)
    if facility_id: q = q.filter(Machine.facility_id == facility_id)
    if department_id: q = q.filter(Machine.department_id == department_id)
    if machine_id: q = q.filter(Machine.id == machine_id)
    if allowed_ids is not None: q = q.filter(Machine.id.in_(allowed_ids))
    return q.all()


def overdue_count(db: Session, ids: list[int]) -> int:
    return db.query(func.count(MaintenanceRecord.id)).filter(MaintenanceRecord.machine_id.in_(ids), MaintenanceRecord.status.in_(["scheduled", "in_progress"]),
                                                              MaintenanceRecord.due_date < utcnow()).scalar() or 0


def safety_score(preds: list, overdue: int, critical: int) -> float:
    """Heuristic 0-100: 100 - 100*mean(latest P) - 5*critical machines - 2*overdue tasks (documented, not a certified metric)."""
    mean_p = sum(p.probability for p in preds) / len(preds) if preds else 0
    return round(max(0.0, min(100.0, 100 - 100 * mean_p - 5 * critical - 2 * overdue)), 1)


def overview(db: Session, facility_id=None, department_id=None, machine_id=None, hours=24, allowed_ids=None) -> dict:
    machines = scoped_machines(db, facility_id, department_id, machine_id, allowed_ids)
    ids = [m.id for m in machines]
    since = utcnow() - timedelta(hours=hours)
    preds = latest_pred_map(db, ids)
    cats = defaultdict(int)
    for p in preds.values():
        cats[p.category] += 1
    critical_zones = sorted({(m.zone or (m.department.name if m.department else "-")) for m in machines if preds.get(m.id) and preds[m.id].category == "Critical"})
    hazards = [m for m in machines if preds.get(m.id) and preds[m.id].category in ("High", "Critical")]
    overdue = overdue_count(db, ids) if ids else 0
    open_critical = db.query(func.count(MaintenanceRecord.id)).filter(MaintenanceRecord.machine_id.in_(ids), MaintenanceRecord.status.in_(["scheduled", "in_progress"]),
                                                                      MaintenanceRecord.priority == "critical").scalar() if ids else 0
    n_high_preds = db.query(func.count(RiskPrediction.id)).filter(RiskPrediction.machine_id.in_(ids), RiskPrediction.timestamp >= since, RiskPrediction.category.in_(["High", "Critical"])).scalar() if ids else 0
    n_preds = db.query(func.count(RiskPrediction.id)).filter(RiskPrediction.machine_id.in_(ids), RiskPrediction.timestamp >= since).scalar() if ids else 0
    n_anom = db.query(func.count(AnomalyRecord.id)).filter(AnomalyRecord.machine_id.in_(ids), AnomalyRecord.timestamp >= since).scalar() if ids else 0
    near = db.query(func.count(Incident.id)).filter(Incident.incident_type == "near_miss", Incident.occurred_at >= since).scalar()
    open_inc = db.query(func.count(Incident.id)).filter(Incident.status.in_(["open", "responding"])).scalar()
    status = defaultdict(int)
    for m in machines:
        status[m.status] += 1
    dept = defaultdict(list)
    for m in machines:
        if preds.get(m.id):
            dept[m.department.name if m.department else "Unassigned"].append(preds[m.id].probability)
    return {
        "scope": {"facility_id": facility_id, "department_id": department_id, "machine_id": machine_id, "hours": hours},
        "generated_at": iso(utcnow()),
        "totals": {"facilities": db.query(func.count(Facility.id)).scalar(), "machines": len(machines), "machines_running": status.get("running", 0), "open_incidents": open_inc},
        "active_hazards": len(hazards), "critical_zones": critical_zones, "critical_zone_count": len(critical_zones),
        "accident_predictions": {"high_or_critical_in_window": n_high_preds, "total_in_window": n_preds, "machines_high_or_critical_now": len(hazards)},
        "anomalies_in_window": n_anom, "near_miss_reports": near,
        "maintenance_alerts": {"overdue": overdue, "open_critical": open_critical, "total": overdue + open_critical},
        "machine_status": dict(status), "risk_distribution": {c: cats.get(c, 0) for c in ("Low", "Moderate", "High", "Critical")},
        "safety_score": safety_score(list(preds.values()), overdue, cats.get("Critical", 0)),
        "safety_score_definition": "Heuristic: 100 - 100 x mean(latest accident probability) - 5 x critical machines - 2 x overdue maintenance tasks, clipped to 0-100.",
        "risk_by_department": sorted(({"department": k, "avg_risk": round(sum(v) / len(v), 4), "max_risk": round(max(v), 4), "machines": len(v)} for k, v in dept.items()), key=lambda d: -d["avg_risk"]),
        "hazard_machines": [{"id": m.id, "code": m.code, "name": m.name, "category": preds[m.id].category, "probability": preds[m.id].probability} for m in sorted(hazards, key=lambda m: -preds[m.id].probability)[:8]],
    }


def risk_trends(db: Session, facility_id=None, hours=24, group_by="fleet", machine_id=None, allowed_ids=None) -> dict:
    machines = scoped_machines(db, facility_id, None, machine_id, allowed_ids)
    ids = [m.id for m in machines]
    bucket = 300 if hours <= 6 else 900 if hours <= 24 else 7200 if hours <= 168 else 21600
    since = utcnow() - timedelta(hours=hours)
    b = bucket_expr(db, RiskPrediction.timestamp, bucket).label("b")
    cols = [func.min(RiskPrediction.timestamp), func.avg(RiskPrediction.probability), func.max(RiskPrediction.probability)]
    q = db.query(*cols, Machine.department_id if group_by == "department" else Machine.id if group_by == "machine" else func.count(RiskPrediction.id)).join(Machine, Machine.id == RiskPrediction.machine_id)
    q = q.filter(RiskPrediction.machine_id.in_(ids), RiskPrediction.timestamp >= since)
    if group_by == "department":
        q = q.group_by(b, Machine.department_id)
    elif group_by == "machine":
        q = q.group_by(b, Machine.id)
    else:
        q = q.group_by(b)
    rows = q.all()
    names = {d.id: d.name for d in db.query(Department).all()} if group_by == "department" else {m.id: m.code for m in machines}
    buckets = sorted({iso(r[0]) for r in rows})
    series: dict[str, dict] = {}
    for t, avg, mx, key in rows:
        name = names.get(key, "Fleet") if group_by != "fleet" else "Fleet"
        series.setdefault(name, {})[iso(t)] = {"avg": round(float(avg), 4), "max": round(float(mx), 4)}
    points = [{"timestamp": t, **{f"{name}": s.get(t, {}).get("avg") for name, s in series.items()}, **({"Fleet max": series["Fleet"].get(t, {}).get("max")} if group_by == "fleet" and "Fleet" in series else {})} for t in buckets]
    return {"hours": hours, "bucket_seconds": bucket, "group_by": group_by, "series_names": list(series), "points": points}


def incident_trends(db: Session, days: int = 30) -> list[dict]:
    since = utcnow() - timedelta(days=days)
    out: dict = {}
    for d, sev in db.query(Incident.occurred_at, Incident.severity).filter(Incident.occurred_at >= since):
        k = d.strftime("%Y-%m-%d")
        out.setdefault(k, {"date": k, "low": 0, "medium": 0, "high": 0, "critical": 0})[sev] += 1
    for i in range(days):
        k = (utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        out.setdefault(k, {"date": k, "low": 0, "medium": 0, "high": 0, "critical": 0})
    return sorted(out.values(), key=lambda d: d["date"])
