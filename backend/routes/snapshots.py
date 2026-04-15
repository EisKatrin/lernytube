"""Router für Snapshot-Endpunkte (CRUD + Suche).

Stellt Endpunkte zum Erstellen, Abrufen, Aktualisieren,
Löschen und Durchsuchen von Video-Snapshots bereit.
"""

import base64
import os
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Query, status

from database import get_db
from models import SnapshotCreate, SnapshotUpdate, SnapshotOut, SnapshotSearchResult
from auth_utils import get_current_user_id

router = APIRouter()

FRAMES_DIR = "static/frames"
UPLOADS_DIR = "static/uploads"


def _format_timestamp(seconds: int) -> str:
    """Konvertiert eine Sekundenanzahl in ein lesbares Zeitformat."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _snapshot_to_out(snap: dict) -> SnapshotOut:
    """Konvertiert ein MongoDB-Snapshot-Dokument in ein SnapshotOut-Modell."""
    return SnapshotOut(
        id=str(snap["_id"]),
        session_id=snap["session_id"],
        timestamp_sec=snap["timestamp_sec"],
        timestamp_label=snap["timestamp_label"],
        notes=snap["notes"],
        frame_url=snap.get("frame_url"),
        frame_source=snap.get("frame_source"),
        created_at=snap["created_at"],
    )


@router.get("/", response_model=list[SnapshotOut])
async def list_snapshots(
    session_id: str = Query(..., description="ID der Session"),
    user_id: str = Depends(get_current_user_id),
):
    """Gibt alle Snapshots einer Lernsession zurück (nach Zeitstempel sortiert)."""
    db = get_db()
    session = await db.sessions.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    cursor = db.snapshots.find({"session_id": session_id}).sort("timestamp_sec", 1)
    return [_snapshot_to_out(snap) async for snap in cursor]


@router.get("/search", response_model=list[SnapshotSearchResult])
async def search_snapshots(
    q: str = Query(..., min_length=1, description="Suchbegriff in Snapshot-Notizen"),
    user_id: str = Depends(get_current_user_id),
):
    """Durchsucht alle Snapshot-Notizen des Benutzers nach einem Suchbegriff."""
    db = get_db()
    cursor = db.snapshots.find(
        {"user_id": user_id, "notes": {"$regex": q, "$options": "i"}}
    ).sort("created_at", -1).limit(50)

    results = []
    async for snap in cursor:
        session = await db.sessions.find_one({"_id": ObjectId(snap["session_id"])})
        if session:
            results.append(SnapshotSearchResult(
                id=str(snap["_id"]),
                session_id=snap["session_id"],
                session_title=session["title"],
                session_youtube_id=session["youtube_id"],
                timestamp_sec=snap["timestamp_sec"],
                timestamp_label=snap["timestamp_label"],
                notes=snap["notes"],
                created_at=snap["created_at"],
            ))
    return results


@router.post("/", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
async def create_snapshot(data: SnapshotCreate, user_id: str = Depends(get_current_user_id)):
    """Erstellt einen neuen Snapshot."""
    db = get_db()
    session = await db.sessions.find_one({"_id": ObjectId(data.session_id), "user_id": user_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    snap_doc = {
        "session_id": data.session_id,
        "user_id": user_id,
        "timestamp_sec": data.timestamp_sec,
        "timestamp_label": _format_timestamp(data.timestamp_sec),
        "notes": data.notes,
        "frame_url": None,
        "frame_source": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.snapshots.insert_one(snap_doc)
    snap_doc["_id"] = result.inserted_id
    snapshot_id = str(result.inserted_id)

    # Externe Thumbnail-URL direkt speichern (z.B. YouTube)
    if data.frame_url and not data.frame_data:
        await db.snapshots.update_one(
            {"_id": result.inserted_id},
            {"$set": {"frame_url": data.frame_url, "frame_source": "thumbnail"}},
        )
        snap_doc["frame_url"] = data.frame_url
        snap_doc["frame_source"] = "thumbnail"

    # Frame-Bild direkt speichern wenn vom Client mitgesendet
    if data.frame_data:
        try:
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            img_bytes = base64.b64decode(data.frame_data)
            output_path = f"{UPLOADS_DIR}/{snapshot_id}.jpg"
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            frame_url = f"/static/uploads/{snapshot_id}.jpg"
            await db.snapshots.update_one(
                {"_id": result.inserted_id},
                {"$set": {"frame_url": frame_url, "frame_source": "manual"}},
            )
            snap_doc["frame_url"] = frame_url
            snap_doc["frame_source"] = "manual"
        except Exception:
            pass

    return _snapshot_to_out(snap_doc)


@router.put("/{snapshot_id}", response_model=SnapshotOut)
async def update_snapshot(
    snapshot_id: str,
    data: SnapshotUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Aktualisiert die Notizen eines bestehenden Snapshots."""
    db = get_db()
    result = await db.snapshots.find_one_and_update(
        {"_id": ObjectId(snapshot_id), "user_id": user_id},
        {"$set": {"notes": data.notes}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")
    return _snapshot_to_out(result)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(snapshot_id: str, user_id: str = Depends(get_current_user_id)):
    """Löscht einen einzelnen Snapshot und sein Frame-Bild."""
    db = get_db()
    snap = await db.snapshots.find_one({"_id": ObjectId(snapshot_id), "user_id": user_id})
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    await db.snapshots.delete_one({"_id": ObjectId(snapshot_id)})

    # Manuell hochgeladenes Bild löschen
    if snap.get("frame_source") == "manual":
        upload_path = f"{UPLOADS_DIR}/{snapshot_id}.jpg"
        if os.path.exists(upload_path):
            os.remove(upload_path)

    # Legacy frames-Verzeichnis aufräumen
    frame_path = f"{FRAMES_DIR}/{snapshot_id}.jpg"
    if os.path.exists(frame_path):
        os.remove(frame_path)


@router.post("/{snapshot_id}/upload-frame", response_model=SnapshotOut)
async def upload_frame(
    snapshot_id: str,
    data: dict,
    user_id: str = Depends(get_current_user_id),
):
    """Speichert einen manuell eingefügten Screenshot (Base64-JPEG) zu einem Snapshot.

    Args:
        snapshot_id: Die MongoDB-ID des Snapshots.
        data: Dictionary mit frame_data (Base64-JPEG-String).
        user_id: Die Benutzer-ID aus dem JWT-Token.

    Returns:
        Der aktualisierte Snapshot mit frame_url und frame_source=manual.
    """
    db = get_db()
    snap = await db.snapshots.find_one({"_id": ObjectId(snapshot_id), "user_id": user_id})
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    frame_data = data.get("frame_data")
    if not frame_data:
        raise HTTPException(status_code=400, detail="Kein frame_data übergeben")

    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        img_bytes = base64.b64decode(frame_data)
        output_path = f"{UPLOADS_DIR}/{snapshot_id}.jpg"
        with open(output_path, "wb") as f_out:
            f_out.write(img_bytes)
        frame_url = f"/static/uploads/{snapshot_id}.jpg"
        snap = await db.snapshots.find_one_and_update(
            {"_id": ObjectId(snapshot_id)},
            {"$set": {"frame_url": frame_url, "frame_source": "manual"}},
            return_document=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Frame-Speicherung fehlgeschlagen: {e}")

    return _snapshot_to_out(snap)
