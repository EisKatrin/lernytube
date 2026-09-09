"""Router für Admin-Dashboard-Endpunkte.

Stellt einen per Shared-Secret geschützten Polling-Endpunkt bereit,
über den das zentrale Admin-Dashboard neu registrierte Mitglieder
und ihren Speicherverbrauch (manuell hochgeladene Snapshot-Bilder)
abfragen kann.
"""

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from database import get_db

router = APIRouter()

UPLOADS_DIR = "static/uploads"


def verify_dashboard_secret(x_dashboard_secret: str | None = Header(default=None)) -> None:
    """Prüft den Shared-Secret-Header gegen DASHBOARD_SHARED_SECRET.

    Nutzt einen zeitkonstanten Vergleich, um Timing-Angriffe zu verhindern.
    """
    expected = os.environ.get("DASHBOARD_SHARED_SECRET", "")
    if not expected or not x_dashboard_secret or not secrets.compare_digest(x_dashboard_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid dashboard secret")


def _parse_since(since: str | None) -> datetime:
    """Parst den optionalen ISO8601-since-Parameter.

    Bei fehlendem oder ungültigem Wert wird datetime.min zurückgegeben,
    sodass alle Benutzer zurückgegeben werden.
    """
    if not since:
        return datetime.min
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


async def _storage_bytes_for_user(db, user_id: str) -> int:
    """Berechnet die Summe der Dateigrößen manuell hochgeladener Snapshot-Bilder.

    Sessions und Snapshots werden über session_id verknüpft, da Snapshots
    keinen direkten user_id-Bezug garantieren (siehe routes/snapshots.py).
    """
    session_ids = [
        str(sess["_id"])
        async for sess in db.sessions.find({"user_id": user_id}, {"_id": 1})
    ]
    if not session_ids:
        return 0

    total = 0
    cursor = db.snapshots.find(
        {"session_id": {"$in": session_ids}, "frame_source": "manual"}
    )
    async for snap in cursor:
        path = os.path.join(UPLOADS_DIR, f"{snap['_id']}.jpg")
        try:
            total += os.path.getsize(path)
        except OSError:
            pass
    return total


@router.get("/new-members", dependencies=[Depends(verify_dashboard_secret)])
async def new_members(since: str | None = Query(default=None)):
    """Gibt alle seit `since` registrierten Benutzer inkl. Speicherverbrauch zurück.

    Args:
        since: Optionaler ISO8601-Zeitstempel. Ohne gültigen Wert werden
            alle Benutzer zurückgegeben.

    Returns:
        Liste von Objekten mit username, email, registered_at, storage_bytes,
        aufsteigend nach Registrierungsdatum sortiert.
    """
    db = get_db()
    since_dt = _parse_since(since)

    cursor = db.users.find({"created_at": {"$gt": since_dt}}).sort("created_at", 1)

    result = []
    async for user in cursor:
        created_at = user["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        storage_bytes = await _storage_bytes_for_user(db, str(user["_id"]))
        result.append({
            "username": user["username"],
            "email": user["email"],
            "registered_at": created_at.isoformat().replace("+00:00", "Z"),
            "storage_bytes": storage_bytes,
        })

    return result
