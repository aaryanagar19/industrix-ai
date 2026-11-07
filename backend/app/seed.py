"""Seed the database with a demo facility, users, machines, dependency graph and ~10 days of GENERATED history.

    python -m app.seed [--reset] [--days 10]

All sensor history is synthetic (same generator as model training, different random stream). Passwords below are
DEVELOPMENT ONLY."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from alembic import command
from alembic.config import Config

from app.api.auth import ensure_roles
from app.core.config import ROOT
from app.core.db import Base, SessionLocal, engine, utcnow
from app.core.security import hash_password
from app.ml import registry
from app.ml.anomaly_detection import detector
from app.ml.common import baseline_for
from app.ml.inference import risk as risk_inf
from app.ml.nlp.pipeline import analyze_text
from app.ml.training.data_gen import generate_machine_series
from app.models import (AnomalyRecord, Department, Document, EmergencyAction, Facility, Incident, InspectionRecord, Machine, MachineDependency,
                        MaintenanceRecord, NlpResult, Notification, RiskPrediction, SensorReading, User)

DEV_USERS = [("admin@industrix.dev", "Admin@12345", "Asha Verma (Super Admin)", "super_admin"), ("safety.manager@industrix.dev", "SafetyMgr@123", "Rahul Mehta", "safety_manager"),
             ("plant.manager@industrix.dev", "PlantMgr@123", "Priya Nair", "plant_manager"), ("engineer@industrix.dev", "Engineer@123", "Vikram Singh", "maintenance_engineer"),
             ("officer@industrix.dev", "Officer@123", "Neha Gupta", "safety_officer")]

DEPTS = {"Utilities": {"x": 20, "y": 20, "w": 300, "h": 260}, "Casting": {"x": 340, "y": 20, "w": 320, "h": 260}, "Machining": {"x": 680, "y": 20, "w": 300, "h": 260},
         "Assembly": {"x": 20, "y": 320, "w": 480, "h": 260}, "Packaging": {"x": 520, "y": 320, "w": 460, "h": 260}}
# code, name, type, dept, install year, x, y, hours
MACHINES = [("CH-01", "Cooling Chiller", "chiller", "Utilities", 2016, 80, 90, 41000), ("AC-01", "Air Compressor", "compressor", "Utilities", 2014, 230, 90, 62000),
            ("BL-01", "Steam Boiler", "boiler", "Utilities", 2012, 80, 200, 71000), ("PM-01", "Coolant Pump", "pump", "Utilities", 2019, 230, 200, 22000),
            ("FN-01", "Induction Furnace", "furnace", "Casting", 2015, 420, 90, 52000), ("HP-01", "Hydraulic Press", "hydraulic_press", "Casting", 2013, 570, 150, 68000),
            ("CN-01", "CNC Mill", "cnc_mill", "Machining", 2020, 750, 90, 15000), ("CN-02", "CNC Lathe", "lathe", "Machining", 2018, 880, 90, 26000),
            ("GR-01", "Surface Grinder", "grinder", "Machining", 2017, 810, 200, 33000), ("CV-01", "Main Conveyor", "conveyor", "Assembly", 2019, 100, 440, 24000),
            ("RB-01", "Welding Robot", "robot", "Assembly", 2021, 300, 400, 11000), ("PK-01", "Packaging Line", "packaging", "Packaging", 2020, 700, 440, 16000)]
DEPS = [("CH-01", "FN-01", .8, "cooling"), ("CH-01", "HP-01", .6, "cooling"), ("CH-01", "CN-01", .5, "cooling"), ("PM-01", "CH-01", .7, "cooling"), ("BL-01", "HP-01", .4, "power"),
        ("AC-01", "CN-01", .5, "air"), ("AC-01", "CN-02", .5, "air"), ("AC-01", "RB-01", .5, "air"), ("AC-01", "PK-01", .4, "air"), ("FN-01", "HP-01", .6, "feeds"),
        ("HP-01", "CN-01", .5, "feeds"), ("CN-01", "GR-01", .5, "feeds"), ("CN-02", "GR-01", .4, "feeds"), ("GR-01", "CV-01", .5, "feeds"), ("CV-01", "RB-01", .6, "feeds"),
        ("RB-01", "PK-01", .5, "feeds"), ("CV-01", "PK-01", .4, "feeds")]

SAMPLE_DOCS = [
    ("maint_log_HP-01.txt", "maintenance_log", "Maintenance log 12 Oct. HP-01 Hydraulic Press showed excessive vibration of 6.8 mm/s and low oil level. Bearing wear suspected. Oil leak noted near seal. Recommend replace seal and inspect bearings within this week. Temperature reached 92 C during operation."),
    ("near_miss_CV-01.txt", "near_miss_report", "Near miss reported at conveyor CV-01. Guard was missing and operator almost caught sleeve in the belt, no injury. Urgent: reinstall guard immediately and review lock-out procedure with the shift supervisor."),
    ("inspection_BL-01.txt", "inspection_report", "Routine quarterly inspection of BL-01 Steam Boiler completed. Pressure 12.1 bar within limits. Minor corrosion on feed pipe flagged. Schedule repainting and monitor. All safety valves tested and verified."),
]


def run_migrations():
    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")


def reset_db():
    Base.metadata.drop_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


def seed(days: int = 10, seed_value: int = 7) -> dict:
    rng = np.random.default_rng(seed_value)
    db = SessionLocal()
    try:
        ensure_roles(db)
        if db.query(User).count():
            return {"skipped": "database already seeded (use --reset)"}
        for email, pw, name, role in DEV_USERS:
            db.add(User(email=email, hashed_password=hash_password(pw), full_name=name, role=role))
        fac = Facility(name="Apex Manufacturing - Unit 1", location="Indore, Madhya Pradesh, India", industry_type="metal fabrication")
        db.add(fac); db.commit()
        depts = {}
        for n, lay in DEPTS.items():
            d = Department(facility_id=fac.id, name=n, layout=lay); db.add(d); db.flush(); depts[n] = d
        eng = db.query(User).filter(User.role == "maintenance_engineer").first()
        ms: dict[str, Machine] = {}
        for code, name, mtype, dept, year, x, y, hrs in MACHINES:
            m = Machine(code=code, name=name, facility_id=fac.id, department_id=depts[dept].id, machine_type=mtype, zone=f"{dept} bay", install_date=datetime(year, 3, 1), operating_hours=hrs,
                        pos_x=x, pos_y=y, baseline=baseline_for(mtype, 0.02, rng), assigned_engineer_id=eng.id if code in ("CN-01", "CN-02", "GR-01", "HP-01") else None,
                        last_inspection_at=utcnow() - timedelta(days=int(rng.integers(3, 40))))
            db.add(m); db.flush(); ms[code] = m
        for s, t, w, rel in DEPS:
            db.add(MachineDependency(source_id=ms[s].id, target_id=ms[t].id, weight=w, relation=rel))
        db.commit()

        officer, mgr = (db.query(User).filter(User.role == r).first() for r in ("safety_officer", "safety_manager"))
        now = utcnow().replace(second=0, microsecond=0)
        # incidents first (previous_incidents feature depends on them)
        inc_specs = [(2, "HP-01", "Hydraulic hose rupture", "leak_spill", "high", "resolved"), (5, "FN-01", "Furnace over-temperature alarm", "fire_overheat", "high", "resolved"),
                     (9, "CV-01", "Guard missing - near miss", "near_miss", "medium", "closed"), (14, "GR-01", "Spindle bearing seizure", "equipment_failure", "medium", "resolved"),
                     (20, "BL-01", "Safety valve lifted unexpectedly", "equipment_failure", "high", "resolved"), (27, "RB-01", "Cable insulation damage - sparking", "electrical", "high", "resolved"),
                     (33, "AC-01", "Operator slipped on oil film", "personal_injury", "low", "closed"), (38, "PK-01", "Near miss: forklift crossing", "near_miss", "low", "closed"),
                     (1, "CH-01", "Chiller coolant leak", "leak_spill", "medium", "responding"), (0, "CN-02", "Spindle vibration alarm", "equipment_failure", "medium", "open")]
        from app.api.incidents import DEFAULT_PROCEDURES
        for ago, code, title, typ, sev, status in inc_specs:
            occ = now - timedelta(days=ago, hours=int(rng.integers(0, 10)))
            i = Incident(title=title, description=f"{title} on {ms[code].name}. Demo record.", incident_type=typ, severity=sev, status=status, facility_id=fac.id, department_id=ms[code].department_id,
                         machine_id=ms[code].id, reported_by_id=officer.id, assigned_team="Shift B response team", occurred_at=occ,
                         resolved_at=occ + timedelta(hours=6) if status in ("resolved", "closed") else None, resolution="Corrective action completed and verified by safety officer." if status in ("resolved", "closed") else "")
            db.add(i); db.flush()
            for step in DEFAULT_PROCEDURES.get(typ, []):
                db.add(EmergencyAction(incident_id=i.id, category="recommended", action=step, status="pending"))
            db.add(EmergencyAction(incident_id=i.id, category="event", action=f"Incident created by {officer.full_name}", status="done", performed_by_id=officer.id, performed_at=occ))
            if status != "open":
                db.add(EmergencyAction(incident_id=i.id, category="recorded", action="Area made safe and supervisor informed", status="done", performed_by_id=officer.id, performed_at=occ + timedelta(minutes=20)))
        db.commit()

        # maintenance & inspections
        tasks = [("HP-01", "Replace hydraulic seals", "corrective", "high", "in_progress", -2), ("CH-01", "Coolant circuit leak repair", "corrective", "critical", "scheduled", -1), ("GR-01", "Spindle bearing inspection", "inspection", "medium", "scheduled", 2),
                 ("BL-01", "Safety valve calibration", "preventive", "high", "scheduled", 5), ("AC-01", "Compressor oil change", "preventive", "medium", "scheduled", -4), ("CN-01", "Quarterly lubrication", "preventive", "low", "scheduled", 9),
                 ("FN-01", "Refractory lining check", "inspection", "high", "completed", -12), ("CV-01", "Replace belt guard", "corrective", "high", "completed", -8), ("RB-01", "Cable harness replacement", "corrective", "high", "completed", -25),
                 ("PM-01", "Pump alignment", "preventive", "low", "completed", -30), ("CN-02", "Spindle vibration diagnostics", "corrective", "medium", "scheduled", 1), ("PK-01", "Sensor calibration", "preventive", "low", "scheduled", 12)]
        for code, title, typ, pr, st, due in tasks:
            t = MaintenanceRecord(machine_id=ms[code].id, title=title, maint_type=typ, priority=pr, status=st, due_date=now + timedelta(days=due), assigned_to_id=eng.id if code in ("CN-01", "CN-02", "GR-01", "HP-01") else None,
                                  created_by_id=mgr.id, source="manual", description="Demo task")
            if st == "completed":
                t.completed_at = now + timedelta(days=due + 1); t.completion_notes = "Completed as planned."
            db.add(t)
        for code, m in ms.items():
            st = "fail" if code == "CH-01" else "conditional" if code in ("GR-01", "BL-01") else "pass"
            db.add(InspectionRecord(machine_id=m.id, inspector_id=officer.id, status=st, notes="Demo inspection", inspected_at=now - timedelta(days=int(rng.integers(3, 30)))))
        db.commit()

        # history
        have_models = registry.available()["risk"] and registry.available()["anomaly"]
        steps = days * 96
        start = now - timedelta(minutes=15 * (steps - 1))
        n_readings = n_preds = n_anoms = 0
        thr = risk_inf.effective_thresholds() if have_models else None
        ab = registry.anomaly_bundle() if have_models else None
        for code, m in ms.items():
            df, base = generate_machine_series(m.machine_type, steps, 15, start, rng, age_years=m.age_years, baseline=m.baseline)
            obs = {k: df[f"{k}_true"] + rng.normal(0, 0.12 * m.baseline[p]["std"], steps) for k, p in (("temperature", "temperature"), ("vibration", "vibration"), ("pressure", "pressure"), ("load", "load_pct"))}
            rows = [{"machine_id": m.id, "timestamp": ts.to_pydatetime(), "temperature": float(obs["temperature"][i]), "vibration": float(obs["vibration"][i]), "pressure": float(max(obs["pressure"][i], 0)),
                     "load_pct": float(np.clip(obs["load"][i], 0, 100)), "shift_hours": float(df.shift_hours[i]), "production_intensity": float(df.production_intensity[i]),
                     "weather_severity": float(df.weather_severity[i]), "data_source": "simulated"} for i, ts in enumerate(df.timestamp)]
            db.bulk_insert_mappings(SensorReading, rows); db.commit(); n_readings += len(rows)
            if not have_models:
                continue
            dev = pd.DataFrame({"temperature_dev": [(r["temperature"] - m.baseline["temperature"]["mean"]) / m.baseline["temperature"]["std"] for r in rows],
                                "vibration_dev": [(r["vibration"] - m.baseline["vibration"]["mean"]) / m.baseline["vibration"]["std"] for r in rows],
                                "pressure_dev": [(r["pressure"] - m.baseline["pressure"]["mean"]) / m.baseline["pressure"]["std"] for r in rows],
                                "load_dev": [(r["load_pct"] - m.baseline["load_pct"]["mean"]) / m.baseline["load_pct"]["std"] for r in rows]})
            tr = lambda c: dev[c] - dev[c].shift(1).rolling(12, min_periods=6).mean()
            prev_inc = db.query(Incident).filter(Incident.machine_id == m.id).count()
            feat = pd.DataFrame({**{c: dev[c] for c in ("temperature_dev", "vibration_dev", "pressure_dev")}, "load_pct": [r["load_pct"] for r in rows], "equipment_age_years": m.age_years,
                                 "maintenance_delay_days": df.maintenance_delay_days.values, "previous_incidents": float(min(prev_inc, 6)), "shift_hours": df.shift_hours.values,
                                 "production_intensity": df.production_intensity.values, "weather_severity": df.weather_severity.values, "inspection_status": df.inspection_status.values,
                                 "temperature_trend": tr("temperature_dev"), "vibration_trend": tr("vibration_dev")})
            idx = list(range(0, steps, 4))
            probs = risk_inf.predict_proba(feat.iloc[idx].to_dict("records"))
            ver = registry.risk_bundle()["version"]
            preds = [{"machine_id": m.id, "timestamp": rows[i]["timestamp"], "probability": float(p), "category": risk_inf.categorize(float(p), thr), "priority": "", "model_version": ver,
                      "features": {k: (None if pd.isna(v) else float(v)) for k, v in feat.iloc[i].items()}, "data_quality": {"status": "ok", "warnings": []}} for i, p in zip(idx, probs)]
            from app.ml.common import PRIORITY
            for p in preds: p["priority"] = PRIORITY[p["category"]]
            db.bulk_insert_mappings(RiskPrediction, preds); db.commit(); n_preds += len(preds)
            res = detector.evaluate(dev, ab["model"], ab["severity"])
            seen = set(); recs = []
            for i in np.where(res.flagged.values)[0]:
                key = (res.parameter.iloc[i], rows[i]["timestamp"].replace(minute=0, second=0))
                if key in seen: continue
                seen.add(key); param = key[0]; b = m.baseline[param]
                recs.append({"machine_id": m.id, "timestamp": rows[i]["timestamp"], "parameter": param, "observed_value": rows[i][param], "expected_low": round(b["mean"] - 3 * b["std"], 3),
                             "expected_high": round(b["mean"] + 3 * b["std"], 3), "score": float(res.score.iloc[i]), "severity": res.severity.iloc[i], "acknowledged": bool(rng.random() < 0.6),
                             "suggestion": "Inspect the affected subsystem and verify on site with a qualified technician."})
            db.bulk_insert_mappings(AnomalyRecord, recs); db.commit(); n_anoms += len(recs)

        for fn, dt, text in SAMPLE_DOCS:
            d = Document(filename=fn, doc_type=dt, content_type="text/plain", size_bytes=len(text), text_content=text, uploaded_by_id=officer.id); db.add(d); db.commit()
            db.add(NlpResult(document_id=d.id, result=analyze_text(text, [{"code": c, "name": mm.name} for c, mm in ms.items()]))); db.commit()
        db.add(Notification(title="Welcome to INDUSTRIX AI", message="Demo data loaded. All sensor data is simulated.", level="info", kind="system")); db.commit()
        from app.main import sync_model_versions
        sync_model_versions()
        return {"users": len(DEV_USERS), "machines": len(ms), "readings": n_readings, "predictions": n_preds, "anomalies": n_anoms, "incidents": len(inc_specs), "tasks": len(tasks)}
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args()
    if a.reset:
        reset_db()
    run_migrations()
    print(seed(a.days))
