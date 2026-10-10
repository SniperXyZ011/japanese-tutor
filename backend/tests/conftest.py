import os
import uuid

os.environ.setdefault("APP_ENV", "test")
os.environ["AI_PROVIDER"] = "mock"
os.environ["AUTH_MODE"] = "local"
os.environ.pop("OPENROUTER_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded() -> None:
    with SessionLocal() as db:
        seed(db)


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def user_client() -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v1/auth/signup",
               json={"email": f"u{uuid.uuid4().hex[:10]}@example.com", "password": "password123"})
    assert r.status_code == 201, r.text
    yield c
    c.delete("/api/v1/me")


@pytest.fixture
def onboarded(user_client: TestClient) -> TestClient:
    r = user_client.patch("/api/v1/me", json={"onboarding": {"goals": ["travel"]},
                                               "onboarding_completed": True,
                                               "current_level": "absolute_beginner"})
    assert r.status_code == 200
    return user_client
