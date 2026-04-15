# LernyTube

Lernvideos mit Notizen, Snapshots und Volltextsuche – direkt im Browser.

**Live:** [lernytube.eiskopani.de](https://lernytube.eiskopani.de)

## Was ist das?

LernyTube ist eine Web-App, die YouTube-Lernvideos in durchsuchbares Wissen verwandelt. Per Klick auf *Snapshot* wird die aktuelle Videoposition festgehalten – zusammen mit einer Notiz, Tags und optional einem manuellen Screenshot (Strg+V).

Wochen später bringt die Volltextsuche dich per Klick exakt an die richtige Stelle im Video zurück.

## Features

- Snapshots mit Zeitstempel und Notizen
- Manueller Screenshot-Upload (Win+Shift+S → Strg+V)
- Volltextsuche über alle Notizen
- Tags und Filter
- Markdown- und PDF-Export
- Mini-Kalender mit Tages-Filter
- Admin-Panel und Forum (Feature-Branch)

## Tech-Stack

| Schicht    | Technologie                    |
|------------|--------------------------------|
| Backend    | Python 3.11, FastAPI, Uvicorn  |
| Datenbank  | MongoDB                        |
| Frontend   | Vanilla HTML / CSS / JS        |
| Auth       | JWT (48h)                      |
| Video      | YouTube IFrame API             |
| Deploy     | Docker + Traefik + Let's Encrypt |

## Schnellstart

```bash
# 1. Repository klonen
git clone https://github.com/EisKatrin/lernytube.git
cd lernytube

# 2. .env anlegen (siehe .env.example)
cp .env.example .env
# Werte ausfüllen: MONGO_URI, JWT_SECRET, YOUTUBE_API_KEY

# 3. Starten
docker compose up -d

# 4. Optional: Demo-Daten laden
pip install pymongo passlib[bcrypt]
python seed_demo.py
```

Die App ist dann unter `http://localhost:8000` erreichbar.

## Projektstruktur

```
├── docker-compose.yml
├── .env.example
├── seed_demo.py            # Demo-User + Beispiel-Sessions
└── backend/
    ├── Dockerfile
    ├── main.py              # FastAPI App, Router, Static Files
    ├── database.py          # MongoDB-Verbindung
    ├── auth_utils.py        # JWT + Passwort-Hashing
    ├── models.py            # Pydantic-Modelle
    ├── routes/
    │   ├── auth.py          # Registrierung + Login
    │   ├── sessions.py      # Lernsession CRUD
    │   └── snapshots.py     # Snapshot CRUD + Screenshot-Upload
    └── static/
        ├── index.html       # Landing Page
        ├── dashboard.html   # Dashboard mit Kalender
        ├── session.html     # Video-Player + Snapshots
        ├── css/
        └── js/
```

## API

| Method | Pfad                               | Beschreibung              |
|--------|-------------------------------------|---------------------------|
| POST   | `/api/auth/register`               | Registrierung             |
| POST   | `/api/auth/login`                  | Login → JWT               |
| GET    | `/api/sessions/`                   | Alle Sessions             |
| POST   | `/api/sessions/`                   | Neue Session              |
| GET    | `/api/snapshots/?session_id=…`     | Snapshots einer Session   |
| POST   | `/api/snapshots/`                  | Neuer Snapshot            |
| POST   | `/api/snapshots/{id}/upload-frame` | Manueller Screenshot      |
| GET    | `/api/snapshots/search?q=…`        | Volltextsuche             |

## Lizenz

MIT
