from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from app.api.deps import DB
from app.api.machines import visible_machines
from app.core.db import utcnow
from app.core.security import get_current_user
from app.models import Incident, Machine, Notification
from app.services import dashboard as dash
from app.services.common import iso

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _allowed(db, user):
    return [m.id for m in visible_machines(db, user).all()] if user.role == "maintenance_engineer" else None


@router.get("/overview")
def overview(db: DB, user=Depends(get_current_user), facility_id: int | None = None, department_id: int | None = None, machine_id: int | None = None, hours: int = Query(24, ge=1, le=720)):
    return dash.overview(db, facility_id, department_id, machine_id, hours, _allowed(db, user))


@router.get("/risk-trends")
def trends(db: DB, user=Depends(get_current_user), facility_id: int | None = None, machine_id: int | None = None, hours: int = Query(24, ge=1, le=720), group_by: str = Query("fleet", pattern="^(fleet|department|machine)$")):
    return dash.risk_trends(db, facility_id, hours, group_by, machine_id, _allowed(db, user))


@router.get("/incident-trends")
def incident_trends(db: DB, user=Depends(get_current_user), days: int = Query(30, ge=7, le=180)):
    return dash.incident_trends(db, days)


@router.get("/recent-alerts")
def recent_alerts(db: DB, user=Depends(get_current_user), limit: int = Query(20, ge=1, le=100)):
    codes = {m.id: m.code for m in db.query(Machine.id, Machine.code)}
    items = [{"type": n.kind, "level": n.level, "title": n.title, "message": n.message, "timestamp": iso(n.created_at), "machine_code": codes.get(n.machine_id)}
             for n in db.query(Notification).filter((Notification.user_id.is_(None)) | (Notification.user_id == user.id)).order_by(Notification.created_at.desc()).limit(limit)]
    for i in db.query(Incident).filter(Incident.created_at >= utcnow() - timedelta(days=7)).order_by(Incident.created_at.desc()).limit(10):
        items.append({"type": "incident", "level": "critical" if i.severity in ("critical", "high") else "warning", "title": f"Incident: {i.title}", "message": f"{i.incident_type} - {i.status}",
                      "timestamp": iso(i.created_at), "machine_code": codes.get(i.machine_id)})
    return sorted(items, key=lambda d: d["timestamp"], reverse=True)[:limit]
