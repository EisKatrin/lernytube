"""Pydantic-Datenmodelle für die LernyTube-API.

Definiert alle Ein- und Ausgabemodelle für Benutzer,
Lernsessions und Snapshots.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Benutzer-Modelle ────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Eingabemodell für die Benutzerregistrierung."""

    username: str = Field(..., min_length=3, max_length=50, description="Eindeutiger Benutzername")
    email: EmailStr = Field(..., description="Gültige E-Mail-Adresse")
    password: str = Field(..., min_length=16, description="Passwort mit mindestens 16 Zeichen")

    @field_validator("password")
    @classmethod
    def password_komplex(cls, v: str) -> str:
        """Prüft ob das Passwort Großbuchstabe und Sonderzeichen enthält."""
        import re
        if not re.search(r"[A-Z]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten.")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("Passwort muss mindestens ein Sonderzeichen enthalten.")
        return v


class UserLogin(BaseModel):
    """Eingabemodell für die Benutzeranmeldung."""

    username: str
    password: str


class UserOut(BaseModel):
    """Ausgabemodell für Benutzerdaten (ohne Passwort-Hash)."""

    id: str
    username: str
    email: str
    created_at: datetime
    tos_accepted: bool = False


class Token(BaseModel):
    """Antwortmodell nach erfolgreichem Login oder Registrierung."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ─── Session-Modelle ─────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Eingabemodell zum Erstellen einer neuen Lernsession."""

    title: str = Field(..., min_length=1, max_length=200, description="Sitzungstitel")
    date: str = Field(..., description="Datum im Format YYYY-MM-DD")
    video_url: str = Field(..., description="Vollständige YouTube-Video-URL")
    tags: list[str] = Field(default=[], description="Bis zu 8 Tags zur Kategorisierung")


class SessionOut(BaseModel):
    """Ausgabemodell für eine Lernsession."""

    id: str
    user_id: str
    title: str
    date: str
    video_url: str
    youtube_id: str
    tags: list[str] = []
    snapshot_count: int = 0
    has_receipt: bool = False
    video_title: Optional[str] = None
    channel_name: Optional[str] = None
    created_at: datetime


# ─── Snapshot-Modelle ────────────────────────────────────────────────────────

class SnapshotCreate(BaseModel):
    """Eingabemodell zum Erstellen eines neuen Snapshots."""

    session_id: str = Field(..., description="ID der zugehörigen Session")
    timestamp_sec: int = Field(..., ge=0, description="Videoposition in Sekunden")
    notes: str = Field(default="", description="Freitext-Notizen zum Snapshot")
    frame_data: str | None = Field(default=None, description="Base64-kodiertes JPEG-Bild vom Client")
    frame_url: str | None = Field(default=None, description="Externe Thumbnail-URL (z.B. YouTube)")


class SnapshotUpdate(BaseModel):
    """Eingabemodell zum Aktualisieren der Notizen eines Snapshots."""

    notes: str


class SnapshotOut(BaseModel):
    """Ausgabemodell für einen Snapshot."""

    id: str
    session_id: str
    timestamp_sec: int
    timestamp_label: str
    notes: str
    frame_url: str | None = None
    frame_source: str | None = None
    created_at: datetime


class SnapshotSearchResult(BaseModel):
    """Ausgabemodell für Snapshot-Suchergebnisse mit Session-Informationen."""

    id: str
    session_id: str
    session_title: str
    session_youtube_id: str
    timestamp_sec: int
    timestamp_label: str
    notes: str
    created_at: datetime


# ─── Kassenbon-Modelle (Lern-Receipt zum Session-Abschluss) ──────────────────

class ReceiptCreate(BaseModel):
    """Eingabemodell zum Speichern eines Lern-Kassenbons.

    Ein Kassenbon ist ein kurzes Reflexions-Format, das der Benutzer
    am Ende einer Lernsession ausfüllt. Es verdichtet die Session auf
    fünf Kernfragen: Wie lange wurde gelernt, wie konzentriert war
    die Session, was wurde produziert, was bleibt hängen und wie
    geht es weiter.
    """

    dauer_min: int = Field(
        ...,
        ge=1,
        le=600,
        description="Effektive Lerndauer in Minuten (1–600).",
    )
    konzentration: int = Field(
        ...,
        ge=1,
        le=5,
        description="Selbsteinschätzung der Konzentration auf einer Skala von 1 (schwach) bis 5 (sehr stark).",
    )
    artefakte: str = Field(
        default="",
        max_length=500,
        description="Kurze Beschreibung dessen, was produziert wurde (z.B. '1 Funktion, 2 Notizen').",
    )
    erkenntnis: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Der eine Satz, der hängenbleibt — die zentrale Einsicht der Session.",
    )
    naechster_schritt: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Konkreter nächster Lern- oder Übungsschritt.",
    )


class ReceiptOut(BaseModel):
    """Ausgabemodell für einen gespeicherten Kassenbon.

    Enthält zusätzlich den Erstellungs- und letzten Aktualisierungszeitpunkt,
    damit das Frontend Bons als chronologische Reflexionshistorie darstellen kann.
    """

    dauer_min: int
    konzentration: int
    artefakte: str
    erkenntnis: str
    naechster_schritt: str
    created_at: datetime
    updated_at: datetime


# ─── Lehrer & Lernbuch-Modelle ───────────────────────────────────────────────

class TutorAsk(BaseModel):
    """Eingabemodell für eine Frage an den KI-Lehrer."""

    question: str = Field(..., min_length=3, max_length=2000, description="Die Frage an den Lehrer")


class TutorEntryOut(BaseModel):
    """Ausgabemodell für einen einzelnen Frage-Antwort-Eintrag im Lernbuch."""

    id: str
    topic_id: str
    topic_path: list[str] = Field(default=[], description="Themenpfad, z.B. ['Programmieren', 'Python']")
    question: str
    answer: str
    created_at: datetime


class TutorTopicNode(BaseModel):
    """Ein Knoten im Themenbaum des Lernbuchs, mit eigenen Einträgen und Unterthemen."""

    id: str
    title: str
    entries: list[TutorEntryOut] = []
    children: list["TutorTopicNode"] = []


TutorTopicNode.model_rebuild()
