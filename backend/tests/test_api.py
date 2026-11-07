import pytest

from app.models import Machine, Notification


def mid(client, admin, code="CN-01"):
    items = client.get("/api/machines", headers=admin, params={"q": code}).json()["items"]
    return items[0]["id"]


# 1. login ---------------------------------------------------------------------------------------------
def test_login_success_and_me(client):
    r = client.post("/api/auth/login", json={"email": "admin@industrix.dev", "password": "Admin@12345"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "super_admin"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "admin@industrix.dev"


def test_login_failure_and_protected_routes(client):
    assert client.post("/api/auth/login", json={"email": "admin@industrix.dev", "password": "nope"}).status_code == 401
    assert client.get("/api/dashboard/overview").status_code == 401
    assert client.get("/api/machines", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_register_validation_and_default_role(client):
    assert client.post("/api/auth/register", json={"email": "bad", "password": "longenough1", "full_name": "Bad Mail"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "x@y.io", "password": "short", "full_name": "Short Pw"}).status_code == 422
    r = client.post("/api/auth/register", json={"email": "new.user@test.io", "password": "StrongPass1", "full_name": "New User"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "plant_manager"   # never self-assigns admin
    assert client.post("/api/auth/register", json={"email": "new.user@test.io", "password": "StrongPass1", "full_name": "New User"}).status_code == 409


# 2. dashboard -----------------------------------------------------------------------------------------------
def test_dashboard_overview_matches_database(client, admin, db):
    r = client.get("/api/dashboard/overview", headers=admin)
    assert r.status_code == 200
    d = r.json()
    assert d["totals"]["machines"] == db.query(Machine).count()
    assert sum(d["risk_distribution"].values()) <= d["totals"]["machines"]
    assert 0 <= d["safety_score"] <= 100
    assert client.get("/api/dashboard/risk-trends", headers=admin, params={"hours": 24}).status_code == 200
    assert isinstance(client.get("/api/dashboard/recent-alerts", headers=admin).json(), list)


def test_dashboard_filters_change_results(client, admin):
    all_ = client.get("/api/dashboard/overview", headers=admin).json()["totals"]["machines"]
    one = client.get("/api/dashboard/overview", headers=admin, params={"machine_id": mid(client, admin)}).json()["totals"]["machines"]
    assert one == 1 < all_


# 3. machine creation -------------------------------------------------------------------------------------------
def test_machine_crud_and_rbac(client, admin, plant_mgr, engineer):
    fac = client.get("/api/facilities", headers=admin).json()[0]["id"]
    body = {"code": "TST-01", "name": "Test Mill", "facility_id": fac, "machine_type": "cnc_mill", "install_year": 2020}
    assert client.post("/api/machines", headers=engineer, json=body).status_code == 403
    r = client.post("/api/machines", headers=plant_mgr, json=body)
    assert r.status_code == 201 and r.json()["baseline"]["temperature"]["mean"] > 0
    assert client.post("/api/machines", headers=plant_mgr, json=body).status_code == 409
    assert client.post("/api/machines", headers=plant_mgr, json={**body, "code": "bad code!"}).status_code == 422
    mid_ = r.json()["id"]
    assert client.patch(f"/api/machines/{mid_}", headers=plant_mgr, json={"status": "idle"}).json()["status"] == "idle"
    assert client.delete(f"/api/machines/{mid_}", headers=plant_mgr).status_code == 403   # delete is super admin only
    assert client.delete(f"/api/machines/{mid_}", headers=admin).status_code == 204
    assert client.get(f"/api/machines/{mid_}", headers=admin).status_code == 404


def test_machine_search_and_pagination(client, admin):
    r = client.get("/api/machines", headers=admin, params={"q": "chiller"}).json()
    assert r["total"] == 1 and r["items"][0]["code"] == "CH-01"
    p = client.get("/api/machines", headers=admin, params={"page_size": 5, "page": 3}).json()
    assert len(p["items"]) == 2 and p["total"] >= 12


def test_engineer_only_sees_assigned_machines(client, engineer, admin):
    codes = {m["code"] for m in client.get("/api/machines", headers=engineer).json()["items"]}
    assert codes == {"CN-01", "CN-02", "GR-01", "HP-01"}


# 4. sensor ingestion -------------------------------------------------------------------------------------------
def test_sensor_ingestion_stores_and_predicts(client, admin):
    m = mid(client, admin)
    r = client.post("/api/sensors/readings", headers=admin, json={"machine_id": m, "temperature": 62, "vibration": 2.1, "pressure": 6.5, "load_pct": 60, "data_source": "manual"})
    assert r.status_code == 201
    res = r.json()["results"][0]
    assert res["reading"]["data_source"] == "manual" and 0 <= res["prediction"]["probability"] <= 1
    hist = client.get(f"/api/sensors/{m}/history", headers=admin, params={"hours": 1}).json()
    assert hist["points"] and hist["baseline"]["temperature"]


def test_sensor_validation(client, admin):
    m = mid(client, admin)
    assert client.post("/api/sensors/readings", headers=admin, json={"machine_id": m, "load_pct": 140}).status_code == 422
    assert client.post("/api/sensors/readings", headers=admin, json={"machine_id": m}).status_code == 422
    assert client.post("/api/sensors/readings", headers=admin, json={"machine_id": 99999, "temperature": 50}).status_code == 404


# 5-6. AI & anomaly -------------------------------------------------------------------------------------------------
def test_predict_contract(client, admin):
    r = client.post("/api/ai/predict", headers=admin, json={"machine_id": mid(client, admin)})
    d = r.json()
    assert r.status_code == 200 and d["category"] in ("Low", "Moderate", "High", "Critical")
    assert d["model_version"] and d["timestamp"].endswith("Z") and "data_quality" in d
    assert d["explanation"]["contributions"] and "NOT proof of physical causation" in d["explanation"]["disclaimer"]
    t = d["thresholds"]; assert t["moderate"] < t["high"] < t["critical"]


def test_predict_hazardous_inputs_raise_risk_and_warn(client, admin):
    m = mid(client, admin)
    normal = client.post("/api/ai/predict", headers=admin, json={"machine_id": m, "temperature": 62, "vibration": 2.1, "pressure": 6.5, "load_pct": 55, "inspection_status": "pass", "maintenance_delay_days": 0, "explain": False}).json()
    bad = client.post("/api/ai/predict", headers=admin, json={"machine_id": m, "temperature": 90, "vibration": 4.5, "pressure": 8.5, "load_pct": 97, "inspection_status": "fail", "maintenance_delay_days": 30, "shift_hours": 11, "explain": False}).json()
    assert bad["probability"] > normal["probability"] * 2
    assert bad["category"] in ("High", "Critical")
    assert any("What-if" in w for w in bad["data_quality"]["warnings"])


def test_explanation_endpoint(client, admin):
    p = client.post("/api/ai/predict", headers=admin, json={"machine_id": mid(client, admin), "temperature": 80, "explain": False}).json()
    e = client.get(f"/api/ai/explanations/{p['id']}", headers=admin).json()
    assert e["explanation"]["top_increasing"] is not None and e["baseline_comparison"]
    assert client.get("/api/ai/explanations/9999999", headers=admin).status_code == 404


def test_anomaly_detection_on_injected_spike(client, admin):
    m = mid(client, admin, "CN-02")
    r = client.post("/api/sensors/readings", headers=admin, json={"machine_id": m, "temperature": 110, "vibration": 2.4, "pressure": 6.0, "load_pct": 55, "data_source": "manual"}).json()
    an = r["results"][0]["anomaly"]
    assert an and an["parameter"] == "temperature" and an["severity"] in ("high", "critical") and an["observed_value"] > an["expected_high"]
    scan = client.post("/api/ai/anomaly-detection", headers=admin, json={"machine_id": m, "hours": 6}).json()
    assert scan["flagged"] >= 1
    assert client.get("/api/ai/anomalies", headers=admin, params={"severity": an["severity"]}).json()["total"] >= 1


def test_forecast_and_insufficient_data_warning(client, admin, plant_mgr):
    f = client.post("/api/ai/forecast", headers=admin, json={"machine_id": mid(client, admin)}).json()
    assert f["data_sufficiency"]["status"] in ("ok", "limited") and len(f["forecast"]) == 24
    p = f["forecast"][0]; assert p["temperature_lower"] <= p["temperature"] <= p["temperature_upper"]
    fac = client.get("/api/facilities", headers=admin).json()[0]["id"]
    new = client.post("/api/machines", headers=plant_mgr, json={"code": "NEW-99", "name": "Brand New", "facility_id": fac}).json()
    g = client.post("/api/ai/forecast", headers=admin, json={"machine_id": new["id"]}).json()
    assert g["data_sufficiency"]["status"] == "insufficient" and g["forecast"] == []


def test_model_performance_declares_synthetic(client, admin):
    d = client.get("/api/ai/model-performance", headers=admin).json()
    assert "SYNTHETIC" in d["data_origin_warning"] and d["risk"]["models"]["xgboost"]["roc_auc"] > 0.5


def test_thresholds_validation_and_rbac(client, admin, engineer, safety_mgr):
    cur = client.get("/api/ai/thresholds", headers=admin).json()["active"]
    assert client.put("/api/ai/thresholds", headers=engineer, json=cur).status_code == 403
    assert client.put("/api/ai/thresholds", headers=safety_mgr, json={"moderate": 0.3, "high": 0.2, "critical": 0.5}).status_code == 422


# 7. maintenance ------------------------------------------------------------------------------------------------
def test_maintenance_workflow(client, admin, plant_mgr, engineer, safety_mgr):
    users = {u["email"]: u["id"] for u in client.get("/api/users", headers=admin).json()}
    m = mid(client, admin, "CN-01")
    r = client.post("/api/maintenance", headers=plant_mgr, json={"machine_id": m, "title": "Test lubrication", "priority": "high", "assigned_to_id": users["engineer@industrix.dev"], "due_date": "2020-01-01T00:00:00Z"})
    assert r.status_code == 201 and r.json()["is_overdue"] is True
    tid = r.json()["id"]
    assert client.post("/api/maintenance", headers=engineer, json={"machine_id": m, "title": "Not allowed"}).status_code == 403
    assert client.patch(f"/api/maintenance/{tid}", headers=engineer, json={"status": "in_progress", "priority": "low"}).json()["priority"] == "high"   # engineers cannot change priority
    done = client.patch(f"/api/maintenance/{tid}", headers=engineer, json={"status": "completed", "completion_notes": "done"}).json()
    assert done["status"] == "completed" and done["completed_at"] and done["is_overdue"] is False
    other = client.post("/api/maintenance", headers=safety_mgr, json={"machine_id": mid(client, admin, "CH-01"), "title": "Chiller job"}).json()["id"]
    assert client.patch(f"/api/maintenance/{other}", headers=engineer, json={"status": "completed"}).status_code == 403
    assert client.get("/api/maintenance", headers=admin, params={"overdue": True}).json()["total"] >= 1
    assert isinstance(client.get("/api/maintenance/recommendations", headers=plant_mgr).json()["items"], list)


# 8. incidents ----------------------------------------------------------------------------------------------------------
def test_incident_workflow_and_pdf(client, admin, officer, engineer):
    m = mid(client, admin, "HP-01")
    assert client.post("/api/incidents", headers=engineer, json={"title": "Nope"}).status_code == 403
    r = client.post("/api/incidents", headers=officer, json={"title": "Test oil leak", "incident_type": "leak_spill", "severity": "high", "machine_id": m})
    assert r.status_code == 201
    iid = r.json()["id"]
    d = client.get(f"/api/incidents/{iid}", headers=officer).json()
    assert any(a["category"] == "recommended" for a in d["actions"]) and "does not replace emergency services" in d["notice"]
    assert client.patch(f"/api/incidents/{iid}", headers=officer, json={"status": "resolved"}).status_code == 422   # needs resolution text
    a = client.post(f"/api/incidents/{iid}/actions", headers=officer, json={"action": "Area cordoned off", "category": "recorded", "status": "done"}).json()
    assert a["performed_by"]
    assert client.patch(f"/api/incidents/{iid}", headers=officer, json={"status": "resolved", "resolution": "Seal replaced"}).json()["resolved_at"]
    pdf = client.get(f"/api/incidents/{iid}/report", headers=officer)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


# 9. reports ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("rtype", ["daily_safety", "weekly_risk", "monthly_incident", "machine_health", "maintenance", "anomaly_detection", "ai_prediction", "emergency_response"])
def test_reports_generate_and_download(client, plant_mgr, rtype):
    for fmt in ("csv", "pdf"):
        r = client.post("/api/reports/generate", headers=plant_mgr, json={"report_type": rtype, "format": fmt})
        assert r.status_code == 201, r.text
        dl = client.get(f"/api/reports/{r.json()['id']}/download", headers=plant_mgr)
        assert dl.status_code == 200
        assert dl.content.startswith(b"%PDF") if fmt == "pdf" else rtype and b"," in dl.content[:300]


def test_report_rbac(client, engineer):
    assert client.post("/api/reports/generate", headers=engineer, json={"report_type": "daily_safety", "format": "csv"}).status_code == 403


# 10. RBAC ---------------------------------------------------------------------------------------------------------------------
def test_user_management_admin_only(client, admin, plant_mgr):
    assert client.get("/api/audit", headers=plant_mgr).status_code == 403
    assert client.post("/api/users", headers=plant_mgr, json={"email": "z@z.io", "password": "Password123", "full_name": "Zed Zed", "role": "super_admin"}).status_code == 403
    r = client.post("/api/users", headers=admin, json={"email": "created@z.io", "password": "Password123", "full_name": "Created User", "role": "safety_officer"})
    assert r.status_code == 201 and r.json()["role"] == "safety_officer"
    me = client.get("/api/auth/me", headers=admin).json()["id"]
    assert client.patch(f"/api/users/{me}", headers=admin, json={"role": "plant_manager"}).status_code == 400
    assert client.get("/api/audit", headers=admin).json()["total"] > 0


def test_preferences_persist(client, plant_mgr):
    client.patch("/api/auth/me/preferences", headers=plant_mgr, json={"theme": "light"})
    assert client.get("/api/auth/me", headers=plant_mgr).json()["preferences"]["theme"] == "light"


def test_notifications_flow(client, admin, db):
    n = client.get("/api/notifications", headers=admin).json()
    assert n["total"] >= 1
    client.post("/api/notifications/read-all", headers=admin)
    assert client.get("/api/notifications", headers=admin, params={"unread": True}).json()["unread"] == 0


# documents / NLP -------------------------------------------------------------------------------------------------------
def test_document_upload_and_analysis(client, officer):
    txt = b"Urgent: HP-01 hydraulic press has an oil leak and excessive vibration of 7.2 mm/s. Replace the seal immediately and inspect bearings."
    r = client.post("/api/documents/upload", headers=officer, files={"file": ("log.txt", txt, "text/plain")}, data={"doc_type": "maintenance_log"})
    assert r.status_code == 201
    a = r.json()["analysis"]
    assert "HP-01" in a["machines"]["codes"] and a["urgency"] == "high" and a["follow_up_actions"] and any("leak" in h for h in a["hazards"] + a["issues"])
    assert client.get(f"/api/documents/{r.json()['id']}/analysis", headers=officer).status_code == 200
    assert client.get(f"/api/documents/{r.json()['id']}/report", headers=officer).content.startswith(b"%PDF")


def test_document_upload_validation(client, officer):
    bad_ext = client.post("/api/documents/upload", headers=officer, files={"file": ("evil.exe", b"MZ....", "application/octet-stream")}, data={"doc_type": "maintenance_log"})
    assert bad_ext.status_code == 415
    fake_pdf = client.post("/api/documents/upload", headers=officer, files={"file": ("x.pdf", b"not a pdf at all", "application/pdf")}, data={"doc_type": "maintenance_log"})
    assert fake_pdf.status_code == 415
    big = client.post("/api/documents/upload", headers=officer, files={"file": ("big.txt", b"a" * (6 * 1024 * 1024), "text/plain")}, data={"doc_type": "maintenance_log"})
    assert big.status_code == 413


# propagation / twin / simulator ------------------------------------------------------------------------------------------
def test_propagation_uses_dependencies(client, admin):
    d = client.get("/api/risk/propagation", headers=admin).json()
    assert len(d["edges"]) == 17 and "ANALYTICAL ESTIMATE" in d["disclaimer"]
    assert all(n["propagated_risk"] >= n["local_risk"] - 1e-9 for n in d["nodes"])
    assert d["departments"] and all(x["layout"] for x in d["departments"])   # map needs zones (regression: page crashed without them)
    assert client.get("/api/twin", headers=admin).json()["departments"]


def test_simulator_controls(client, admin, engineer):
    st = client.get("/api/simulator/status", headers=admin).json()
    assert st["mode"] == "simulated" and st["hardware_connected"] is False
    assert client.post("/api/simulator/control", headers=engineer, json={"running": False}).status_code == 403
    assert client.post("/api/simulator/control", headers=admin, json={"speed": 2}).json()["speed"] == 2
    assert client.post("/api/simulator/inject", headers=admin, json={"machine_id": mid(client, admin), "kind": "temperature_spike", "duration_s": 30}).status_code == 200
    client.post("/api/simulator/clear", headers=admin)


def test_websocket_requires_token(client, admin):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/live?token=bad"):
            pass
    tok = admin["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/live?token={tok}") as ws:
        assert ws.receive_json()["type"] == "hello"


def test_time_bucketing_actually_aggregates(client, admin):
    """Regression: float division once made every row its own bucket."""
    d = client.get("/api/dashboard/risk-trends", headers=admin, params={"hours": 168}).json()
    assert d["bucket_seconds"] == 7200 and 0 < len(d["points"]) <= 168 / 2 + 2
    assert len({p["timestamp"] for p in d["points"]}) == len(d["points"])
    h = client.get(f"/api/sensors/{mid(client, admin)}/history", headers=admin, params={"hours": 24, "max_points": 100}).json()
    assert len(h["points"]) <= 110
