"""Tests for auth endpoints and model integrity."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import app
from app.models import Paint, PaintStatus, Recipe, RecipeComponent, User, UserPaint


@pytest.fixture()
def client():
    return TestClient(app)


def test_register_endpoint_exists(client):
    """POST /auth/register should exist (may return 422 without body)."""
    response = client.post("/auth/register", json={})
    # 422 = validation error (missing fields) — endpoint is wired up
    assert response.status_code in (200, 201, 400, 422)


def test_login_endpoint_exists(client):
    """POST /auth/cookie/login should exist."""
    response = client.post("/auth/cookie/login", data={})
    assert response.status_code in (200, 400, 422)


def test_users_me_requires_auth(client):
    """GET /users/me should return 401 when unauthenticated."""
    response = client.get("/users/me")
    assert response.status_code == 401


def test_register_and_login(client):
    """Full register → login → /users/me round-trip."""
    import uuid as _uuid
    email = f"test-{_uuid.uuid4().hex[:8]}@example.com"
    creds = {"email": email, "password": "testPass_123!"}

    # Register
    reg = client.post("/auth/register", json=creds)
    assert reg.status_code in (200, 201), reg.text

    # Login
    login = client.post(
        "/auth/cookie/login",
        data={"username": creds["email"], "password": creds["password"]},
    )
    assert login.status_code in (200, 204), login.text

    # Access protected route with the cookie
    cookie = login.cookies.get("mixmini_auth")
    assert cookie is not None

    me = client.get("/users/me", cookies={"mixmini_auth": cookie})
    assert me.status_code == 200
    assert me.json()["email"] == email


# ---------------------------------------------------------------------------
# SQLAlchemy model sanity tests (sync engine, in-memory)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_paint_model(sync_session):
    paint = Paint(
        brand="Citadel",
        range="Base",
        name="Abaddon Black",
        hex="#231F20",
        paint_type="base",
    )
    sync_session.add(paint)
    sync_session.commit()

    result = sync_session.query(Paint).filter_by(name="Abaddon Black").first()
    assert result is not None
    assert result.brand == "Citadel"
    assert result.hex == "#231F20"


def test_paint_status_enum(sync_session):
    paint = Paint(brand="Test", range="Test", name="Test Paint", hex="#000000", paint_type="base")
    sync_session.add(paint)
    sync_session.flush()

    assert PaintStatus.full == "full"
    assert PaintStatus.low == "low"
    assert PaintStatus.empty == "empty"
