import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import ai, auth, dashboard, documents, facilities, incidents, machines, maintenance, misc, reports_api, sensors, simulator_api
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.ml import registry
from app.simulator.engine import simulator

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("industrix")


def sync_model_versions():
    """Register trained artifacts in the model_versions table (idempotent)."""
    from app.models import ModelVersion
    db = SessionLocal()
    try:
        for kind, name in (("risk", "accident-risk-xgboost"), ("anomaly", "isolation-forest"), ("forecast", "lstm-forecaster"), ("nlp", "nlp-classifier")):
            m = registry.metrics(kind)
            if not m or "version" not in m:
                continue
            if not db.query(ModelVersion).filter(ModelVersion.name == name, ModelVersion.version == m["version"]).first():
                db.query(ModelVersion).filter(ModelVersion.name == name).update({"is_active": False})
                summ = m.get("models", {}).get("xgboost", m.get("test_metrics", m))
                db.add(ModelVersion(name=name, kind=kind, version=m["version"], metrics=json_safe(summ), data_origin=m.get("data_origin", "synthetic")))
        db.commit()
    except Exception:
        log.exception("model version sync failed")
    finally:
        db.close()


def json_safe(d):
    import json
    return json.loads(json.dumps(d, default=str)) if isinstance(d, dict) else {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_model_versions()
    task = None
    if settings.simulator_autostart:
        db = SessionLocal()
        try:
            from app.models import Machine
            has = db.query(Machine).count() > 0
        except Exception:
            has = False
        finally:
            db.close()
        if has:
            task = asyncio.create_task(simulator.run())
            log.info("Industrial SIMULATOR started (simulated data only)")
        if registry.available()["forecast"]:
            asyncio.get_event_loop().run_in_executor(None, lambda: _safe(registry.forecast_model))
    yield
    if task:
        task.cancel()


def _safe(fn):
    try:
        fn()
    except Exception:
        log.exception("preload failed")


app = FastAPI(title="INDUSTRIX AI", version="1.0.0", lifespan=lifespan,
              description="AI-powered industrial risk intelligence (decision-support prototype; not a certified safety system).")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for r in (auth, facilities, machines, sensors, ai, dashboard, maintenance, incidents, documents, reports_api, simulator_api, misc):
    app.include_router(r.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
