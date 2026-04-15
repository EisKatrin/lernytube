"""Datenbankmodul: Verbindungsmanagement für MongoDB via Motor (async).

Stellt eine globale Datenbankverbindung bereit und erstellt
beim Start automatisch die notwendigen Indizes.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


async def connect_db() -> None:
    """Stellt die Verbindung zur MongoDB-Datenbank her und erstellt Indizes."""
    global _client, _db
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    mongo_db = os.getenv("MONGO_DB", "lernytube_db")
    _client = AsyncIOMotorClient(mongo_uri)
    _db = _client[mongo_db]
    # Eindeutige Indizes für Benutzer
    await _db.users.create_index("username", unique=True)
    await _db.users.create_index("email", unique=True)
    # Indizes für schnelle Abfragen
    await _db.sessions.create_index("user_id")
    await _db.snapshots.create_index("session_id")


async def disconnect_db() -> None:
    """Trennt die Verbindung zur MongoDB-Datenbank."""
    global _client
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    """Gibt die aktive Datenbankinstanz zurück.

    Returns:
        Die aktive MongoDB-Datenbankinstanz.
    """
    return _db
