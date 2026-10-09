"""Integration-Tests für Auth-Endpoints."""

import pytest
import pytest_asyncio

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_db")]


async def test_register_erfolgreich(client, mock_db):
    resp = await client.post("/api/auth/register", json={
        "username": "neuuser",
        "email": "neu@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" not in data
    assert data["email"] == "neu@example.com"

    user = await mock_db.users.find_one({"username": "neuuser"})
    assert user["email_verified"] is False
    assert user["verification_token"]


async def test_register_duplikat_username(client, registered_user):
    resp = await client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "andere@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    assert resp.status_code == 409


async def test_register_schwaches_passwort(client):
    resp = await client.post("/api/auth/register", json={
        "username": "neuuser",
        "email": "neu@example.com",
        "password": "schwach",
    })
    assert resp.status_code == 422


async def test_login_erfolgreich(client, registered_user):
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "MeinTestPasswort!1",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_falsches_passwort(client, registered_user):
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "FalschesPasswort!123",
    })
    assert resp.status_code == 401


async def test_login_unbekannter_user(client):
    resp = await client.post("/api/auth/login", json={
        "username": "gibtsNicht",
        "password": "EgalWasHier!12345",
    })
    assert resp.status_code == 401


async def test_login_vor_bestaetigung_blockiert(client):
    await client.post("/api/auth/register", json={
        "username": "unbestaetigt",
        "email": "unbestaetigt@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "unbestaetigt",
        "password": "SehrSicheresPasswort!1",
    })
    assert resp.status_code == 403


async def test_verify_email_erfolgreich(client, mock_db):
    await client.post("/api/auth/register", json={
        "username": "zuverifizieren",
        "email": "zuverifizieren@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    user = await mock_db.users.find_one({"username": "zuverifizieren"})
    token = user["verification_token"]

    resp = await client.get(f"/api/auth/verify-email?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "email_verified=1" in resp.headers["location"]

    login_resp = await client.post("/api/auth/login", json={
        "username": "zuverifizieren",
        "password": "SehrSicheresPasswort!1",
    })
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["email_verified"] is True


async def test_verify_email_ungueltiges_token(client):
    resp = await client.get("/api/auth/verify-email?token=nicht-existent", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "verify_error=invalid" in resp.headers["location"]


async def test_me_mit_token(client, auth_headers):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


async def test_me_ohne_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403
