import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="industrix_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_DIR"] = f"{_tmp}/storage"
os.environ["SIMULATOR_AUTOSTART"] = "false"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "10000"
ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "models" / "risk_model.joblib").exists():  # train quick models once if artifacts are absent
    os.environ["MODELS_DIR"] = f"{_tmp}/models"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _models():
    from app.ml import registry
    if not registry.available()["risk"]:
        from app.ml.training.train_all import main
        main(fast=True)
        registry.reset()


@pytest.fixture(scope="session")
def client(_models):
    Base.metadata.create_all(engine)
    from app.seed import seed
    seed(days=3)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client): return _login(client, "admin@industrix.dev", "Admin@12345")
@pytest.fixture(scope="session")
def safety_mgr(client): return _login(client, "safety.manager@industrix.dev", "SafetyMgr@123")
@pytest.fixture(scope="session")
def plant_mgr(client): return _login(client, "plant.manager@industrix.dev", "PlantMgr@123")
@pytest.fixture(scope="session")
def engineer(client): return _login(client, "engineer@industrix.dev", "Engineer@123")
@pytest.fixture(scope="session")
def officer(client): return _login(client, "officer@industrix.dev", "Officer@123")


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()
