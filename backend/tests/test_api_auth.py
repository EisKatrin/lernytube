"""Integration-Tests für Auth-Endpoints."""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


async def test_register_erfolgreich(client):
    resp = await client.post("/api/auth/register", json={
        "username": "neuuser",
        "email": "neu@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["username"] == "neuuser"


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


async def test_me_mit_token(client, auth_headers):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


async def test_me_ohne_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403
