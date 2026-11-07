from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.api.deps import DB, Pagination
from app.api.machines import latest_by_machine, visible_machines
from app.core.security import decode_token, get_current_user, require_roles
from app.core.ws import manager
from app.models import AuditLog, Department, Document, Facility, Incident, Machine, MaintenanceRecord, Notification, RiskPrediction, User
from app.services import propagation
from app.services.common import iso, notif_dict

router = APIRouter(tags=["misc"])


# ---- notifications -------------------------------------------------------------------------------------
def _nq(db, user):
    return db.query(Notification).filter((Notification.user_id.is_(None)) | (Notification.user_id == user.id))


@router.get("/api/notifications")
def notifications(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), unread: bool = False, level: str | None = None):
    q = _nq(db, user)
    if unread: q = q.filter(Notification.is_read.is_(False))
    if level: q = q.filter(Notification.level == level)
    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).offset(p.offset).limit(p.page_size).all()
    return {"items": [notif_dict(n) for n in rows], "total": total, "unread": _nq(db, user).filter(Notification.is_read.is_(False)).count()}


@router.post("/api/notifications/{nid}/read")
def read_one(nid: int, db: DB, user=Depends(get_current_user)):
    n = _nq(db, user).filter(Notification.id == nid).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True; db.commit()
    return notif_dict(n)


@router.post("/api/notifications/read-all")
def read_all(db: DB, user=Depends(get_current_user)):
    n = _nq(db, user).filter(Notification.is_read.is_(False)).update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"updated": n}


# ---- search ----------------------------------------------------------------------------------------------
@router.get("/api/search")
def search(db: DB, q: str = Query(..., min_length=2, max_length=60), user=Depends(get_current_user)):
    like = f"%{q}%"
    ms = visible_machines(db, user).filter((Machine.name.ilike(like)) | (Machine.code.ilike(like)) | (Machine.zone.ilike(like))).limit(8).all()
    inc = db.query(Incident).filter((Incident.title.ilike(like)) | (Incident.description.ilike(like))).limit(8).all()
    mt = db.query(MaintenanceRecord).filter(MaintenanceRecord.title.ilike(like)).limit(8).all()
    dc = db.query(Document).filter(Document.filename.ilike(like)).limit(8).all()
    return {"machines": [{"id": m.id, "code": m.code, "name": m.name} for m in ms], "incidents": [{"id": i.id, "title": i.title, "severity": i.severity} for i in inc],
            "maintenance": [{"id": t.id, "title": t.title, "status": t.status} for t in mt], "documents": [{"id": d.id, "filename": d.filename} for d in dc]}


# ---- risk propagation & digital twin ----------------------------------------------------------------------------
@router.get("/api/risk/propagation")
def propagation_map(db: DB, user=Depends(get_current_user), facility_id: int | None = None):
    f = db.get(Facility, facility_id) if facility_id else db.query(Facility).order_by(Facility.id).first()
    out = propagation.compute(db, facility_id)
    out["departments"] = [{"id": d.id, "name": d.name, "layout": d.layout} for d in f.departments] if f else []
    return out


@router.get("/api/twin")
def twin(db: DB, user=Depends(get_current_user), facility_id: int | None = None):
    f = db.get(Facility, facility_id) if facility_id else db.query(Facility).order_by(Facility.id).first()
    if not f:
        raise HTTPException(404, "No facility")
    prop = propagation.compute(db, f.id)
    return {"facility": {"id": f.id, "name": f.name}, "departments": [{"id": d.id, "name": d.name, "layout": d.layout} for d in f.departments], **prop,
            "note": "Operational visualisation and risk-monitoring view; not a physical process simulation."}


@router.get("/api/audit")
def audit_log(db: DB, user=Depends(require_roles()), p: Pagination = Depends()):
    q = db.query(AuditLog)
    users = {u.id: u.email for u in db.query(User)}
    rows = q.order_by(AuditLog.created_at.desc()).offset(p.offset).limit(p.page_size).all()
    return {"items": [{"id": a.id, "user": users.get(a.user_id), "action": a.action, "entity": a.entity, "entity_id": a.entity_id, "detail": a.detail, "created_at": iso(a.created_at)} for a in rows], "total": q.count()}


@router.get("/api/health")
def health(db: DB):
    from sqlalchemy import text
    from app.ml import registry
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "models": registry.available()}


# ---- websocket -------------------------------------------------------------------------------------------
@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, token: str = ""):
    if not decode_token(token):
        await ws.close(code=4401)
        return
    await manager.connect(ws)
    try:
        await ws.send_text('{"type":"hello","data":{"mode":"simulated"}}')
        while True:
            await ws.receive_text()  # keep-alive pings from client
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
