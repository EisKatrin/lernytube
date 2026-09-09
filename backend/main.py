"""Hauptmodul der LernyTube-Anwendung.

Initialisiert die FastAPI-App, registriert alle Router und
stellt das Frontend als statische Dateien bereit.
"""

import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import connect_db, disconnect_db
from routes import auth, sessions, snapshots, tutor, admin

_404_DIR = Path("/home/ekaterina/404-pages")
_404_FILES = ["404-terminal.html", "404-gameover.html", "404-literary.html"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lebenszyklusmanager: Stellt DB-Verbindung beim Start/Stop her bzw. trennt sie."""
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(
    title="LernyTube API",
    description="Backend für die LernyTube YouTube-Lernplattform",
    version="1.0.0",
    lifespan=lifespan,
)

# API-Router einbinden
app.include_router(auth.router, prefix="/api/auth", tags=["Authentifizierung"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(snapshots.router, prefix="/api/snapshots", tags=["Snapshots"])
app.include_router(tutor.router, prefix="/api/tutor", tags=["Lehrer & Lernbuch"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin-Dashboard"])

# Statische Dateien (CSS, JS, Bilder) einbinden
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """Gibt die Login/Registrierungs-Seite zurück."""
    return FileResponse("static/index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Gibt die Dashboard-Seite mit der Sessionsübersicht zurück."""
    return FileResponse("static/dashboard.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/session", include_in_schema=False)
async def session_page():
    """Gibt die Session-Seite mit Video-Player und Snapshots zurück."""
    return FileResponse("static/session.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/lernbuch", include_in_schema=False)
async def lernbuch_page():
    """Gibt die Lernbuch-Seite mit dem KI-Lehrer zurück."""
    return FileResponse("static/lernbuch.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        try:
            chosen = random.choice(_404_FILES)
            html = (_404_DIR / chosen).read_text(encoding="utf-8")
            return HTMLResponse(content=html, status_code=404)
        except OSError:
            # _404_DIR ist ein Bind-Mount, der nur auf der VPS existiert
            # (z.B. nicht in der CI-Umgebung) — dann auf JSON zurückfallen.
            pass
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
