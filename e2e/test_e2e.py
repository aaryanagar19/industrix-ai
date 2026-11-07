"""Browser end-to-end tests (Playwright). Requires the stack to be running:
    backend:  uvicorn app.main:app --port 8000     (seeded database, trained models)
    frontend: npm run dev                           (http://127.0.0.1:5173)
Run:  pip install playwright pytest && playwright install chromium && pytest e2e -q
Set SHOTS=1 to also write screenshots to docs/screenshots/."""
import json
import os
import re
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

BASE = os.getenv("E2E_BASE", "http://127.0.0.1:5173")
SHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
PAGES = [("dashboard", "/"), ("monitoring", "/monitoring"), ("prediction", "/prediction"), ("forecast", "/forecast"), ("anomalies", "/anomalies"), ("explain", "/explain"),
         ("digital-twin", "/twin"), ("risk-propagation", "/propagation"), ("maintenance", "/maintenance"), ("incidents", "/incidents"), ("emergency", "/emergency"),
         ("documents", "/documents"), ("reports", "/reports"), ("notifications", "/notifications"), ("users", "/users"), ("settings", "/settings")]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def ctx(browser):
    c = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    yield c
    c.close()


def login(page, email="admin@industrix.dev", pw="Admin@12345"):
    page.goto(BASE + "/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(pw)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector("text=Executive Intelligence Dashboard", timeout=20000)


def api(page, path, method="GET", body=None):
    return page.evaluate("""async ([p, m, b]) => { const t = localStorage.getItem('ix_token');
      const r = await fetch(p, {method: m, headers: {'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json'}, body: b ? JSON.stringify(b) : undefined}); return r.json(); }""", [path, method, body])


def test_login_failure_then_success_and_protected_redirect(ctx):
    page = ctx.new_page()
    page.goto(BASE + "/monitoring")
    expect(page).to_have_url(re.compile("/login"))
    page.get_by_label("Email").fill("admin@industrix.dev"); page.get_by_label("Password").fill("wrong-password")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("alert")).to_contain_text("Invalid email or password")
    login(page)
    expect(page.get_by_text("Safety score")).to_be_visible()


def test_every_page_renders_without_errors(ctx):
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text and "WebSocket" not in m.text else None)
    login(page)
    if os.getenv("SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
    for name, path in PAGES:
        page.goto(BASE + path)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2500 if name in ("forecast", "digital-twin", "risk-propagation", "dashboard", "explain") else 1200)
        assert page.locator("h1").first.is_visible(), name
        assert "Something went wrong" not in page.content(), name
        if name == "forecast":
            page.locator("select").first.select_option(index=1); page.wait_for_timeout(4000)
        if name == "explain":
            page.wait_for_timeout(1500)
        if os.getenv("SHOTS"):
            page.screenshot(path=str(SHOTS / f"{name}.png"))
    assert not errors, errors[:5]


def test_dashboard_values_come_from_backend(ctx):
    page = ctx.new_page(); login(page)
    ov = api(page, "/api/dashboard/overview")
    expect(page.get_by_text(str(ov["safety_score"]), exact=True).first).to_be_visible()
    expect(page.get_by_text(f"{ov['totals']['machines_running']}/{ov['totals']['machines']}")).to_be_visible()


def test_live_websocket_updates_without_refresh(ctx):
    page = ctx.new_page(); login(page)
    page.goto(BASE + "/monitoring"); page.wait_for_selector("text=Simulator running", timeout=15000)
    expect(page.get_by_text("WebSocket connected")).to_be_visible(timeout=15000)
    card = page.locator("button", has_text="CN-01").first
    first = card.inner_text()
    page.wait_for_timeout(9000)
    assert card.inner_text() != first, "machine card did not change - no live updates"
    expect(page.get_by_text("SIMULATED DATA").first).to_be_visible()


def test_inject_fault_creates_anomaly_notification_and_risk_rise(ctx):
    page = ctx.new_page(); login(page)
    before = len(api(page, "/api/ai/anomalies?machine_id=7&hours=1")["items"])
    page.goto(BASE + "/monitoring"); page.wait_for_selector("text=Simulator running", timeout=15000)
    page.locator("button", has_text="CN-01").first.click()
    page.get_by_role("button", name=re.compile("Inject")).click()
    expect(page.get_by_text(re.compile("Injected 'temperature_spike' on CN-01")).first).to_be_visible(timeout=10000)
    deadline, found = time.time() + 60, False
    while time.time() < deadline and not found:
        page.wait_for_timeout(4000)
        items = api(page, "/api/ai/anomalies?machine_id=7&hours=1")["items"]
        found = len(items) > before and any(a["parameter"] == "temperature" for a in items)
    assert found, "no temperature anomaly was recorded after injection"
    notes = api(page, "/api/notifications?page_size=20")["items"]
    assert any("CN-01" in n["title"] for n in notes), "no notification for injected fault"
    pred = api(page, "/api/ai/predictions?machine_id=7&page_size=1")["items"][0]
    assert pred["probability"] > 0.02
    page.get_by_role("button", name="Clear all").click()


def test_incident_workflow_and_pdf_export(ctx):
    page = ctx.new_page(); login(page, "officer@industrix.dev", "Officer@123")
    page.goto(BASE + "/incidents")
    page.get_by_role("button", name="Report incident").click()
    page.get_by_role("dialog").get_by_label("Title").fill("E2E hydraulic leak")
    page.get_by_role("button", name="Create incident").click()
    page.wait_for_url(re.compile("/emergency\\?id="), timeout=10000)
    expect(page.get_by_text("Recommended response checklist")).to_be_visible()
    expect(page.get_by_text("never replaces emergency services", exact=False).first).to_be_visible()
    page.get_by_label("Record action").fill("Area cordoned off by E2E test"); page.get_by_role("button", name="Record", exact=True).click()
    expect(page.get_by_text("Area cordoned off by E2E test").first).to_be_visible(timeout=8000)
    page.get_by_role("button", name="Resolve…").click()
    page.get_by_role("button", name="Mark resolved").click()   # empty resolution -> validation
    expect(page.get_by_text("Resolution text is required")).to_be_visible()
    page.get_by_role("dialog").get_by_label("Resolution details (required)").fill("Seal replaced")
    page.get_by_role("button", name="Mark resolved").click()
    page.wait_for_timeout(1500)
    with page.expect_download() as d:
        page.get_by_role("button", name="Export PDF report").click()
    p = d.value.path(); assert open(p, "rb").read(5) == b"%PDF-"


def test_report_generation_and_csv_download(ctx):
    page = ctx.new_page(); login(page, "plant.manager@industrix.dev", "PlantMgr@123")
    page.goto(BASE + "/reports"); page.wait_for_selector("text=Generated reports")
    page.get_by_label("Format").select_option("csv")
    with page.expect_download() as d:
        page.get_by_role("button", name=re.compile("Generate")).click()
    txt = open(d.value.path(), encoding="utf-8").read()
    assert txt.startswith("Daily Safety Report") and "Machine" in txt


def test_machine_creation_via_ui_and_validation(ctx):
    page = ctx.new_page(); login(page, "plant.manager@industrix.dev", "PlantMgr@123")
    page.goto(BASE + "/monitoring"); page.get_by_role("button", name="Add machine").click()
    dlg = page.get_by_role("dialog"); dlg.get_by_role("button", name="Create").click()
    expect(dlg.get_by_role("alert")).to_contain_text("Code")
    code = f"E2E-{int(time.time()) % 10000}"
    dlg.get_by_label("Code").fill(code); dlg.get_by_label("Name").fill("E2E Test Machine"); dlg.get_by_role("button", name="Create").click()
    expect(page.get_by_text("Machine created")).to_be_visible(timeout=8000)
    page.get_by_placeholder("Filter machines…").fill(code)
    expect(page.locator("button", has_text=code)).to_be_visible(timeout=8000)


def test_role_based_access_in_ui(ctx):
    page = ctx.new_page(); login(page, "engineer@industrix.dev", "Engineer@123")
    expect(page.get_by_role("link", name="User Management")).to_have_count(0)
    page.goto(BASE + "/users"); expect(page.get_by_role("alert")).to_contain_text("does not have access")
    page.goto(BASE + "/monitoring"); page.locator("button", has_text="CN-01").first.wait_for(timeout=15000)
    assert page.locator("button", has_text="CN-01").count() == 1 and page.locator("button", has_text="CH-01").count() == 0   # assigned machines only
    expect(page.get_by_text("Simulator controls require")).to_be_visible()


def test_theme_toggle_and_responsive_layout(browser):
    c = browser.new_context(viewport={"width": 390, "height": 800}); page = c.new_page(); login(page)
    page.get_by_label("Toggle theme").click()
    assert "dark" not in (page.locator("html").get_attribute("class") or "")
    assert page.evaluate("document.documentElement.scrollWidth") <= 392, "horizontal overflow on mobile"
    page.get_by_label("Open menu").click(); expect(page.get_by_role("link", name="Live Monitoring")).to_be_visible()
    if os.getenv("SHOTS"):
        page.screenshot(path=str(SHOTS / "dashboard-mobile-light.png"))
    prefs = api(page, "/api/auth/me")["preferences"]; assert prefs.get("theme") == "light"   # persisted server-side
    c.close()
