from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DB, get_machine_or_404
from app.core.security import get_current_user, require_roles
from app.schemas.ops import SimControl, SimInject
from app.services.common import audit
from app.simulator.engine import simulator

router = APIRouter(prefix="/api/simulator", tags=["simulator"])
OPS = require_roles("plant_manager", "safety_manager")


@router.get("/status")
def status(user=Depends(get_current_user)):
    return simulator.status()


@router.post("/control")
def control(body: SimControl, db: DB, user=Depends(OPS)):
    if body.running is not None:
        simulator.running = body.running
    if body.speed is not None:
        simulator.speed = body.speed
    audit(db, user, "simulator_control", "simulator", "", body.model_dump(exclude_none=True))
    return simulator.status()


@router.post("/inject")
def inject(body: SimInject, db: DB, user=Depends(OPS)):
    m = get_machine_or_404(db, body.machine_id)
    simulator.inject(m.id, body.kind, body.duration_s, body.cascade)
    audit(db, user, "simulator_inject", "machine", m.id, body.model_dump())
    return {"message": f"Injected '{body.kind}' on {m.code} for {body.duration_s}s (simulated test condition)", **simulator.status()}


@router.post("/clear")
def clear(db: DB, user=Depends(OPS)):
    simulator.clear()
    return simulator.status()
