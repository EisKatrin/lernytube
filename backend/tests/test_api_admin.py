"""Integration-Tests für den Admin-Dashboard-Endpoint /api/admin/new-members."""

import os

os.environ["DASHBOARD_SHARED_SECRET"] = "test-dashboard-secret"

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_db")]


async def test_new_members_ohne_secret(client):
    resp = await client.get("/api/admin/new-members")
    assert resp.status_code in (401, 422)  # 422 falls Header fehlt (FastAPI-Validierung)


async def test_new_members_falsches_secret(client):
    resp = await client.get(
        "/api/admin/new-members", headers={"X-Dashboard-Secret": "falsch"}
    )
    assert resp.status_code == 401


async def test_new_members_registrierter_user_erscheint(client):
    reg = await client.post("/api/auth/register", json={
        "username": "dashboarduser",
        "email": "dashboard@example.com",
        "password": "SehrSicheresPasswort!1",
    })
    assert reg.status_code == 201

    resp = await client.get(
        "/api/admin/new-members",
        headers={"X-Dashboard-Secret": "test-dashboard-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(u["username"] == "dashboarduser" for u in data)
    entry = next(u for u in data if u["username"] == "dashboarduser")
    assert entry["email"] == "dashboard@example.com"
    assert entry["registered_at"].endswith("Z")
    assert entry["storage_bytes"] == 0


async def test_new_members_since_filtert(client):
    await client.post("/api/auth/register", json={
        "username": "alterUser",
        "email": "alt@example.com",
        "password": "SehrSicheresPasswort!1",
    })

    resp = await client.get(
        "/api/admin/new-members",
        params={"since": "2099-01-01T00:00:00Z"},
        headers={"X-Dashboard-Secret": "test-dashboard-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
