from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import DB, Pagination
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.models import Department, EmergencyAction, Incident, Machine, RiskPrediction, SensorReading, User
from app.reports.render import write_incident_pdf
from app.schemas.ops import ActionIn, ActionPatch, IncidentIn, IncidentPatch
from app.services import risk as risk_svc
from app.services.common import audit, get_setting, iso, notify, set_setting

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
WRITE = require_roles("safety_manager", "safety_officer")

DEFAULT_PROCEDURES = {
    "fire_overheat": ["Follow the site fire emergency procedure and raise the alarm", "Notify the on-duty safety officer and emergency services per site procedure", "Isolate equipment only if authorised and safe to do so", "Account for personnel at the assembly point"],
    "leak_spill": ["Secure and cordon the area", "Notify the safety officer and follow the site spill-response procedure", "Prevent ignition sources near the release", "Record material, quantity and containment actions"],
    "electrical": ["Do not approach the equipment; follow the site electrical-safety procedure", "Notify the authorised electrical lead", "Record lock-out/tag-out status", "Arrange first aid if anyone is affected"],
    "personal_injury": ["Provide first aid via trained first-aiders", "Contact medical/emergency services as required", "Preserve the scene for investigation", "Notify the safety manager"],
    "equipment_failure": ["Notify the shift supervisor and maintenance lead", "Confirm equipment is in a safe state per site procedure", "Create a corrective maintenance task", "Record downtime and conditions"],
    "near_miss": ["Record who/what/where and contributing conditions", "Review guarding and procedures with the safety officer", "Schedule a follow-up inspection"],
    "other": ["Notify the safety officer", "Record observations", "Follow approved site procedures"],
}


def idict(db, i: Incident) -> dict:
    m = db.get(Machine, i.machine_id) if i.machine_id else None
    return {"id": i.id, "title": i.title, "description": i.description, "incident_type": i.incident_type, "severity": i.severity, "status": i.status, "machine_id": i.machine_id,
            "machine_code": m.code if m else None, "department_id": i.department_id, "assigned_team": i.assigned_team, "occurred_at": iso(i.occurred_at), "resolved_at": iso(i.resolved_at),
            "resolution": i.resolution, "created_at": iso(i.created_at)}


def adict(db, a: EmergencyAction) -> dict:
    u = db.get(User, a.performed_by_id) if a.performed_by_id else None
    return {"id": a.id, "incident_id": a.incident_id, "category": a.category, "action": a.action, "status": a.status, "performed_by": u.full_name if u else None,
            "performed_at": iso(a.performed_at), "created_at": iso(a.created_at)}


@router.get("")
def list_incidents(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), status: str | None = None, severity: str | None = None, machine_id: int | None = None,
                   incident_type: str | None = None, q: str | None = Query(None, max_length=60)):
    qr = db.query(Incident)
    if status == "active": qr = qr.filter(Incident.status.in_(["open", "responding"]))
    elif status: qr = qr.filter(Incident.status == status)
    if severity: qr = qr.filter(Incident.severity == severity)
    if machine_id: qr = qr.filter(Incident.machine_id == machine_id)
    if incident_type: qr = qr.filter(Incident.incident_type == incident_type)
    if q: qr = qr.filter(Incident.title.ilike(f"%{q}%"))
    total = qr.count()
    rows = qr.order_by(Incident.occurred_at.desc()).offset(p.offset).limit(p.page_size).all()
    return {"items": [idict(db, i) for i in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.post("", status_code=201)
def create_incident(body: IncidentIn, db: DB, user=Depends(WRITE)):
    m = db.get(Machine, body.machine_id) if body.machine_id else None
    if body.machine_id and not m:
        raise HTTPException(422, "Machine not found")
    data = body.model_dump()
    inc = Incident(**data, facility_id=m.facility_id if m else None, reported_by_id=user.id)
    if not inc.occurred_at: inc.occurred_at = utcnow()
    if m and not inc.department_id: inc.department_id = m.department_id
    db.add(inc); db.commit()
    procs = get_setting(db, "emergency_procedures", DEFAULT_PROCEDURES)
    for step in procs.get(inc.incident_type, procs.get("other", [])):
        db.add(EmergencyAction(incident_id=inc.id, category="recommended", action=step, status="pending"))
    db.add(EmergencyAction(incident_id=inc.id, category="event", action=f"Incident created by {user.full_name} (severity {inc.severity})", status="done", performed_by_id=user.id, performed_at=utcnow()))
    db.commit()
    risk_svc.clear_context_cache(inc.machine_id)
    notify(db, f"Incident reported: {inc.title}", f"{inc.incident_type} / {inc.severity}", "critical" if inc.severity in ("high", "critical") else "warning", "incident", inc.machine_id)
    audit(db, user, "create_incident", "incident", inc.id)
    return idict(db, inc)


@router.get("/procedures")
def procedures(db: DB, user=Depends(get_current_user)):
    return {"procedures": get_setting(db, "emergency_procedures", DEFAULT_PROCEDURES), "notice": "Templates must be aligned with approved facility procedures and reviewed by authorised safety personnel."}


@router.put("/procedures")
def put_procedures(body: dict, db: DB, user=Depends(require_roles("safety_manager"))):
    if not all(isinstance(v, list) and all(isinstance(s, str) for s in v) for v in body.values()):
        raise HTTPException(422, "Expected {incident_type: [step, ...]}")
    set_setting(db, "emergency_procedures", body)
    audit(db, user, "update_procedures", "settings", "emergency_procedures")
    return {"procedures": body}


@router.get("/{incident_id}")
def get_incident(incident_id: int, db: DB, user=Depends(get_current_user)):
    i = db.get(Incident, incident_id)
    if not i:
        raise HTTPException(404, "Incident not found")
    acts = db.query(EmergencyAction).filter(EmergencyAction.incident_id == i.id).order_by(EmergencyAction.created_at, EmergencyAction.id).all()
    return {**idict(db, i), "actions": [adict(db, a) for a in acts],
            "notice": "Recommended actions are templates for review by authorised safety personnel. This system does not replace emergency services or official procedures."}


@router.patch("/{incident_id}")
def patch_incident(incident_id: int, body: IncidentPatch, db: DB, user=Depends(WRITE)):
    i = db.get(Incident, incident_id)
    if not i:
        raise HTTPException(404, "Incident not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("status") in ("resolved", "closed") and not (data.get("resolution") or i.resolution):
        raise HTTPException(422, "A resolution description is required to resolve or close an incident")
    old = i.status
    for k, v in data.items():
        setattr(i, k, v)
    if data.get("status") in ("resolved", "closed") and not i.resolved_at:
        i.resolved_at = utcnow()
    if data.get("status") and data["status"] != old:
        db.add(EmergencyAction(incident_id=i.id, category="event", action=f"Status changed {old} -> {i.status} by {user.full_name}", status="done", performed_by_id=user.id, performed_at=utcnow()))
    db.commit()
    audit(db, user, "update_incident", "incident", i.id, data)
    return idict(db, i)


@router.post("/{incident_id}/actions", status_code=201)
def add_action(incident_id: int, body: ActionIn, db: DB, user=Depends(WRITE)):
    if not db.get(Incident, incident_id):
        raise HTTPException(404, "Incident not found")
    a = EmergencyAction(incident_id=incident_id, category=body.category, action=body.action, status=body.status, performed_by_id=user.id if body.status == "done" else None,
                        performed_at=utcnow() if body.status == "done" else None)
    db.add(a); db.commit()
    audit(db, user, "add_action", "incident", incident_id)
    return adict(db, a)


@router.patch("/{incident_id}/actions/{action_id}")
def patch_action(incident_id: int, action_id: int, body: ActionPatch, db: DB, user=Depends(WRITE)):
    a = db.get(EmergencyAction, action_id)
    if not a or a.incident_id != incident_id:
        raise HTTPException(404, "Action not found")
    a.status = body.status
    a.performed_by_id, a.performed_at = (user.id, utcnow()) if body.status == "done" else (None, None)
    db.commit()
    audit(db, user, "update_action", "incident", incident_id, {"action": action_id, "status": body.status})
    return adict(db, a)


@router.get("/{incident_id}/report")
def incident_report(incident_id: int, db: DB, user=Depends(require_roles("safety_manager", "safety_officer", "plant_manager"))):
    i = db.get(Incident, incident_id)
    if not i:
        raise HTTPException(404, "Incident not found")
    m = db.get(Machine, i.machine_id) if i.machine_id else None
    dept = db.get(Department, i.department_id) if i.department_id else None
    lo, hi = i.occurred_at - timedelta(hours=2), i.occurred_at + timedelta(hours=2)
    sens = db.query(SensorReading).filter(SensorReading.machine_id == i.machine_id, SensorReading.timestamp >= lo, SensorReading.timestamp <= hi).order_by(SensorReading.timestamp).all() if m else []
    sens = sens[::max(len(sens) // 20, 1)]
    preds = db.query(RiskPrediction).filter(RiskPrediction.machine_id == i.machine_id, RiskPrediction.timestamp >= lo, RiskPrediction.timestamp <= hi).order_by(RiskPrediction.timestamp).all() if m else []
    preds = preds[::max(len(preds) // 15, 1)]
    acts = [adict(db, a) for a in db.query(EmergencyAction).filter(EmergencyAction.incident_id == i.id).order_by(EmergencyAction.created_at)]
    rb = db.get(User, i.reported_by_id) if i.reported_by_id else None
    data = {"incident": idict(db, i), "location": f"{dept.name if dept else '-'} / {m.zone if m else '-'}", "machine_line": f"{m.code} {m.name}" if m else "-", "reported_by": rb.full_name if rb else "-",
            "sensors": [{"timestamp": iso(s.timestamp), "temperature": s.temperature and round(s.temperature, 1), "vibration": s.vibration and round(s.vibration, 2), "pressure": s.pressure and round(s.pressure, 2),
                         "load_pct": s.load_pct and round(s.load_pct, 1)} for s in sens], "predictions": [{"timestamp": iso(p.timestamp), "probability": p.probability, "category": p.category} for p in preds], "actions": acts}
    d = Path(get_settings().storage_dir) / "reports"; d.mkdir(parents=True, exist_ok=True)
    path = d / f"incident_{i.id}_{utcnow():%Y%m%d%H%M%S}.pdf"
    write_incident_pdf(path, data)
    audit(db, user, "export_incident_report", "incident", i.id)
    return FileResponse(path, media_type="application/pdf", filename=f"incident_{i.id}_report.pdf")
