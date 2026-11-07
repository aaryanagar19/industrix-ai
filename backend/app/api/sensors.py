from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func

from app.api.deps import DB, Pagination, bucket_expr, get_machine_or_404, paginate
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.models import Machine, SensorReading
from app.schemas.ops import ReadingIn
from app.services.common import iso
from app.services.ingest import ingest_reading, reading_dict

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.get("/readings")
def list_readings(db: DB, user=Depends(get_current_user), p: Pagination = Depends(), machine_id: int | None = None, hours: int | None = Query(None, ge=1, le=720)):
    q = db.query(SensorReading)
    if machine_id: q = q.filter(SensorReading.machine_id == machine_id)
    if hours: q = q.filter(SensorReading.timestamp >= utcnow() - timedelta(hours=hours))
    rows, total = paginate(q.order_by(SensorReading.timestamp.desc()), p)
    return {"items": [reading_dict(r) for r in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.post("/readings", status_code=201)
def post_readings(body: ReadingIn | list[ReadingIn], db: DB, user=Depends(require_roles("plant_manager", "maintenance_engineer", "safety_manager"))):
    """Ingest one reading or a batch (max 500). Runs prediction + anomaly detection for each."""
    items = body if isinstance(body, list) else [body]
    if len(items) > 500:
        raise HTTPException(413, "Batch too large (max 500)")
    results = []
    for it in items:
        m = get_machine_or_404(db, it.machine_id)
        d = it.model_dump(exclude={"machine_id", "data_source"})
        if all(d.get(k) is None for k in ("temperature", "vibration", "pressure", "load_pct")):
            raise HTTPException(422, "At least one sensor value is required")
        ev = ingest_reading(db, m, d, it.data_source)
        results.append({"reading": ev["reading"], "prediction": ev["prediction"], "anomaly": ev["anomaly"]})
    return {"ingested": len(results), "results": results if len(results) <= 20 else results[:20]}


@router.get("/{machine_id}/history")
def history(machine_id: int, db: DB, user=Depends(get_current_user), hours: int = Query(6, ge=1, le=720), max_points: int = Query(300, ge=20, le=2000)):
    m = get_machine_or_404(db, machine_id)
    since = utcnow() - timedelta(hours=hours)
    bucket_s = max(int(hours * 3600 / max_points), 1)
    if bucket_s <= 3:  # raw
        rows = db.query(SensorReading).filter(SensorReading.machine_id == m.id, SensorReading.timestamp >= since).order_by(SensorReading.timestamp).limit(max_points * 3).all()
        pts = [reading_dict(r) for r in rows]
    else:
        b = bucket_expr(db, SensorReading.timestamp, bucket_s).label("b")
        q = db.query(func.min(SensorReading.timestamp), func.avg(SensorReading.temperature), func.avg(SensorReading.vibration), func.avg(SensorReading.pressure),
                     func.avg(SensorReading.load_pct), func.count(SensorReading.id)).filter(SensorReading.machine_id == m.id, SensorReading.timestamp >= since).group_by(b).order_by(func.min(SensorReading.timestamp))
        pts = [{"timestamp": iso(t), "temperature": a, "vibration": v, "pressure": pr, "load_pct": l, "n": n} for t, a, v, pr, l, n in q.all()]
    return {"machine_id": m.id, "machine_code": m.code, "hours": hours, "bucket_seconds": bucket_s if bucket_s > 3 else 0, "baseline": m.baseline, "points": pts}
