"""Report data builders. Every report is generated from live DB records."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import AnomalyRecord, Incident, Machine, MaintenanceRecord, RiskPrediction, User
from app.services import dashboard as dash
from app.services.common import iso

TITLES = {"daily_safety": "Daily Safety Report", "weekly_risk": "Weekly Industrial Risk Report", "monthly_incident": "Monthly Incident Report", "machine_health": "Machine Health Report",
          "maintenance": "Maintenance Report", "anomaly_detection": "Anomaly Detection Report", "ai_prediction": "AI Prediction Report", "emergency_response": "Emergency Response Report"}
DEFAULT_DAYS = {"daily_safety": 1, "weekly_risk": 7, "monthly_incident": 30, "machine_health": 1, "maintenance": 30, "anomaly_detection": 7, "ai_prediction": 7, "emergency_response": 30}


def build(db: Session, rtype: str, facility_id: int | None = None, days: int | None = None, incident_id: int | None = None) -> dict:
    days = days or DEFAULT_DAYS[rtype]
    since = utcnow() - timedelta(days=days)
    machines = dash.scoped_machines(db, facility_id)
    ids = [m.id for m in machines]
    mm = {m.id: m for m in machines}
    summary: list[tuple[str, object]] = [("Period", f"last {days} day(s) to {iso(utcnow())}")]
    cols: list[str]; rows: list[list]
    if rtype in ("daily_safety", "weekly_risk", "machine_health"):
        ov = dash.overview(db, facility_id, hours=days * 24)
        preds = dash.latest_pred_map(db, ids)
        summary += [("Safety score (heuristic)", ov["safety_score"]), ("Machines", ov["totals"]["machines"]), ("Active hazards (High/Critical now)", ov["active_hazards"]),
                    ("Anomalies in period", ov["anomalies_in_window"]), ("Maintenance overdue", ov["maintenance_alerts"]["overdue"]), ("Near-miss reports", ov["near_miss_reports"])]
        cols = ["Machine", "Name", "Department", "Status", "Current risk", "Category", "Avg risk (period)", "Max risk (period)", "Anomalies", "Op. hours", "Age (y)"]
        rows = []
        for m in machines:
            a = db.query(func.avg(RiskPrediction.probability), func.max(RiskPrediction.probability)).filter(RiskPrediction.machine_id == m.id, RiskPrediction.timestamp >= since).one()
            n = db.query(func.count(AnomalyRecord.id)).filter(AnomalyRecord.machine_id == m.id, AnomalyRecord.timestamp >= since).scalar()
            p = preds.get(m.id)
            rows.append([m.code, m.name, m.department.name if m.department else "", m.status, round(p.probability, 4) if p else "", p.category if p else "", round(a[0] or 0, 4), round(a[1] or 0, 4), n, round(m.operating_hours, 1), round(m.age_years, 1)])
    elif rtype in ("monthly_incident", "emergency_response"):
        q = db.query(Incident).filter(Incident.occurred_at >= since)
        if incident_id: q = db.query(Incident).filter(Incident.id == incident_id)
        incs = q.order_by(Incident.occurred_at.desc()).all()
        summary += [("Incidents", len(incs)), ("Open/responding", sum(i.status in ("open", "responding") for i in incs)), ("Critical/High", sum(i.severity in ("critical", "high") for i in incs))]
        users = {u.id: u.full_name for u in db.query(User)}
        cols = ["ID", "Occurred", "Title", "Type", "Severity", "Status", "Machine", "Team", "Reported by", "Resolved", "Resolution"]
        rows = [[i.id, iso(i.occurred_at), i.title, i.incident_type, i.severity, i.status, db.get(Machine, i.machine_id).code if i.machine_id else "", i.assigned_team, users.get(i.reported_by_id, ""), iso(i.resolved_at) or "", i.resolution] for i in incs]
    elif rtype == "maintenance":
        recs = db.query(MaintenanceRecord).filter(MaintenanceRecord.machine_id.in_(ids), MaintenanceRecord.created_at >= since).order_by(MaintenanceRecord.due_date).all()
        users = {u.id: u.full_name for u in db.query(User)}
        now = utcnow()
        summary += [("Tasks", len(recs)), ("Completed", sum(r.status == "completed" for r in recs)), ("Overdue", sum(bool(r.status in ("scheduled", "in_progress") and r.due_date and r.due_date < now) for r in recs))]
        cols = ["ID", "Machine", "Title", "Type", "Priority", "Status", "Due", "Assigned to", "Completed", "Overdue"]
        rows = [[r.id, mm[r.machine_id].code if r.machine_id in mm else "", r.title, r.maint_type, r.priority, r.status, iso(r.due_date) or "", users.get(r.assigned_to_id, ""), iso(r.completed_at) or "",
                 "yes" if r.status in ("scheduled", "in_progress") and r.due_date and r.due_date < now else "no"] for r in recs]
    elif rtype == "anomaly_detection":
        recs = db.query(AnomalyRecord).filter(AnomalyRecord.machine_id.in_(ids), AnomalyRecord.timestamp >= since).order_by(AnomalyRecord.timestamp.desc()).limit(5000).all()
        summary += [("Anomalies", len(recs)), ("Critical", sum(r.severity == "critical" for r in recs)), ("High", sum(r.severity == "high" for r in recs))]
        cols = ["Time", "Machine", "Parameter", "Observed", "Expected low", "Expected high", "Score", "Severity", "Acknowledged"]
        rows = [[iso(r.timestamp), mm[r.machine_id].code, r.parameter, r.observed_value, r.expected_low, r.expected_high, r.score, r.severity, r.acknowledged] for r in recs]
    else:  # ai_prediction
        thr = dash.risk_svc.thresholds(db)
        recs = db.query(RiskPrediction).filter(RiskPrediction.machine_id.in_(ids), RiskPrediction.timestamp >= since, RiskPrediction.probability >= thr["moderate"]).order_by(RiskPrediction.timestamp.desc()).limit(5000).all()
        total = db.query(func.count(RiskPrediction.id)).filter(RiskPrediction.machine_id.in_(ids), RiskPrediction.timestamp >= since).scalar()
        summary += [("Predictions in period", total), ("Listed (>= Moderate, max 5000)", len(recs)), ("Thresholds in force", str(thr)), ("Note", "Model output on simulated/synthetic-trained model; decision support only")]
        cols = ["Time", "Machine", "Probability", "Category", "Priority", "Model version", "Data quality", "Warnings"]
        rows = [[iso(r.timestamp), mm[r.machine_id].code, r.probability, r.category, r.priority, r.model_version, (r.data_quality or {}).get("status", ""), "; ".join((r.data_quality or {}).get("warnings", []))] for r in recs]
    return {"title": TITLES[rtype], "summary": summary, "columns": cols, "rows": rows}
