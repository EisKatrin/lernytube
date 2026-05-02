"""Integration-Tests für Session-Endpoints."""

import pytest
from unittest.mock import patch, AsyncMock

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_db")]


@pytest.fixture
def mock_youtube():
    """Mockt die YouTube-API um keine echten Requests zu machen."""
    with patch("routes.sessions._fetch_video_info", new_callable=AsyncMock) as m:
        m.return_value = {"video_title": "Test Video", "channel_name": "Test Channel"}
        yield m


async def test_create_session(client, auth_headers, mock_youtube):
    resp = await client.post("/api/sessions/", json={
        "title": "Python Basics",
        "date": "2026-04-15",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "tags": ["python", "basics"],
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Python Basics"
    assert data["youtube_id"] == "dQw4w9WgXcQ"
    assert data["tags"] == ["python", "basics"]
    assert data["video_title"] == "Test Video"


async def test_list_sessions(client, auth_headers, mock_youtube):
    # Zwei Sessions erstellen
    for i in range(2):
        await client.post("/api/sessions/", json={
            "title": f"Session {i}",
            "date": "2026-04-15",
            "video_url": "https://youtu.be/dQw4w9WgXcQ",
        }, headers=auth_headers)

    resp = await client.get("/api/sessions/", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_session(client, auth_headers, mock_youtube):
    create_resp = await client.post("/api/sessions/", json={
        "title": "Test",
        "date": "2026-04-15",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
    }, headers=auth_headers)
    session_id = create_resp.json()["id"]

    resp = await client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test"


async def test_get_session_nicht_gefunden(client, auth_headers):
    resp = await client.get("/api/sessions/000000000000000000000000", headers=auth_headers)
    assert resp.status_code == 404


async def test_delete_session(client, auth_headers, mock_youtube):
    create_resp = await client.post("/api/sessions/", json={
        "title": "Zum Löschen",
        "date": "2026-04-15",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
    }, headers=auth_headers)
    session_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Sicherstellen dass Session weg ist
    resp = await client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 404


async def test_list_tags(client, auth_headers, mock_youtube):
    await client.post("/api/sessions/", json={
        "title": "Tagged",
        "date": "2026-04-15",
        "video_url": "https://youtu.be/dQw4w9WgXcQ",
        "tags": ["python", "api"],
    }, headers=auth_headers)

    resp = await client.get("/api/sessions/tags", headers=auth_headers)
    assert resp.status_code == 200
    tags = resp.json()
    assert "python" in tags
    assert "api" in tags


async def test_ungueltige_youtube_url(client, auth_headers):
    resp = await client.post("/api/sessions/", json={
        "title": "Bad URL",
        "date": "2026-04-15",
        "video_url": "https://example.com/not-youtube",
    }, headers=auth_headers)
    assert resp.status_code == 400
