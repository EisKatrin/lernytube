"""Integration-Tests für den KI-Lehrer / das Lernbuch (/api/tutor/*).

Deckt sowohl den fachlichen Ablauf (Frage -> Antwort -> Einsortierung in
den Themenbaum) als auch die Zugriffskontrolle ab: Diese Funktion ist
bewusst nur einem einzigen, freigeschalteten Benutzer zugänglich, und
niemand darf über die Entry-ID an Lernbuch-Einträge eines anderen
Benutzers kommen.
"""

import os

os.environ["TUTOR_ALLOWED_USERNAME"] = "testuser"

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from auth_utils import create_token, hash_password

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("mock_db")]


@pytest.fixture
def mock_ask_claude():
    """Mockt den Anthropic-Call, damit Tests ohne echten API-Key/Netzwerk laufen."""
    with patch("routes.tutor._ask_claude", new_callable=AsyncMock) as m:
        m.return_value = {"answer": "Das ist die Antwort.", "topic_path": ["Mathe", "Algebra"]}
        yield m


@pytest_asyncio.fixture
async def other_user_headers(mock_db):
    """Ein zweiter, NICHT freigeschalteter Benutzer — für Zugriffs-/IDOR-Tests."""
    user_doc = {
        "username": "anderer_nutzer",
        "email": "other@example.com",
        "password_hash": hash_password("EinAnderesPasswort!1"),
        "created_at": datetime.now(timezone.utc),
        "tos_accepted": False,
    }
    result = await mock_db.users.insert_one(user_doc)
    token = create_token(str(result.inserted_id))
    return {"Authorization": f"Bearer {token}"}


# ─── Grundfunktion: Frage stellen & automatisch einsortieren ────────────────

async def test_ask_erstellt_eintrag_und_thema(client, auth_headers, mock_ask_claude):
    resp = await client.post("/api/tutor/ask", json={"question": "Was ist Algebra?"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["question"] == "Was ist Algebra?"
    assert data["answer"] == "Das ist die Antwort."
    assert data["topic_path"] == ["Mathe", "Algebra"]
    assert data["topic_id"]


async def test_ask_wiederverwendet_bestehendes_thema(client, auth_headers, mock_ask_claude):
    await client.post("/api/tutor/ask", json={"question": "Frage 1"}, headers=auth_headers)
    resp = await client.post("/api/tutor/ask", json={"question": "Frage 2"}, headers=auth_headers)
    assert resp.status_code == 201

    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    mathe_nodes = [t for t in book if t["title"] == "Mathe"]
    assert len(mathe_nodes) == 1  # keine Themen-Duplikate
    assert len(mathe_nodes[0]["children"]) == 1
    assert mathe_nodes[0]["children"][0]["title"] == "Algebra"
    assert len(mathe_nodes[0]["children"][0]["entries"]) == 2


async def test_ask_case_insensitive_wiederverwendung(client, auth_headers, mock_ask_claude):
    await client.post("/api/tutor/ask", json={"question": "Frage 1"}, headers=auth_headers)
    mock_ask_claude.return_value = {"answer": "Zweite Antwort", "topic_path": ["mathe", "ALGEBRA"]}
    await client.post("/api/tutor/ask", json={"question": "Frage 2"}, headers=auth_headers)

    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    assert len(book) == 1  # kein zweites "mathe"-Oberthema
    assert len(book[0]["children"]) == 1  # kein zweites "ALGEBRA"-Unterthema
    assert len(book[0]["children"][0]["entries"]) == 2


async def test_ask_legt_neues_thema_fuer_anderes_gebiet_an(client, auth_headers, mock_ask_claude):
    await client.post("/api/tutor/ask", json={"question": "Frage 1"}, headers=auth_headers)
    mock_ask_claude.return_value = {"answer": "Geschichtsantwort", "topic_path": ["Geschichte"]}
    await client.post("/api/tutor/ask", json={"question": "Was war 1989?"}, headers=auth_headers)

    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    titles = {t["title"] for t in book}
    assert titles == {"Mathe", "Geschichte"}


async def test_book_ist_leer_ohne_eintraege(client, auth_headers):
    resp = await client.get("/api/tutor/book", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_delete_entry(client, auth_headers, mock_ask_claude):
    create = await client.post("/api/tutor/ask", json={"question": "Frage"}, headers=auth_headers)
    entry_id = create.json()["id"]

    resp = await client.delete(f"/api/tutor/entries/{entry_id}", headers=auth_headers)
    assert resp.status_code == 204

    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    assert book[0]["children"][0]["entries"] == []


async def test_delete_unbekannter_eintrag_404(client, auth_headers):
    resp = await client.delete("/api/tutor/entries/000000000000000000000000", headers=auth_headers)
    assert resp.status_code == 404


# ─── Eingabevalidierung ──────────────────────────────────────────────────────

async def test_frage_zu_kurz_wird_abgelehnt(client, auth_headers):
    resp = await client.post("/api/tutor/ask", json={"question": "Hi"}, headers=auth_headers)
    assert resp.status_code == 422


async def test_frage_zu_lang_wird_abgelehnt(client, auth_headers):
    resp = await client.post("/api/tutor/ask", json={"question": "x" * 2001}, headers=auth_headers)
    assert resp.status_code == 422


async def test_frage_fehlt_ganz(client, auth_headers):
    resp = await client.post("/api/tutor/ask", json={}, headers=auth_headers)
    assert resp.status_code == 422


# ─── Sicherheit: Zugriffskontrolle & Datenisolation ─────────────────────────

async def test_ohne_token_verweigert(client):
    resp = await client.post("/api/tutor/ask", json={"question": "Frage?"})
    assert resp.status_code == 403  # HTTPBearer ohne Header


async def test_nicht_freigeschalteter_user_bekommt_403_bei_ask(client, other_user_headers):
    resp = await client.post("/api/tutor/ask", json={"question": "Frage?"}, headers=other_user_headers)
    assert resp.status_code == 403


async def test_nicht_freigeschalteter_user_bekommt_403_bei_book(client, other_user_headers):
    resp = await client.get("/api/tutor/book", headers=other_user_headers)
    assert resp.status_code == 403


async def test_nicht_freigeschalteter_user_bekommt_403_bei_delete(client, other_user_headers):
    resp = await client.delete("/api/tutor/entries/000000000000000000000000", headers=other_user_headers)
    assert resp.status_code == 403


async def test_anderer_user_kann_fremden_eintrag_nicht_loeschen(
    client, auth_headers, other_user_headers, mock_ask_claude, monkeypatch
):
    """IDOR-Check: Selbst wenn ein zweiter Account irgendwann freigeschaltet würde,
    darf er nie über die Entry-ID an Einträge eines anderen Benutzers kommen —
    die Löschung muss zusätzlich am user_id-Filter scheitern."""
    create = await client.post("/api/tutor/ask", json={"question": "Frage"}, headers=auth_headers)
    entry_id = create.json()["id"]

    monkeypatch.setenv("TUTOR_ALLOWED_USERNAME", "anderer_nutzer")
    resp = await client.delete(f"/api/tutor/entries/{entry_id}", headers=other_user_headers)
    assert resp.status_code == 404  # nicht gefunden, weil user_id nicht passt — kein Fremdzugriff

    monkeypatch.setenv("TUTOR_ALLOWED_USERNAME", "testuser")
    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    assert len(book[0]["children"][0]["entries"]) == 1  # Eintrag ist noch da


async def test_kein_api_key_konfiguriert_gibt_500_ohne_leak(client, auth_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = await client.post("/api/tutor/ask", json={"question": "Frage ohne Key?"}, headers=auth_headers)
    assert resp.status_code == 500
    assert "API_KEY" not in resp.text  # kein Variablenname/Key im Response-Body


async def test_upstream_fehler_der_ki_wird_nicht_als_erfolg_gespeichert(client, auth_headers, monkeypatch):
    """Wenn die Anthropic-API fehlschlägt, darf kein Lernbuch-Eintrag entstehen."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with patch("routes.tutor._ask_claude", new_callable=AsyncMock) as mock_ask:
        from fastapi import HTTPException
        mock_ask.side_effect = HTTPException(status_code=502, detail="KI-Lehrer nicht erreichbar")
        resp = await client.post("/api/tutor/ask", json={"question": "Frage?"}, headers=auth_headers)
    assert resp.status_code == 502

    book = (await client.get("/api/tutor/book", headers=auth_headers)).json()
    assert book == []
