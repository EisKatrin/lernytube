"""Router für das Klassenzimmer: Chat mit den Lehrer-Agenten der Lehrer-Engine.

Dünner Proxy — die eigentliche Chat-Logik (Steckbriefe, Claude-Aufruf,
Gesprächsverlauf, Lernstand) lebt in der zentralen Lehrer-Engine
(/docker/lehrer-engine/), die auch von der Bewerbungsmappe genutzt
wird. Dieser Router löst nur die bereits authentifizierte LernyTube-
Identität auf und leitet an die Engine weiter.

Das bestehende /lernbuch-Feature (routes/tutor.py) bleibt davon
komplett unberührt.
"""

import os

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_db
from auth_utils import get_current_user_id

router = APIRouter()

APP_NAME = "lernytube"


async def _resolve_username(user_id: str) -> str:
    """Löst die Lehrer-Engine-Identität (Username) aus der JWT-User-ID auf.

    Die Engine kennt LernyTubes Mongo-ObjectIds nicht — sie arbeitet mit
    einem stabilen, lesbaren user_key (dem Username), genau wie schon
    TUTOR_ALLOWED_USERNAME in routes/tutor.py.
    """
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return user["username"]


def _engine_headers() -> dict:
    secret = os.environ.get("ENGINE_SHARED_SECRET", "")
    return {"X-Engine-Secret": secret}


def _engine_base_url() -> str:
    return os.environ.get("ENGINE_BASE_URL", "").rstrip("/")


async def _engine_request(method: str, path: str, **kwargs) -> httpx.Response:
    """Führt eine Anfrage an die Lehrer-Engine aus und übersetzt Netzwerkfehler in 502."""
    base_url = _engine_base_url()
    if not base_url:
        raise HTTPException(status_code=500, detail="Klassenzimmer ist nicht konfiguriert")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await client.request(method, f"{base_url}{path}", headers=_engine_headers(), **kwargs)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Klassenzimmer-Dienst nicht erreichbar")


@router.get("/agents")
async def list_agents(user_id: str = Depends(get_current_user_id)):
    """Gibt die für LernyTube freigegebenen Lehrer zurück (Auswahl-Kacheln)."""
    await _resolve_username(user_id)  # stellt sicher, dass der Benutzer existiert
    resp = await _engine_request("GET", "/v1/agents", params={"app": APP_NAME})
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Lehrer-Liste nicht verfügbar")
    return resp.json()


@router.post("/chat")
async def chat(data: dict, user_id: str = Depends(get_current_user_id)):
    """Schickt eine Nachricht an den gewählten Lehrer und gibt die Antwort zurück.

    Args:
        data: Body mit mindestens `agent_id` (str) und `message` (str).
        user_id: Die Benutzer-ID aus dem JWT-Token.
    """
    agent_id = data.get("agent_id")
    message = data.get("message")
    if not agent_id or not message:
        raise HTTPException(status_code=422, detail="agent_id und message sind erforderlich")

    username = await _resolve_username(user_id)
    resp = await _engine_request(
        "POST",
        "/v1/chat",
        json={
            "app": APP_NAME,
            "user_key": username,
            "agent_id": agent_id,
            "mode": "stateful",
            "message": message,
        },
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Fehler im Klassenzimmer"))
    return resp.json()


@router.get("/history")
async def get_history(agent_id: str = Query(...), user_id: str = Depends(get_current_user_id)):
    """Gibt den bisherigen Gesprächsverlauf mit einem Lehrer zurück."""
    username = await _resolve_username(user_id)
    resp = await _engine_request(
        "GET", "/v1/history", params={"app": APP_NAME, "user_key": username, "agent_id": agent_id}
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Verlauf nicht verfügbar")
    return resp.json()


@router.get("/lernstand")
async def get_lernstand(agent_id: str = Query(...), user_id: str = Depends(get_current_user_id)):
    """Gibt den aktuellen Lernstand für einen Lehrer zurück."""
    username = await _resolve_username(user_id)
    resp = await _engine_request(
        "GET", "/v1/lernstand", params={"app": APP_NAME, "user_key": username, "agent_id": agent_id}
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Lernstand nicht verfügbar")
    return resp.json()
