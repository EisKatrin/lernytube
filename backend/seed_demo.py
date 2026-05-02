#!/usr/bin/env python3
"""Seed-Skript: Erstellt einen Demo-User mit 3 Sessions und 16 Snapshots.

Nutzung:
    python3 seed_demo.py              # Erstellt alles neu
    python3 seed_demo.py --reset      # Löscht vorhandene Demo-Daten und erstellt neu
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from passlib.context import CryptContext

# ── Konfiguration ────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "lernytube_db")

DEMO_USER = {
    "username": "demo",
    "email": "demo@lernytube.de",
    "password": os.getenv("DEMO_PASSWORD", "changeme"),
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────

def fmt_ts(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


def yt_thumb(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


# ── Demo-Daten ───────────────────────────────────────────────────────────────

SESSIONS = [
    {
        "title": "Python Grundlagen – Variablen & Datentypen",
        "date": "2026-04-01",
        "video_url": "https://www.youtube.com/watch?v=kqtD5dpn9C8",
        "youtube_id": "kqtD5dpn9C8",
        "tags": ["Python", "Anfänger", "Grundlagen", "Programmieren"],
        "video_title": "Python Tutorial - Python Full Course for Beginners",
        "channel_name": "Programming with Mosh",
        "snapshots": [
            {
                "timestamp_sec": 180,
                "notes": (
                    "**Was ist eine Variable?** – Variablen sind wie beschriftete Boxen "
                    "im Speicher. Name links, Wert rechts: `preis = 10`. Python erkennt "
                    "den Typ automatisch (dynamische Typisierung)."
                ),
            },
            {
                "timestamp_sec": 540,
                "notes": (
                    "**Strings** – Text in einfachen oder doppelten Anführungszeichen. "
                    "Wichtig: `len()` gibt die Länge zurück, Zugriff auf einzelne Zeichen "
                    "mit `name[0]`. Negative Indizes zählen von hinten: `name[-1]`."
                ),
            },
            {
                "timestamp_sec": 900,
                "notes": (
                    "**Zahlentypen: int vs float** – `10` ist int, `10.5` ist float. "
                    "Division `/` ergibt immer float! Für ganzzahlige Division `//` "
                    "verwenden. Achtung: `10 / 3 = 3.333...`, aber `10 // 3 = 3`."
                ),
            },
            {
                "timestamp_sec": 1320,
                "notes": (
                    "**Type Conversion** – `int(\"10\")` wandelt String zu Integer, "
                    "`str(42)` umgekehrt. Typischer Fehler: `input()` gibt IMMER einen "
                    "String zurück → `int(input(\"Alter: \"))` nötig für Rechnungen."
                ),
            },
            {
                "timestamp_sec": 1680,
                "notes": (
                    "**Boolean & Vergleiche** – `True`/`False` (Großschreibung!). "
                    "Vergleichsoperatoren: `==`, `!=`, `>`, `<`. Ergebnis ist immer bool. "
                    "Leerer String, `0` und `None` sind \"falsy\"."
                ),
            },
            {
                "timestamp_sec": 2100,
                "notes": (
                    "**F-Strings (ab Python 3.6)** – "
                    "`f\"Hallo {name}, du bist {alter} Jahre alt\"`. "
                    "Viel besser lesbar als Konkatenation mit `+`. Auch Ausdrücke möglich: "
                    "`f\"Summe: {2+3}\"` → `\"Summe: 5\"`."
                ),
            },
        ],
    },
    {
        "title": "CSS Flexbox – Layout Schritt für Schritt",
        "date": "2026-04-03",
        "video_url": "https://www.youtube.com/watch?v=phWxA89Dy94",
        "youtube_id": "phWxA89Dy94",
        "tags": ["CSS", "Flexbox", "Layout", "Webdesign"],
        "video_title": "Learn Flexbox CSS in 8 minutes",
        "channel_name": "Slaying The Dragon",
        "snapshots": [
            {
                "timestamp_sec": 45,
                "notes": (
                    "**Flex-Container aktivieren** – `display: flex` auf dem Eltern-Element. "
                    "Sofort werden alle direkten Kinder zu Flex-Items und nebeneinander "
                    "angeordnet. Standard-Richtung: horizontal (row)."
                ),
            },
            {
                "timestamp_sec": 130,
                "notes": (
                    "**justify-content** – Verteilung entlang der Hauptachse. "
                    "`center` = mittig, `space-between` = erster links, letzter rechts, "
                    "Rest gleichmäßig. `space-around` gibt auch außen halben Abstand."
                ),
            },
            {
                "timestamp_sec": 240,
                "notes": (
                    "**align-items** – Ausrichtung auf der Kreuzachse (vertikal bei row). "
                    "`center` = vertikal zentriert, `stretch` = volle Höhe (Standard!). "
                    "Perfekte Zentrierung: `justify-content: center` + `align-items: center`."
                ),
            },
            {
                "timestamp_sec": 350,
                "notes": (
                    "**flex-direction: column** – Hauptachse wird vertikal! Dann dreht sich "
                    "alles: `justify-content` wirkt jetzt vertikal, `align-items` horizontal. "
                    "Merke: Vergleich row vs column nebeneinander skizzieren."
                ),
            },
            {
                "timestamp_sec": 450,
                "notes": (
                    "**flex-wrap & gap** – `flex-wrap: wrap` erlaubt Umbruch wenn Items zu "
                    "breit werden. `gap: 16px` ist der moderne Weg für Abstände – besser als "
                    "margin-Hacks. Responsive ohne Media-Query möglich!"
                ),
            },
        ],
    },
    {
        "title": "Git Crashkurs – Commit, Branch, Merge",
        "date": "2026-04-05",
        "video_url": "https://www.youtube.com/watch?v=RGOj5yH7evk",
        "youtube_id": "RGOj5yH7evk",
        "tags": ["Git", "GitHub", "Versionskontrolle", "Terminal"],
        "video_title": "Git and GitHub for Beginners - Crash Course",
        "channel_name": "freeCodeCamp.org",
        "snapshots": [
            {
                "timestamp_sec": 300,
                "notes": (
                    "**git init & Grundstruktur** – `git init` erstellt versteckten "
                    "`.git`-Ordner im Projekt. Drei Bereiche: Working Directory → "
                    "Staging Area → Repository. Staging ist wie ein Einkaufswagen: "
                    "man legt rein was man committen will."
                ),
            },
            {
                "timestamp_sec": 720,
                "notes": (
                    "**add & commit Workflow** – `git add datei.txt` (oder `git add .` "
                    "für alles) → `git commit -m \"Nachricht\"`. Commit-Messages im Imperativ: "
                    "\"Add login page\", nicht \"Added login page\". Jeder Commit = ein Checkpoint."
                ),
            },
            {
                "timestamp_sec": 1500,
                "notes": (
                    "**Branching erklärt** – `git branch feature-x` erstellt neuen Zweig, "
                    "`git checkout feature-x` wechselt hin. Shortcut: `git checkout -b feature-x`. "
                    "Branches sind billig in Git – für jedes Feature einen eigenen Branch nutzen!"
                ),
            },
            {
                "timestamp_sec": 2400,
                "notes": (
                    "**Merge & Konflikte** – `git merge feature-x` holt Änderungen in "
                    "aktuellen Branch. Bei Konflikten: Git markiert beide Versionen mit "
                    "`<<<<<<<` und `>>>>>>>`. Manuell entscheiden welche Version bleibt, "
                    "dann `git add` + `git commit`."
                ),
            },
            {
                "timestamp_sec": 3300,
                "notes": (
                    "**Push zu GitHub** – `git remote add origin URL` verknüpft lokales "
                    "Repo mit GitHub. `git push -u origin main` beim ersten Mal, danach nur "
                    "`git push`. Pull Request = Vorschlag, Code in main zu mergen. "
                    "Immer erst PR statt direkt auf main pushen!"
                ),
            },
        ],
    },
]


# ── Hauptlogik ───────────────────────────────────────────────────────────────

def seed(reset: bool = False) -> None:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    # Vorhandene Demo-Daten prüfen / löschen
    existing = db.users.find_one({"username": DEMO_USER["username"]})
    if existing and not reset:
        print(f"✗ Demo-User '{DEMO_USER['username']}' existiert bereits.")
        print("  Nutze --reset um alles neu zu erstellen.")
        sys.exit(1)

    if existing and reset:
        user_id = str(existing["_id"])
        n_sessions = db.sessions.delete_many({"user_id": user_id}).deleted_count
        n_snaps = db.snapshots.delete_many({"user_id": user_id}).deleted_count
        db.users.delete_one({"_id": existing["_id"]})
        print(f"↻ Alte Demo-Daten gelöscht: {n_sessions} Sessions, {n_snaps} Snapshots")

    # Demo-User anlegen
    user_doc = {
        "username": DEMO_USER["username"],
        "email": DEMO_USER["email"],
        "password_hash": pwd_context.hash(DEMO_USER["password"]),
        "created_at": datetime.now(timezone.utc),
        "tos_accepted": True,
        "tos_accepted_at": datetime.now(timezone.utc),
    }
    user_id = str(db.users.insert_one(user_doc).inserted_id)
    print(f"✓ Demo-User erstellt: {DEMO_USER['username']} / {DEMO_USER['password']}")

    # Sessions + Snapshots anlegen
    total_snaps = 0
    for sess_data in SESSIONS:
        session_doc = {
            "user_id": user_id,
            "title": sess_data["title"],
            "date": sess_data["date"],
            "video_url": sess_data["video_url"],
            "youtube_id": sess_data["youtube_id"],
            "tags": sess_data["tags"],
            "video_title": sess_data["video_title"],
            "channel_name": sess_data["channel_name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        session_id = str(db.sessions.insert_one(session_doc).inserted_id)

        for snap in sess_data["snapshots"]:
            snap_doc = {
                "session_id": session_id,
                "user_id": user_id,
                "timestamp_sec": snap["timestamp_sec"],
                "timestamp_label": fmt_ts(snap["timestamp_sec"]),
                "notes": snap["notes"],
                "frame_url": yt_thumb(sess_data["youtube_id"]),
                "frame_source": "thumbnail",
                "created_at": datetime.now(timezone.utc),
            }
            db.snapshots.insert_one(snap_doc)
            total_snaps += 1

        print(f"  ✓ Session: {sess_data['title']} ({len(sess_data['snapshots'])} Snapshots)")

    print(f"\n✓ Fertig: 1 User, {len(SESSIONS)} Sessions, {total_snaps} Snapshots")
    print(f"  Login: {DEMO_USER['username']} / {DEMO_USER['password']}")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LernyTube Demo-Daten erstellen")
    parser.add_argument("--reset", action="store_true", help="Vorhandene Demo-Daten löschen")
    args = parser.parse_args()
    seed(reset=args.reset)
