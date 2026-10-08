"""Integration-Tests für den Klassenzimmer-Proxy (/api/klassenzimmer/*).

Die eigentliche Lehrer-Logik läuft in der externen Lehrer-Engine —
hier wird nur geprüft, dass LernyTube korrekt authentifiziert,
den Username auflöst und Engine-Antworten/-Fehler durchreicht.
Gemockt wird die eigene _engine_request()-Funktion (Funktionsgrenze),
NICHT httpx.AsyncClient direkt — sonst fängt der Mock auch den
äußeren Test-HTTP-Client ab, der dieselbe httpx-Klasse nutzt.
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_db")]


class FakeEngineResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def mock_engine_request():
    with patch("routes.klassenzimmer._engine_request", new_callable=AsyncMock) as m:
        yield m


async def test_list_agents_proxy(client, auth_headers, mock_engine_request):
    mock_engine_request.return_value = FakeEngineResponse(
        200, [{"agent_id": "it-lehrer", "display_name": "IT-Lehrer", "kurzbeschreibung": "..."}]
    )
    resp = await client.get("/api/klassenzimmer/agents", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["agent_id"] == "it-lehrer"

    call = mock_engine_request.call_args
    assert call.args[:2] == ("GET", "/v1/agents")
    assert call.kwargs["params"]["app"] == "lernytube"


async def test_chat_proxy_leitet_antwort_durch(client, auth_headers, mock_engine_request):
    mock_engine_request.return_value = FakeEngineResponse(200, {"reply": "Hallo, ich bin dein Lehrer."})
    resp = await client.post(
        "/api/klassenzimmer/chat",
        json={"agent_id": "it-lehrer", "message": "Was ist ein Container?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Hallo, ich bin dein Lehrer."

    call = mock_engine_request.call_args
    assert call.args[:2] == ("POST", "/v1/chat")
    sent_body = call.kwargs["json"]
    assert sent_body["app"] == "lernytube"
    assert sent_body["agent_id"] == "it-lehrer"
    assert sent_body["mode"] == "stateful"
    assert sent_body["user_key"] == "testuser"  # Username aus registered_user-Fixture, nicht die Mongo-ID


async def test_chat_ohne_agent_id_422(client, auth_headers, mock_engine_request):
    resp = await client.post(
        "/api/klassenzimmer/chat", json={"message": "Hallo"}, headers=auth_headers
    )
    assert resp.status_code == 422
    mock_engine_request.assert_not_called()


async def test_chat_engine_403_wird_durchgereicht(client, auth_headers, mock_engine_request):
    mock_engine_request.return_value = FakeEngineResponse(403, {"detail": "Nicht freigeschaltet"})
    resp = await client.post(
        "/api/klassenzimmer/chat",
        json={"agent_id": "it-lehrer", "message": "Hallo"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


async def test_history_proxy(client, auth_headers, mock_engine_request):
    mock_engine_request.return_value = FakeEngineResponse(200, {"messages": []})
    resp = await client.get("/api/klassenzimmer/history", params={"agent_id": "it-lehrer"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


async def test_ohne_token_403(client):
    resp = await client.get("/api/klassenzimmer/agents")
    assert resp.status_code == 403


async def test_fehlende_engine_konfiguration_gibt_500(client, auth_headers, monkeypatch):
    """Ohne Mock der _engine_request: die echte Funktion muss selbst 500 liefern,
    wenn ENGINE_BASE_URL fehlt — ganz ohne Netzwerkaufruf."""
    monkeypatch.delenv("ENGINE_BASE_URL", raising=False)
    resp = await client.get("/api/klassenzimmer/agents", headers=auth_headers)
    assert resp.status_code == 500
