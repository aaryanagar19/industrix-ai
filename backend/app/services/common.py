from datetime import datetime

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import AuditLog, Notification, SystemSetting


def iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


def audit(db: Session, user, action: str, entity: str = "", entity_id="", detail: dict | None = None):
    db.add(AuditLog(user_id=getattr(user, "id", None), action=action, entity=entity, entity_id=str(entity_id), detail=detail or {}))
    db.commit()


def get_setting(db: Session, key: str, default: dict | None = None) -> dict:
    row = db.get(SystemSetting, key)
    return row.value if row else (default or {})


def set_setting(db: Session, key: str, value: dict):
    row = db.get(SystemSetting, key)
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def notify(db: Session, title: str, message: str, level: str = "info", kind: str = "system", machine_id: int | None = None,
           user_id: int | None = None, cooldown_s: int = 0) -> Notification | None:
    if cooldown_s:
        from datetime import timedelta
        recent = db.query(Notification.id).filter(Notification.kind == kind, Notification.machine_id == machine_id, Notification.level == level,
                                                   Notification.title == title, Notification.created_at > utcnow() - timedelta(seconds=cooldown_s)).first()
        if recent:
            return None
    n = Notification(title=title, message=message, level=level, kind=kind, machine_id=machine_id, user_id=user_id)
    db.add(n)
    db.commit()
    return n


def notif_dict(n: Notification) -> dict:
    return {"id": n.id, "title": n.title, "message": n.message, "level": n.level, "kind": n.kind, "machine_id": n.machine_id,
            "is_read": n.is_read, "created_at": iso(n.created_at)}
