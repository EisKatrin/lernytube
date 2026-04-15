"""Hauptmodul der LernyTube-Anwendung.

Initialisiert die FastAPI-App, registriert alle Router und
stellt das Frontend als statische Dateien bereit.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import connect_db, disconnect_db
from routes import auth, sessions, snapshots


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
