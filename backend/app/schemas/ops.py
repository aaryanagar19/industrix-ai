from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM, UTCDatetime


class ReadingIn(BaseModel):
    machine_id: int
    timestamp: UTCDatetime | None = None
    temperature: float | None = Field(default=None, ge=-100, le=2000)
    vibration: float | None = Field(default=None, ge=0, le=200)
    pressure: float | None = Field(default=None, ge=0, le=2000)
    load_pct: float | None = Field(default=None, ge=0, le=100)
    shift_hours: float | None = Field(default=None, ge=0, le=24)
    production_intensity: float | None = Field(default=None, ge=0, le=1)
    weather_severity: float | None = Field(default=None, ge=0, le=1)
    data_source: Literal["simulated", "manual", "hardware"] = "manual"


class PredictIn(BaseModel):
    machine_id: int
    temperature: float | None = None
    vibration: float | None = None
    pressure: float | None = None
    load_pct: float | None = Field(default=None, ge=0, le=100)
    shift_hours: float | None = Field(default=None, ge=0, le=24)
    production_intensity: float | None = Field(default=None, ge=0, le=1)
    weather_severity: float | None = Field(default=None, ge=0, le=1)
    equipment_age_years: float | None = Field(default=None, ge=0)
    maintenance_delay_days: float | None = Field(default=None, ge=0)
    previous_incidents: int | None = Field(default=None, ge=0)
    inspection_status: Literal["pass", "conditional", "fail"] | None = None
    explain: bool = True


class ForecastIn(BaseModel):
    machine_id: int


class AnomalyScanIn(BaseModel):
    machine_id: int
    hours: int = Field(default=24, ge=1, le=168)
    persist: bool = False


class MaintenanceIn(BaseModel):
    machine_id: int
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    maint_type: Literal["preventive", "corrective", "inspection"] = "preventive"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    due_date: UTCDatetime | None = None
    assigned_to_id: int | None = None
    source: Literal["manual", "ai_recommendation"] = "manual"


class MaintenancePatch(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["scheduled", "in_progress", "completed", "cancelled"] | None = None
    due_date: UTCDatetime | None = None
    assigned_to_id: int | None = None
    completion_notes: str | None = None


class InspectionIn(BaseModel):
    machine_id: int
    status: Literal["pass", "conditional", "fail"]
    notes: str = ""


class IncidentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    incident_type: Literal["equipment_failure", "fire_overheat", "leak_spill", "electrical", "near_miss", "personal_injury", "other"] = "equipment_failure"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    machine_id: int | None = None
    department_id: int | None = None
    assigned_team: str = ""
    occurred_at: UTCDatetime | None = None


class IncidentPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["open", "responding", "resolved", "closed"] | None = None
    assigned_team: str | None = None
    resolution: str | None = None


class ActionIn(BaseModel):
    action: str = Field(min_length=3)
    category: Literal["checklist", "recorded"] = "recorded"
    status: Literal["pending", "done", "skipped"] = "done"


class ActionPatch(BaseModel):
    status: Literal["pending", "done", "skipped"]


class TextDocIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    doc_type: Literal["maintenance_log", "inspection_report", "incident_description", "near_miss_report", "equipment_complaint"] = "maintenance_log"
    text: str = Field(min_length=10, max_length=60000)


class ReportIn(BaseModel):
    report_type: Literal["daily_safety", "weekly_risk", "monthly_incident", "machine_health", "maintenance", "anomaly_detection", "ai_prediction", "emergency_response"]
    format: Literal["csv", "pdf"] = "pdf"
    facility_id: int | None = None
    incident_id: int | None = None
    days: int | None = Field(default=None, ge=1, le=366)


class ThresholdsIn(BaseModel):
    moderate: float = Field(gt=0, lt=1)
    high: float = Field(gt=0, lt=1)
    critical: float = Field(gt=0, lt=1)


class SimControl(BaseModel):
    running: bool | None = None
    speed: float | None = Field(default=None, ge=0.25, le=20)


class SimInject(BaseModel):
    machine_id: int
    kind: Literal["temperature_spike", "vibration_surge", "pressure_instability", "overload", "combined_fault"]
    duration_s: int = Field(default=60, ge=10, le=600)
    cascade: bool = False
