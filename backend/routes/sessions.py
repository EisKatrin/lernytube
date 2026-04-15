"""Router für Lernsession-Endpunkte (CRUD + Tags).

Stellt Endpunkte zum Erstellen, Abrufen, Löschen
und Tag-Verwaltung von Lernsessions bereit.
"""

import os
import re
import httpx
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, status

from database import get_db
from models import SessionCreate, SessionOut
from auth_utils import get_current_user_id

router = APIRouter()

# Regex-Muster zum Extrahieren der YouTube-Video-ID
_YT_PATTERNS = [
    r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
]


def _extract_youtube_id(url: str) -> str:
    """Extrahiert die 11-stellige YouTube-Video-ID aus verschiedenen URL-Formaten.

    Unterstützt: youtube.com/watch?v=..., youtu.be/..., /embed/..., /shorts/...

    Args:
        url: Die YouTube-Video-URL oder direkte Video-ID.

    Returns:
        Die 11-stellige YouTube-Video-ID.

    Raises:
        HTTPException 400: Bei ungültiger oder nicht erkannter YouTube-URL.
    """
    for pattern in _YT_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise HTTPException(status_code=400, detail="Ungültige YouTube-URL — bitte vollständige URL einfügen")


def _clean_tags(tags: list[str]) -> list[str]:
    """Bereinigt und dedupliziert eine Tag-Liste.

    Entfernt Leerzeichen, leere Strings und Duplikate.
    Begrenzt auf maximal 8 Tags pro Session.

    Args:
        tags: Die rohe Tag-Liste.

    Returns:
        Bereinigte, deduplizierte Tag-Liste (max. 8 Einträge).
    """
    seen = []
    for tag in tags:
        cleaned = tag.strip()[:50]
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:8]


async def _fetch_video_info(video_id: str) -> dict:
    """Ruft Videotitel und Kanalname von der YouTube Data API v3 ab."""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return {}
    url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet&id={video_id}&key={api_key}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return {}
            snippet = items[0].get("snippet", {})
            return {
                "video_title": snippet.get("title"),
                "channel_name": snippet.get("channelTitle"),
            }
    except Exception:
        return {}


def _session_to_out(session: dict, snapshot_count: int = 0) -> SessionOut:
    """Konvertiert ein MongoDB-Sessiondokument in ein SessionOut-Modell.

    Args:
        session: Das rohe MongoDB-Dokument.
        snapshot_count: Anzahl der zugehörigen Snapshots.

    Returns:
        Ein SessionOut-Modell.
    """
    return SessionOut(
        id=str(session["_id"]),
        user_id=session["user_id"],
        title=session["title"],
        date=session["date"],
        video_url=session["video_url"],
        youtube_id=session["youtube_id"],
        tags=session.get("tags", []),
        snapshot_count=snapshot_count,
        video_title=session.get("video_title"),
        channel_name=session.get("channel_name"),
        created_at=session["created_at"],
    )


@router.get("/tags", response_model=list[str])
async def list_user_tags(user_id: str = Depends(get_current_user_id)):
    """Gibt alle einzigartigen Tags zurück, die der Benutzer bisher verwendet hat.

    Nützlich für Autovervollständigung und die Filterleiste im Dashboard.

    Args:
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Alphabetisch sortierte Liste aller einzigartigen Tags des Benutzers.
    """
    db = get_db()
    tags = await db.sessions.distinct("tags", {"user_id": user_id})
    return sorted(tags)


@router.get("/", response_model=list[SessionOut])
async def list_sessions(user_id: str = Depends(get_current_user_id)):
    """Gibt alle Lernsessions des angemeldeten Benutzers zurück (neueste zuerst).

    Args:
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Liste aller Sessions mit Snapshot-Anzahl und Tags.
    """
    db = get_db()
    cursor = db.sessions.find({"user_id": user_id}).sort("created_at", -1)
    sessions = []
    async for session in cursor:
        count = await db.snapshots.count_documents({"session_id": str(session["_id"])})
        sessions.append(_session_to_out(session, count))
    return sessions


@router.post("/", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(data: SessionCreate, user_id: str = Depends(get_current_user_id)):
    """Erstellt eine neue Lernsession mit YouTube-Video und optionalen Tags.

    Args:
        data: Titel, Datum, YouTube-URL und optionale Tags der neuen Session.
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Die neu erstellte Session.
    """
    db = get_db()
    youtube_id = _extract_youtube_id(data.video_url)
    video_info = await _fetch_video_info(youtube_id)
    session_doc = {
        "user_id": user_id,
        "title": data.title,
        "date": data.date,
        "video_url": data.video_url,
        "youtube_id": youtube_id,
        "tags": _clean_tags(data.tags),
        "video_title": video_info.get("video_title"),
        "channel_name": video_info.get("channel_name"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.sessions.insert_one(session_doc)
    session_doc["_id"] = result.inserted_id
    return _session_to_out(session_doc)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Gibt eine einzelne Lernsession anhand ihrer ID zurück.

    Args:
        session_id: Die MongoDB-ID der Session.
        user_id: Die Benutzer-ID aus dem JWT-Token (Zugriffsprüfung).

    Returns:
        Die angeforderte Session.

    Raises:
        HTTPException 404: Wenn die Session nicht existiert oder nicht dem Benutzer gehört.
    """
    db = get_db()
    session = await db.sessions.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    count = await db.snapshots.count_documents({"session_id": session_id})
    return _session_to_out(session, count)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Löscht eine Lernsession und alle zugehörigen Snapshots.

    Args:
        session_id: Die MongoDB-ID der zu löschenden Session.
        user_id: Die Benutzer-ID aus dem JWT-Token (Zugriffsprüfung).

    Raises:
        HTTPException 404: Wenn die Session nicht gefunden wird.
    """
    db = get_db()
    result = await db.sessions.delete_one({"_id": ObjectId(session_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    # Alle zugehörigen Snapshots ebenfalls löschen
    await db.snapshots.delete_many({"session_id": session_id})
