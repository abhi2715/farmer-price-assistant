import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="agriroute-test-")
# Must be set before any app import (settings + engine are created at import time).
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_TMP}/test.db"),
    "REDIS_URL": "",
    "MODEL_DIR": f"{_TMP}/models",
    "REPORT_DIR": f"{_TMP}/reports",
    "MLFLOW_TRACKING_URI": f"file:{_TMP}/mlruns",
    "ENABLE_PROPHET": os.environ.get("TEST_ENABLE_PROPHET", "false"),
    "BACKTEST_ORIGINS": "1",
    "BACKTEST_SERIES": "6",
    "LGBM_ROUNDS": "80",
    "OTP_DEV_MODE": "true",
    "USE_LIVE_APIS": "false",
})

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

BACKEND = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def seeded():
    from app.db import SessionLocal, engine
    from app.scripts import seed
    from app.services import forecasting

    if engine.dialect.name == "postgresql":  # CI: start from a clean schema
        from sqlalchemy import text

        with engine.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    command.upgrade(cfg, "head")
    seed.run()
    db = SessionLocal()
    try:
        res = forecasting.train(db)
        forecasting.generate_forecasts(db)
    finally:
        db.close()
    return res


@pytest.fixture
def db(seeded):
    from app.db import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client(seeded):
    from app.main import app
    from app.ratelimit import limiter

    limiter.reset()
    with TestClient(app) as c:
        yield c


def login(client, phone, **extra) -> dict:
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": r.json()["dev_otp"], **extra})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


FARMER, BUYER, ADMIN = "9000000001", "9100000001", "9999999999"
