"""Unit-Tests für die reinen Hilfsfunktionen des KI-Lehrers (routes/tutor.py).

Läuft ohne Datenbank und ohne echte Netzwerkaufrufe — die Anthropic-API
wird über httpx.AsyncClient.post gemockt.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routes.tutor import _ask_claude, _parse_tutor_response


class FakeAnthropicResponse:
    """Minimaler Stand-in für httpx.Response, wie er von _ask_claude genutzt wird."""

    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _content_response(text: str, status_code: int = 200) -> FakeAnthropicResponse:
    return FakeAnthropicResponse(status_code, {"content": [{"type": "text", "text": text}]})


class TestParseTutorResponse:
    """Das Modell muss zuverlässig JSON liefern — aber wenn nicht, darf nichts crashen."""

    def test_valides_json(self):
        text = '{"answer": "Die Antwort.", "topic_path": ["Mathe", "Algebra"]}'
        result = _parse_tutor_response(text)
        assert result == {"answer": "Die Antwort.", "topic_path": ["Mathe", "Algebra"]}

    def test_json_mit_umgebendem_text(self):
        text = 'Hier ist die Antwort:\n{"answer": "42", "topic_path": ["Zahlen"]}\nEnde.'
        result = _parse_tutor_response(text)
        assert result["answer"] == "42"
        assert result["topic_path"] == ["Zahlen"]

    def test_ungueltiges_json_faellt_zurueck(self):
        text = "Das ist kein JSON, nur Fließtext als Antwort."
        result = _parse_tutor_response(text)
        assert result["answer"] == text
        assert result["topic_path"] == ["Sonstiges"]

    def test_fehlende_felder_fallen_zurueck(self):
        text = '{"foo": "bar"}'
        result = _parse_tutor_response(text)
        assert result["topic_path"] == ["Sonstiges"]
        assert result["answer"]  # nie leer

    def test_leerer_topic_path_faellt_zurueck(self):
        text = '{"answer": "Antwort ohne Thema", "topic_path": []}'
        result = _parse_tutor_response(text)
        assert result["topic_path"] == ["Sonstiges"]

    def test_topic_path_wird_auf_zwei_ebenen_begrenzt(self):
        text = '{"answer": "Tief verschachtelt", "topic_path": ["A", "B", "C", "D"]}'
        result = _parse_tutor_response(text)
        assert result["topic_path"] == ["A", "B"]

    def test_leere_strings_im_topic_path_werden_entfernt(self):
        text = '{"answer": "x", "topic_path": ["  ", "Mathe"]}'
        result = _parse_tutor_response(text)
        assert result["topic_path"] == ["Mathe"]

    def test_leerer_text_faellt_zurueck(self):
        result = _parse_tutor_response("")
        assert result["topic_path"] == ["Sonstiges"]
        assert result["answer"] == "Keine Antwort erhalten."


@pytest.mark.asyncio
class TestAskClaude:
    """Prüft den Netzwerk-Aufruf gegen die Anthropic-API inkl. Fehlerfällen.

    Sicherheitsrelevant: Ohne konfigurierten Key darf niemals ein Request
    hinausgehen; ein Fehler der Upstream-API darf nicht als 200 durchgereicht
    werden und keine Rohdaten der Anfrage im Fehlertext offenlegen.
    """

    async def test_ohne_api_key_wird_kein_request_gesendet(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            with pytest.raises(HTTPException) as exc_info:
                await _ask_claude("Frage?", [])
        mock_post.assert_not_called()
        assert exc_info.value.status_code == 500

    async def test_upstream_fehler_wird_als_502_gemeldet(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = FakeAnthropicResponse(529, {})
            with pytest.raises(HTTPException) as exc_info:
                await _ask_claude("Frage?", [])
        assert exc_info.value.status_code == 502
        # Der Fehlertext darf nicht die rohe Upstream-Antwort/den Key enthalten
        assert "test-key" not in str(exc_info.value.detail)

    async def test_erfolgreiche_antwort_wird_korrekt_geparst(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        payload = _content_response('{"answer": "Die Antwort.", "topic_path": ["Mathe", "Algebra"]}')
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = payload
            result = await _ask_claude("Was ist Algebra?", ["Mathe > Geometrie"])
        assert result == {"answer": "Die Antwort.", "topic_path": ["Mathe", "Algebra"]}

    async def test_api_key_landet_nicht_im_prompt_oder_in_der_frage(self, monkeypatch):
        """Der Key darf ausschließlich als Header verschickt werden, nie im Body."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "super-secret-key")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _content_response('{"answer": "ok", "topic_path": ["X"]}')
            await _ask_claude("Frage?", [])
        _, kwargs = mock_post.call_args
        body = kwargs.get("json", {})
        assert "super-secret-key" not in str(body)
        assert kwargs["headers"]["x-api-key"] == "super-secret-key"

