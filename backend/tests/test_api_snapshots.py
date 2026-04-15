"""Integration-Tests für Snapshot-Endpoints."""

import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_youtube():
    with patch("routes.sessions._fetch_video_info", new_callable=AsyncMock) as m:
        m.return_value = {"video_title": "Test", "channel_name": "Channel"}
        yield m


async def _create_session(client, auth_headers, mock_youtube):
    """Helper: Erstellt eine Session und gibt die ID zurück."""
    resp = await client.post("/api/sessions/", json={
        "title": "Test Session",
        "date": "2026-04-15",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
    }, headers=auth_headers)
    return resp.json()["id"]


async def test_create_snapshot(client, auth_headers, mock_youtube):
    session_id = await _create_session(client, auth_headers, mock_youtube)
    resp = await client.post("/api/snapshots/", json={
        "session_id": session_id,
        "timestamp_sec": 120,
        "notes": "Wichtiger Punkt",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["timestamp_sec"] == 120
    assert data["timestamp_label"] == "2:00"
    assert data["notes"] == "Wichtiger Punkt"


async def test_list_snapshots(client, auth_headers, mock_youtube):
    session_id = await _create_session(client, auth_headers, mock_youtube)
    for ts in [60, 30, 90]:
        await client.post("/api/snapshots/", json={
            "session_id": session_id,
            "timestamp_sec": ts,
        }, headers=auth_headers)

    resp = await client.get(f"/api/snapshots/?session_id={session_id}", headers=auth_headers)
    assert resp.status_code == 200
    snaps = resp.json()
    assert len(snaps) == 3
    # Sortiert nach timestamp_sec
    assert snaps[0]["timestamp_sec"] <= snaps[1]["timestamp_sec"] <= snaps[2]["timestamp_sec"]


async def test_update_snapshot_notes(client, auth_headers, mock_youtube):
    session_id = await _create_session(client, auth_headers, mock_youtube)
    create_resp = await client.post("/api/snapshots/", json={
        "session_id": session_id,
        "timestamp_sec": 10,
        "notes": "Alt",
    }, headers=auth_headers)
    snap_id = create_resp.json()["id"]

    resp = await client.put(f"/api/snapshots/{snap_id}", json={
        "notes": "Aktualisiert",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Aktualisiert"


async def test_delete_snapshot(client, auth_headers, mock_youtube):
    session_id = await _create_session(client, auth_headers, mock_youtube)
    create_resp = await client.post("/api/snapshots/", json={
        "session_id": session_id,
        "timestamp_sec": 5,
    }, headers=auth_headers)
    snap_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/snapshots/{snap_id}", headers=auth_headers)
    assert resp.status_code == 204


async def test_search_snapshots(client, auth_headers, mock_youtube):
    session_id = await _create_session(client, auth_headers, mock_youtube)
    await client.post("/api/snapshots/", json={
        "session_id": session_id,
        "timestamp_sec": 10,
        "notes": "Python ist eine Programmiersprache",
    }, headers=auth_headers)
    await client.post("/api/snapshots/", json={
        "session_id": session_id,
        "timestamp_sec": 20,
        "notes": "JavaScript ist auch cool",
    }, headers=auth_headers)

    resp = await client.get("/api/snapshots/search?q=Python", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert "Python" in results[0]["notes"]


async def test_snapshot_ohne_session(client, auth_headers):
    resp = await client.post("/api/snapshots/", json={
        "session_id": "000000000000000000000000",
        "timestamp_sec": 10,
    }, headers=auth_headers)
    assert resp.status_code == 404
