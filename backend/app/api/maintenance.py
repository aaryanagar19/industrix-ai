from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import DB, Pagination, get_machine_or_404
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.models import InspectionRecord, Machine, MaintenanceRecord, RiskPrediction, User
from app.schemas.ops import InspectionIn, MaintenanceIn, MaintenancePatch
from app.services import risk as risk_svc
from app.services.common import audit, iso, notify
from app.services.maintenance_recs import effectiveness, recommend

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])
MGR = require_roles("safety_manager", "plant_manager")


def mdict(db: Session, r: MaintenanceRecord, machines: dict, users: dict) -> dict:
    now = utcnow()
    m = machines.get(r.machine_id)
    return {"id": r.id, "machine_id": r.machine_id, "machine_code": m.code if m else None, "machine_name": m.name if m else None, "title": r.title, "description": r.description,
            "maint_type": r.maint_type, "priority": r.priority, "status": r.status, "source": r.source, "due_date": iso(r.due_date), "assigned_to_id": r.assigned_to_id,
            "assigned_to": users.get(r.assigned_to_id), "created_by": users.get(r.created_by_id), "completed_at": iso(r.completed_at), "completion_notes": r.completion_notes,
            "is_overdue": bool(r.status in ("scheduled", "in_progress") and r.due_date and r.due_date < now), "created_at": iso(r.created_at),
            "effectiveness": effectiveness(db, r) if r.status == "completed" else None}


def _maps(db):
    return {m.id: m for m in db.query(Machine).all()}, {u.id: u.full_name for u in db.query(User).all()}


@router.get("")
def list_tasks(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), status: str | None = None, priority: str | None = None, machine_id: int | None = None,
               overdue: bool | None = None, assigned_to_me: bool = False, q: str | None = Query(None, max_length=60)):
    qr = db.query(MaintenanceRecord)
    if user.role == "maintenance_engineer" or assigned_to_me:
        qr = qr.filter(MaintenanceRecord.assigned_to_id == user.id)
    if status: qr = qr.filter(MaintenanceRecord.status == status)
    if priority: qr = qr.filter(MaintenanceRecord.priority == priority)
    if machine_id: qr = qr.filter(MaintenanceRecord.machine_id == machine_id)
    if overdue: qr = qr.filter(MaintenanceRecord.status.in_(["scheduled", "in_progress"]), MaintenanceRecord.due_date < utcnow())
    if q: qr = qr.filter(MaintenanceRecord.title.ilike(f"%{q}%"))
    total = qr.count()
    rows = qr.order_by(MaintenanceRecord.due_date.is_(None), MaintenanceRecord.due_date).offset(p.offset).limit(p.page_size).all()
    machines, users = _maps(db)
    return {"items": [mdict(db, r, machines, users) for r in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.get("/recommendations")
def recommendations(db: DB, user=Depends(MGR)):
    return {"items": recommend(db), "method": "Heuristic score: 0.5 x risk + 0.2 x anomalies(24h) + 0.15 x days since service + 0.1 x inspection. Review before scheduling."}


@router.get("/summary")
def summary(db: DB, user=Depends(get_current_user)):
    now = utcnow()
    c = lambda *f: db.query(func.count(MaintenanceRecord.id)).filter(*f).scalar()
    return {"scheduled": c(MaintenanceRecord.status == "scheduled"), "in_progress": c(MaintenanceRecord.status == "in_progress"), "completed": c(MaintenanceRecord.status == "completed"),
            "overdue": c(MaintenanceRecord.status.in_(["scheduled", "in_progress"]), MaintenanceRecord.due_date < now)}


@router.post("", status_code=201)
def create_task(body: MaintenanceIn, db: DB, user=Depends(MGR)):
    m = get_machine_or_404(db, body.machine_id)
    if body.assigned_to_id and not db.get(User, body.assigned_to_id):
        raise HTTPException(422, "Assigned user does not exist")
    r = MaintenanceRecord(**body.model_dump(), created_by_id=user.id)
    db.add(r); db.commit()
    risk_svc.clear_context_cache(m.id)
    if r.assigned_to_id:
        notify(db, f"Maintenance assigned: {r.title}", f"{m.code} - priority {r.priority}", "info", "maintenance", m.id, user_id=r.assigned_to_id)
    audit(db, user, "create_maintenance", "maintenance", r.id, {"machine": m.code})
    machines, users = _maps(db)
    return mdict(db, r, machines, users)


@router.patch("/{task_id}")
def update_task(task_id: int, body: MaintenancePatch, db: DB, user=Depends(require_roles("safety_manager", "plant_manager", "maintenance_engineer"))):
    r = db.get(MaintenanceRecord, task_id)
    if not r:
        raise HTTPException(404, "Task not found")
    data = body.model_dump(exclude_unset=True)
    if user.role == "maintenance_engineer":
        if r.assigned_to_id != user.id:
            raise HTTPException(403, "You can only update tasks assigned to you")
        data = {k: v for k, v in data.items() if k in ("status", "completion_notes")}
    if data.get("status") == "completed" and r.status != "completed":
        r.completed_at = utcnow()
        from datetime import timedelta
        r.risk_before = db.query(func.avg(RiskPrediction.probability)).filter(RiskPrediction.machine_id == r.machine_id, RiskPrediction.timestamp >= utcnow() - timedelta(hours=6)).scalar()
        m = db.get(Machine, r.machine_id)
        if m:
            m.last_inspection_at = utcnow() if r.maint_type == "inspection" else m.last_inspection_at
    if data.get("assigned_to_id") and not db.get(User, data["assigned_to_id"]):
        raise HTTPException(422, "Assigned user does not exist")
    for k, v in data.items():
        setattr(r, k, v)
    db.commit()
    risk_svc.clear_context_cache(r.machine_id)
    audit(db, user, "update_maintenance", "maintenance", r.id, data)
    machines, users = _maps(db)
    return mdict(db, r, machines, users)


@router.get("/inspections")
def list_inspections(db: DB, user=Depends(get_current_user), machine_id: int | None = None, limit: int = Query(50, le=200)):
    q = db.query(InspectionRecord)
    if machine_id: q = q.filter(InspectionRecord.machine_id == machine_id)
    codes = {m.id: m.code for m in db.query(Machine.id, Machine.code)}
    return [{"id": i.id, "machine_id": i.machine_id, "machine_code": codes.get(i.machine_id), "status": i.status, "notes": i.notes, "inspected_at": iso(i.inspected_at)}
            for i in q.order_by(InspectionRecord.inspected_at.desc()).limit(limit)]


@router.post("/inspections", status_code=201)
def create_inspection(body: InspectionIn, db: DB, user=Depends(require_roles("safety_manager", "safety_officer", "maintenance_engineer", "plant_manager"))):
    m = get_machine_or_404(db, body.machine_id)
    i = InspectionRecord(machine_id=m.id, inspector_id=user.id, status=body.status, notes=body.notes)
    m.last_inspection_at = utcnow()
    db.add(i); db.commit()
    risk_svc.clear_context_cache(m.id)
    audit(db, user, "create_inspection", "machine", m.id, {"status": body.status})
    return {"id": i.id, "status": i.status, "inspected_at": iso(i.inspected_at)}
