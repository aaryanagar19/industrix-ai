import io
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import DB, Pagination
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.security import get_current_user, require_roles
from app.ml.nlp.pipeline import analyze_text
from app.models import Document, Machine, NlpResult
from app.schemas.ops import TextDocIn
from app.services.common import audit, iso

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()
ALLOWED = {".txt", ".md", ".log", ".csv", ".pdf"}
DOC_TYPES = {"maintenance_log", "inspection_report", "incident_description", "near_miss_report", "equipment_complaint"}
WRITERS = require_roles("safety_manager", "safety_officer", "maintenance_engineer", "plant_manager")


def _extract(name: str, raw: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        if not raw.startswith(b"%PDF"):
            raise HTTPException(415, "File content is not a valid PDF")
        from pypdf import PdfReader
        try:
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            raise HTTPException(422, "Could not read PDF text")
    if b"\x00" in raw[:2048]:
        raise HTTPException(415, "Binary content is not accepted for text file types")
    return raw.decode("utf-8", errors="replace")


def _analyze(db, doc: Document) -> NlpResult:
    machines = [{"code": m.code, "name": m.name} for m in db.query(Machine)]
    res = analyze_text(doc.text_content, machines)
    row = db.query(NlpResult).filter(NlpResult.document_id == doc.id).first()
    if row: row.result = res
    else:
        row = NlpResult(document_id=doc.id, result=res); db.add(row)
    db.commit()
    return row


def ddict(d: Document, r: NlpResult | None = None) -> dict:
    out = {"id": d.id, "filename": d.filename, "doc_type": d.doc_type, "size_bytes": d.size_bytes, "uploaded_at": iso(d.uploaded_at), "preview": d.text_content[:200]}
    if r:
        out["urgency"], out["incident_type"] = r.result.get("urgency"), r.result.get("incident_type")
    return out


@router.post("/upload", status_code=201)
async def upload(db: DB, file: UploadFile = File(...), doc_type: str = Form("maintenance_log"), user=Depends(WRITERS)):
    name = re.sub(r"[^A-Za-z0-9._\- ]", "_", Path(file.filename or "upload").name)[:120]
    if Path(name).suffix.lower() not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED))}")
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, "Invalid doc_type")
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    text = _extract(name, raw).strip()[:60000]
    if len(text) < 10:
        raise HTTPException(422, "No readable text found in file")
    doc = Document(filename=name, doc_type=doc_type, content_type=file.content_type or "", size_bytes=len(raw), text_content=text, uploaded_by_id=user.id)
    db.add(doc); db.commit()
    r = _analyze(db, doc)
    audit(db, user, "upload_document", "document", doc.id, {"name": name})
    return {**ddict(doc, r), "analysis": r.result}


@router.post("/text", status_code=201)
def from_text(body: TextDocIn, db: DB, user=Depends(WRITERS)):
    doc = Document(filename=body.title, doc_type=body.doc_type, content_type="text/plain", size_bytes=len(body.text.encode()), text_content=body.text, uploaded_by_id=user.id)
    db.add(doc); db.commit()
    r = _analyze(db, doc)
    audit(db, user, "create_document_text", "document", doc.id)
    return {**ddict(doc, r), "analysis": r.result}


@router.get("")
def list_docs(db: DB, user=Depends(get_current_user), p: Pagination = Depends()):
    q = db.query(Document)
    total = q.count()
    rows = q.order_by(Document.uploaded_at.desc()).offset(p.offset).limit(p.page_size).all()
    res = {r.document_id: r for r in db.query(NlpResult).filter(NlpResult.document_id.in_([d.id for d in rows]))}
    return {"items": [ddict(d, res.get(d.id)) for d in rows], "total": total, "page": p.page, "page_size": p.page_size}


@router.get("/{doc_id}/analysis")
def analysis(doc_id: int, db: DB, user=Depends(get_current_user)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    r = db.query(NlpResult).filter(NlpResult.document_id == d.id).first() or _analyze(db, d)
    return {"document": ddict(d), "text": d.text_content, "analysis": r.result}


@router.get("/{doc_id}/report")
def report(doc_id: int, db: DB, user=Depends(get_current_user)):
    from app.reports.render import write_pdf
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    r = db.query(NlpResult).filter(NlpResult.document_id == d.id).first() or _analyze(db, d)
    a = r.result
    rep = {"title": f"NLP Analysis - {d.filename}", "summary": [("Document type", d.doc_type), ("Incident type", f"{a['incident_type']} ({a['classification_method']}, conf {a['classifier_confidence']})"), ("Urgency", a["urgency"]),
           ("Machines", ", ".join(a["machines"]["codes"]) or "-"), ("Hazards", ", ".join(a["hazards"]) or "-"), ("Issues", ", ".join(a["issues"]) or "-"), ("Measurements", ", ".join(a["measurements"]) or "-"),
           ("Keywords", ", ".join(a["keywords"])), ("Summary", a["summary"]), ("Disclaimer", a["disclaimer"])], "columns": ["Follow-up action (extracted sentence)"], "rows": [[s] for s in a["follow_up_actions"]]}
    out = Path(settings.storage_dir) / "reports"; out.mkdir(parents=True, exist_ok=True)
    path = out / f"nlp_{d.id}.pdf"
    write_pdf(path, rep)
    return FileResponse(path, media_type="application/pdf", filename=f"nlp_analysis_{d.id}.pdf")
