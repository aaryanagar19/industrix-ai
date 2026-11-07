from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DB
from app.core.security import get_current_user, require_roles
from app.models import Department, Facility, Machine
from app.schemas.assets import DepartmentIn, DepartmentOut, FacilityIn, FacilityOut
from app.services.common import audit

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityOut])
def list_facilities(db: DB, user=Depends(get_current_user)):
    return db.query(Facility).order_by(Facility.name).all()


@router.post("", response_model=FacilityOut, status_code=201)
def create_facility(body: FacilityIn, db: DB, user=Depends(require_roles())):
    if db.query(Facility).filter(Facility.name == body.name).first():
        raise HTTPException(409, "Facility name already exists")
    f = Facility(**body.model_dump())
    db.add(f); db.commit()
    audit(db, user, "create_facility", "facility", f.id)
    return f


@router.get("/{facility_id}")
def get_facility(facility_id: int, db: DB, user=Depends(get_current_user)):
    f = db.get(Facility, facility_id)
    if not f:
        raise HTTPException(404, "Facility not found")
    return {**FacilityOut.model_validate(f).model_dump(mode="json"), "departments": [DepartmentOut.model_validate(d).model_dump() for d in f.departments],
            "machine_count": db.query(Machine).filter(Machine.facility_id == f.id).count()}


@router.post("/{facility_id}/departments", response_model=DepartmentOut, status_code=201)
def create_department(facility_id: int, body: DepartmentIn, db: DB, user=Depends(require_roles())):
    if not db.get(Facility, facility_id):
        raise HTTPException(404, "Facility not found")
    d = Department(facility_id=facility_id, **body.model_dump())
    db.add(d); db.commit()
    audit(db, user, "create_department", "department", d.id)
    return d
