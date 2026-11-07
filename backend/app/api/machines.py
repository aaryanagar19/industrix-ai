from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_

from app.api.deps import DB, Pagination, get_machine_or_404, paginate
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.ml.common import baseline_for
from app.models import AnomalyRecord, Department, InspectionRecord, Machine, MachineDependency, MaintenanceRecord, RiskPrediction, SensorReading
from app.schemas.assets import MachineIn, MachineOut, MachinePatch
from app.services import risk as risk_svc
from app.services.common import audit, iso
from app.services.ingest import anomaly_dict, reading_dict

router = APIRouter(prefix="/api/machines", tags=["machines"])


def latest_by_machine(db, model, ids):
    if not ids:
        return {}
    sub = db.query(func.max(model.id)).filter(model.machine_id.in_(ids)).group_by(model.machine_id)
    return {r.machine_id: r for r in db.query(model).filter(model.id.in_(sub))}


def visible_machines(db, user):
    q = db.query(Machine)
    if user.role == "maintenance_engineer":
        task_ids = db.query(MaintenanceRecord.machine_id).filter(MaintenanceRecord.assigned_to_id == user.id)
        q = q.filter(or_(Machine.assigned_engineer_id == user.id, Machine.id.in_(task_ids)))
    return q


def machine_card(m: Machine, reading, pred, dept_name=None) -> dict:
    d = MachineOut.model_validate(m).model_dump(mode="json")
    d["department"] = dept_name
    d["latest_reading"] = reading_dict(reading, m) if reading else None
    d["risk"] = {"probability": pred.probability, "category": pred.category, "timestamp": iso(pred.timestamp), "model_version": pred.model_version} if pred else None
    return d


@router.get("")
def list_machines(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), facility_id: int | None = None, department_id: int | None = None,
                  status: str | None = None, q: str | None = Query(None, max_length=60), risk: str | None = None):
    query = visible_machines(db, user)
    if facility_id: query = query.filter(Machine.facility_id == facility_id)
    if department_id: query = query.filter(Machine.department_id == department_id)
    if status: query = query.filter(Machine.status == status)
    if q: query = query.filter(or_(Machine.name.ilike(f"%{q}%"), Machine.code.ilike(f"%{q}%"), Machine.zone.ilike(f"%{q}%")))
    query = query.order_by(Machine.code)
    if risk:  # filter by current category requires latest predictions -> filter after fetch
        rows = query.all()
        preds = latest_by_machine(db, RiskPrediction, [m.id for m in rows])
        rows = [m for m in rows if preds.get(m.id) and preds[m.id].category.lower() == risk.lower()]
        total, rows = len(rows), rows[p.offset:p.offset + p.page_size]
    else:
        rows, total = paginate(query, p)
    ids = [m.id for m in rows]
    readings, preds = latest_by_machine(db, SensorReading, ids), latest_by_machine(db, RiskPrediction, ids)
    depts = {d.id: d.name for d in db.query(Department).all()}
    return {"items": [machine_card(m, readings.get(m.id), preds.get(m.id), depts.get(m.department_id)) for m in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.post("", response_model=MachineOut, status_code=201)
def create_machine(body: MachineIn, db: DB, user=Depends(require_roles("plant_manager"))):
    if db.query(Machine).filter(Machine.code == body.code).first():
        raise HTTPException(409, "Machine code already exists")
    data = body.model_dump(exclude={"install_year"})
    data["baseline"] = body.baseline or baseline_for(body.machine_type)
    m = Machine(**data, install_date=datetime(body.install_year or utcnow().year, 1, 1))
    db.add(m); db.commit()
    audit(db, user, "create_machine", "machine", m.id, {"code": m.code})
    return m


@router.get("/{machine_id}")
def machine_detail(machine_id: int, db: DB, user=Depends(get_current_user)):
    m = get_machine_or_404(db, machine_id)
    r = latest_by_machine(db, SensorReading, [m.id]).get(m.id)
    p = latest_by_machine(db, RiskPrediction, [m.id]).get(m.id)
    card = machine_card(m, r, p, m.department.name if m.department else None)
    maint = db.query(MaintenanceRecord).filter(MaintenanceRecord.machine_id == m.id).order_by(MaintenanceRecord.created_at.desc()).limit(20).all()
    insp = db.query(InspectionRecord).filter(InspectionRecord.machine_id == m.id).order_by(InspectionRecord.inspected_at.desc()).limit(10).all()
    anoms = db.query(AnomalyRecord).filter(AnomalyRecord.machine_id == m.id).order_by(AnomalyRecord.timestamp.desc()).limit(10).all()
    deps = db.query(MachineDependency).filter((MachineDependency.source_id == m.id) | (MachineDependency.target_id == m.id)).all()
    codes = {x.id: x.code for x in db.query(Machine.id, Machine.code).all()}
    card.update({
        "maintenance_history": [{"id": x.id, "title": x.title, "status": x.status, "priority": x.priority, "due_date": iso(x.due_date), "completed_at": iso(x.completed_at)} for x in maint],
        "inspections": [{"id": x.id, "status": x.status, "notes": x.notes, "inspected_at": iso(x.inspected_at)} for x in insp],
        "recent_anomalies": [anomaly_dict(a, m) for a in anoms],
        "dependencies": [{"source": codes[d.source_id], "target": codes[d.target_id], "weight": d.weight, "relation": d.relation} for d in deps],
        "context": risk_svc.machine_context(db, m),
    })
    return card


@router.patch("/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: int, body: MachinePatch, db: DB, user=Depends(require_roles("plant_manager", "maintenance_engineer"))):
    m = get_machine_or_404(db, machine_id)
    data = body.model_dump(exclude_unset=True)
    if user.role == "maintenance_engineer":
        if m.assigned_engineer_id != user.id:
            raise HTTPException(403, "Only assigned machines can be updated")
        data = {k: v for k, v in data.items() if k in ("status", "operating_hours")}
    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    audit(db, user, "update_machine", "machine", m.id, data)
    return m


@router.delete("/{machine_id}", status_code=204)
def delete_machine(machine_id: int, db: DB, user=Depends(require_roles())):
    m = get_machine_or_404(db, machine_id)
    db.delete(m); db.commit()
    audit(db, user, "delete_machine", "machine", machine_id)
