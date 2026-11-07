from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    vibration: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shift_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    production_intensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_severity: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(20), default="simulated")  # simulated|manual|hardware
    __table_args__ = (Index("ix_readings_machine_ts", "machine_id", "timestamp"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(40))
    artifact_path: Mapped[str] = mapped_column(String(300), default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    data_origin: Mapped[str] = mapped_column(String(40), default="synthetic")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("sensor_readings.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    probability: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(12))
    priority: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(40))
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    contributions: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # cached SHAP output
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("ix_pred_machine_ts", "machine_id", "timestamp"),)


class AnomalyRecord(Base):
    __tablename__ = "anomaly_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("sensor_readings.id", ondelete="SET NULL"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    parameter: Mapped[str] = mapped_column(String(30))
    observed_value: Mapped[float] = mapped_column(Float)
    expected_low: Mapped[float] = mapped_column(Float)
    expected_high: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(12))
    suggestion: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("ix_anom_machine_ts", "machine_id", "timestamp"),)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    maint_type: Mapped[str] = mapped_column(String(20), default="preventive")  # preventive|corrective|inspection
    priority: Mapped[str] = mapped_column(String(12), default="medium")  # low|medium|high|critical
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|in_progress|completed|cancelled
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|ai_recommendation
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completion_notes: Mapped[str] = mapped_column(Text, default="")
    risk_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InspectionRecord(Base):
    __tablename__ = "inspection_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    inspector_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    inspected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(12), default="pass")  # pass|conditional|fail
    notes: Mapped[str] = mapped_column(Text, default="")
