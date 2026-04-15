"""
seed_demo.py – Demo-Daten für LernyTube

Erstellt einen Demo-User + 3 Lernsessions mit je mehreren Snapshots.
Läuft direkt auf dem VPS (außerhalb Docker) mit pymongo.

Aufruf: python3 seed_demo.py
"""

import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote_plus

from pymongo import MongoClient
from passlib.context import CryptContext

# ─── Konfiguration ────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB  = os.getenv("MONGO_DB", "lernytube_db")

DEMO_USER = {
    "username": os.getenv("DEMO_USERNAME", "demo"),
    "email":    os.getenv("DEMO_EMAIL", "demo@lernytube.de"),
    "password": os.getenv("DEMO_PASSWORD", "change-me"),
}

# 3 echte YouTube-Videos mit realistischen Lern-Inhalten
SESSIONS = [
    {
        "title":     "Python für Einsteiger – Vollständiger Kurs",
        "date":      "2026-04-01",
        "video_url": "https://www.youtube.com/watch?v=rfscVS0vtbw",
        "youtube_id":"rfscVS0vtbw",
        "tags":      ["python", "programmierung", "anfänger"],
        "video_title":   "Learn Python - Full Course for Beginners",
        "channel_name":  "freeCodeCamp.org",
        "snapshots": [
            {"timestamp_sec": 312,  "notes": "Variablen und Datentypen erklärt. int, float, str, bool – immer mit type() testen."},
            {"timestamp_sec": 847,  "notes": "Listen vs. Tupel: Liste ist veränderlich, Tupel nicht. Wichtig für Performance bei großen Datensätzen."},
            {"timestamp_sec": 1523, "notes": "For-Schleife mit range(): range(0, 10, 2) gibt [0,2,4,6,8]. Zweiter Parameter ist exklusiv!"},
            {"timestamp_sec": 2901, "notes": "Funktionen definieren mit def. *args und **kwargs für flexible Parameter – merken für spätere Projekte."},
        ],
    },
    {
        "title":     "SQL Grundlagen – Datenbankabfragen verstehen",
        "date":      "2026-04-02",
        "video_url": "https://www.youtube.com/watch?v=HXV3zeQKqGY",
        "youtube_id":"HXV3zeQKqGY",
        "tags":      ["sql", "datenbank", "backend"],
        "video_title":   "SQL Tutorial - Full Database Course for Beginners",
        "channel_name":  "freeCodeCamp.org",
        "snapshots": [
            {"timestamp_sec": 430,  "notes": "SELECT * ist langsam – immer nur die Spalten auswählen die man braucht!"},
            {"timestamp_sec": 1102, "notes": "WHERE vs HAVING: WHERE filtert Zeilen VOR GROUP BY, HAVING filtert Gruppen NACH GROUP BY."},
            {"timestamp_sec": 1988, "notes": "INNER JOIN zeigt nur Datensätze die in BEIDEN Tabellen vorhanden sind. LEFT JOIN nimmt alle aus der linken Tabelle."},
            {"timestamp_sec": 2640, "notes": "Index erstellen: CREATE INDEX idx_name ON tabelle(spalte); – macht Suche dramatisch schneller."},
            {"timestamp_sec": 3215, "notes": "Subquery-Beispiel: SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE total > 100)"},
        ],
    },
    {
        "title":     "CSS Flexbox & Grid – Modernes Layout meistern",
        "date":      "2026-04-03",
        "video_url": "https://www.youtube.com/watch?v=phWxA89Dy94",
        "youtube_id":"phWxA89Dy94",
        "tags":      ["css", "flexbox", "grid", "frontend"],
        "video_title":   "Flexbox CSS In 20 Minutes",
        "channel_name":  "Traversy Media",
        "snapshots": [
            {"timestamp_sec": 185,  "notes": "display: flex aktiviert Flexbox auf dem Container, nicht auf den Kindern! Kinder werden automatisch flex-items."},
            {"timestamp_sec": 412,  "notes": "justify-content: space-between – Lücken zwischen den Elementen. space-around – Lücken auch außen (halb so groß)."},
            {"timestamp_sec": 730,  "notes": "align-items vs align-content: align-items für einzeilige Container, align-content nur wenn flex-wrap aktiv ist."},
        ],
    },
]

# ─── Haupt-Logik ──────────────────────────────────────────────────────────────

def ts_label(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def main():
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    client  = MongoClient(MONGO_URI)
    db      = client[MONGO_DB]

    # ── Demo-User anlegen oder vorhandenen nutzen ──
    existing = db.users.find_one({"username": DEMO_USER["username"]})
    if existing:
        print(f"[INFO] User '{DEMO_USER['username']}' existiert bereits – bestehende Daten werden gelöscht und neu angelegt.")
        user_id_str = str(existing["_id"])
        # Alle Sessions + Snapshots des Users löschen
        session_ids = [str(s["_id"]) for s in db.sessions.find({"user_id": user_id_str})]
        if session_ids:
            db.snapshots.delete_many({"session_id": {"$in": session_ids}})
        db.sessions.delete_many({"user_id": user_id_str})
        db.users.delete_one({"_id": existing["_id"]})

    now = datetime.now(timezone.utc)
    user_doc = {
        "username":   DEMO_USER["username"],
        "email":      DEMO_USER["email"],
        "password":   pwd_ctx.hash(DEMO_USER["password"]),
        "created_at": now,
    }
    result   = db.users.insert_one(user_doc)
    user_id  = str(result.inserted_id)
    print(f"[OK] User '{DEMO_USER['username']}' angelegt (ID: {user_id})")

    # ── Sessions + Snapshots anlegen ──
    for sess in SESSIONS:
        session_doc = {
            "user_id":      user_id,
            "title":        sess["title"],
            "date":         sess["date"],
            "video_url":    sess["video_url"],
            "youtube_id":   sess["youtube_id"],
            "tags":         sess["tags"],
            "video_title":  sess.get("video_title"),
            "channel_name": sess.get("channel_name"),
            "created_at":   now,
        }
        s_result    = db.sessions.insert_one(session_doc)
        session_id  = str(s_result.inserted_id)

        snap_docs = []
        for snap in sess["snapshots"]:
            snap_docs.append({
                "session_id":    session_id,
                "timestamp_sec": snap["timestamp_sec"],
                "timestamp_label": ts_label(snap["timestamp_sec"]),
                "notes":         snap["notes"],
                "frame_url":     f"https://img.youtube.com/vi/{sess['youtube_id']}/maxresdefault.jpg",
                "frame_source":  "thumbnail",
                "created_at":    now,
            })
        db.snapshots.insert_many(snap_docs)

        # snapshot_count in Sessions-Collection aktualisieren
        db.sessions.update_one(
            {"_id": s_result.inserted_id},
            {"$set": {"snapshot_count": len(snap_docs)}}
        )
        print(f"[OK] Session '{sess['title']}' → {len(snap_docs)} Snapshots")

    client.close()
    print()
    print("─" * 50)
    print("Demo-Daten erfolgreich geladen!")
    print(f"  Login: {DEMO_USER['username']} / {DEMO_USER['password']}")
    print(f"  URL:   https://lernytube.eiskopani.de")
    print("─" * 50)


if __name__ == "__main__":
    main()
