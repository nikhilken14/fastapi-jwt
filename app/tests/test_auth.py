"""
Integration tests hitting the real FastAPI app + a real (temporary,
in-memory) SQLite database - not mocks - so these tests exercise the
full register -> login -> access protected route -> refresh flow the
way a real client would.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.models.user import Base
from app.main import app


@pytest.fixture
async def client():
    """Provide an AsyncClient wired directly to the app, with a fresh
    (empty) database for every test - tests never affect each other."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_then_login(client):
    """A newly registered user can immediately log in and receive tokens."""
    r = await client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@example.com"

    r = await client.post("/auth/token", data={"username": "a@example.com", "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(client):
    """Registering the same email twice returns 409, not a 500 or silent overwrite."""
    await client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    r = await client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_wrong_password_rejected(client):
    """Logging in with the wrong password returns 401."""
    await client.post("/auth/register", json={"email": "b@example.com", "password": "password123"})
    r = await client.post("/auth/token", data={"username": "b@example.com", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    """Calling /users/me with no Authorization header is rejected."""
    r = await client.get("/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client):
    """A valid access token can read /users/me."""
    await client.post("/auth/register", json={"email": "c@example.com", "password": "password123"})
    login = await client.post("/auth/token", data={"username": "c@example.com", "password": "password123"})
    token = login.json()["access_token"]

    r = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "c@example.com"


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_route(client):
    """A regular user's token is rejected by an admin-only route with 403."""
    await client.post("/auth/register", json={"email": "d@example.com", "password": "password123"})
    login = await client.post("/auth/token", data={"username": "d@example.com", "password": "password123"})
    token = login.json()["access_token"]

    r = await client.get("/users/admin/all", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token_issues_new_access_token(client):
    """A valid refresh token yields a fresh token pair."""
    await client.post("/auth/register", json={"email": "e@example.com", "password": "password123"})
    login = await client.post("/auth/token", data={"username": "e@example.com", "password": "password123"})
    refresh_token = login.json()["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_access_token_rejected_by_refresh_endpoint(client):
    """An access token cannot be used where a refresh token is required."""
    await client.post("/auth/register", json={"email": "f@example.com", "password": "password123"})
    login = await client.post("/auth/token", data={"username": "f@example.com", "password": "password123"})
    access_token = login.json()["access_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert r.status_code == 401