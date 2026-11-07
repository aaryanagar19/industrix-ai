from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, utcnow


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    industry_type: Mapped[str] = mapped_column(String(80), default="manufacturing")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    departments: Mapped[list["Department"]] = relationship(back_populates="facility", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    layout: Mapped[dict | None] = mapped_column(JSON, default=None)  # {x,y,w,h} for the digital twin
    facility: Mapped[Facility] = relationship(back_populates="departments")
    __table_args__ = (UniqueConstraint("facility_id", "name"),)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"), default="plant_manager")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Machine(Base):
    __tablename__ = "machines"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True, nullable=True)
    machine_type: Mapped[str] = mapped_column(String(40), default="generic")
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|idle|maintenance|offline
    zone: Mapped[str] = mapped_column(String(60), default="")
    install_date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    operating_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_inspection_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    # {"temperature": {"mean":.., "std":..}, "vibration": {...}, "pressure": {...}, "load_pct": {...}}
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    assigned_engineer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    facility: Mapped[Facility] = relationship()
    department: Mapped[Department | None] = relationship()

    @property
    def age_years(self) -> float:
        return max((utcnow() - self.install_date).days / 365.25, 0.0)


class MachineDependency(Base):
    __tablename__ = "machine_dependencies"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1 influence of source on target
    relation: Mapped[str] = mapped_column(String(40), default="feeds")  # cooling|power|feeds|air|shared_zone
    __table_args__ = (UniqueConstraint("source_id", "target_id"),)
