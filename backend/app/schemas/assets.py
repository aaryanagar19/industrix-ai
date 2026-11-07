import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORM, UTCDatetime

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Role = Literal["super_admin", "safety_manager", "plant_manager", "maintenance_engineer", "safety_officer"]


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("email")
    @classmethod
    def _e(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    facility_id: int | None = None
    preferences: dict = {}
    created_at: UTCDatetime


class UserCreate(RegisterIn):
    role: Role = "plant_manager"
    facility_id: int | None = None


class UserPatch(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    facility_id: int | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FacilityIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = ""
    industry_type: str = "manufacturing"


class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    layout: dict | None = None


class DepartmentOut(ORM):
    id: int
    facility_id: int
    name: str
    layout: dict | None = None


class FacilityOut(ORM):
    id: int
    name: str
    location: str
    industry_type: str
    created_at: UTCDatetime


MachineStatus = Literal["running", "idle", "maintenance", "offline"]


class MachineIn(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9\-_]+$")
    name: str = Field(min_length=2, max_length=120)
    facility_id: int
    department_id: int | None = None
    machine_type: str = "cnc_mill"
    status: MachineStatus = "running"
    zone: str = ""
    install_year: int | None = Field(default=None, ge=1950, le=2100)
    operating_hours: float = Field(default=0, ge=0)
    pos_x: float = 0
    pos_y: float = 0
    baseline: dict | None = None
    assigned_engineer_id: int | None = None


class MachinePatch(BaseModel):
    name: str | None = None
    department_id: int | None = None
    status: MachineStatus | None = None
    zone: str | None = None
    operating_hours: float | None = Field(default=None, ge=0)
    pos_x: float | None = None
    pos_y: float | None = None
    baseline: dict | None = None
    assigned_engineer_id: int | None = None


class MachineOut(ORM):
    id: int
    code: str
    name: str
    facility_id: int
    department_id: int | None
    machine_type: str
    status: str
    zone: str
    operating_hours: float
    last_inspection_at: UTCDatetime | None
    pos_x: float
    pos_y: float
    baseline: dict
    assigned_engineer_id: int | None
    age_years: float
