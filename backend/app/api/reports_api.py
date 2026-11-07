from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import DB, Pagination
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.models import Report
from app.reports import builders, render
from app.schemas.ops import ReportIn
from app.services.common import audit, iso

router = APIRouter(prefix="/api/reports", tags=["reports"])
GEN = require_roles("safety_manager", "plant_manager", "safety_officer")


def rdict(r: Report) -> dict:
    return {"id": r.id, "report_type": r.report_type, "title": builders.TITLES.get(r.report_type, r.report_type), "format": r.fmt, "params": r.params, "row_count": r.row_count, "created_at": iso(r.created_at)}


@router.get("")
def list_reports(db: DB, user=Depends(get_current_user), p: Pagination = Depends()):
    q = db.query(Report)
    return {"items": [rdict(r) for r in q.order_by(Report.created_at.desc()).offset(p.offset).limit(p.page_size)], "total": q.count(), "types": builders.TITLES}


@router.post("/generate", status_code=201)
def generate(body: ReportIn, db: DB, user=Depends(GEN)):
    rep = builders.build(db, body.report_type, body.facility_id, body.days, body.incident_id)
    d = Path(get_settings().storage_dir) / "reports"; d.mkdir(parents=True, exist_ok=True)
    path = d / f"{body.report_type}_{utcnow():%Y%m%d%H%M%S%f}.{body.format}"
    (render.write_pdf if body.format == "pdf" else render.write_csv)(path, rep)
    r = Report(report_type=body.report_type, fmt=body.format, params=body.model_dump(exclude={"report_type", "format"}), file_path=str(path), row_count=len(rep["rows"]), created_by_id=user.id)
    db.add(r); db.commit()
    audit(db, user, "generate_report", "report", r.id, {"type": body.report_type})
    return rdict(r)


@router.get("/{report_id}/download")
def download(report_id: int, db: DB, user=Depends(get_current_user)):
    r = db.get(Report, report_id)
    if not r or not Path(r.file_path).exists():
        raise HTTPException(404, "Report file not found")
    return FileResponse(r.file_path, media_type="application/pdf" if r.fmt == "pdf" else "text/csv", filename=f"{r.report_type}_{r.id}.{r.fmt}")
