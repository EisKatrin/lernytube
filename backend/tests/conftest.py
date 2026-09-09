"""Gemeinsame Fixtures für Integration-Tests mit echtem MongoDB."""

import os
import pytest
import pytest_asyncio

os.environ["JWT_SECRET"] = "test-secret-key-for-integration-tests"
os.environ["JWT_EXPIRE_HOURS"] = "48"

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://admin:REDACTED_MONGO_PASSWORD@localhost:27017/")
TEST_DB = os.environ.get("MONGO_DB", "lernytube_test")

from motor.motor_asyncio import AsyncIOMotorClient
from httpx import AsyncClient, ASGITransport

import database
from main import app
from auth_utils import hash_password, create_token


@pytest_asyncio.fixture
async def mock_db():
    """Nutzt eine Test-Datenbank auf dem echten MongoDB und leert sie nach jedem Test."""
    client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[TEST_DB]
    database._client = client
    database._db = db
    yield db
    for name in ["users", "sessions", "snapshots", "settings", "topics", "qa_entries"]:
        await db[name].delete_many({})
    client.close()


@pytest_asyncio.fixture
async def client():
    """Async HTTP-Client für API-Requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(mock_db):
    """Erstellt einen Test-User direkt in der DB und gibt User-Dict + Token zurück."""
    from datetime import datetime, timezone
    user_doc = {
        "username": "testuser",
        "email": "test@example.com",
        "password_hash": hash_password("MeinTestPasswort!1"),
        "created_at": datetime.now(timezone.utc),
        "tos_accepted": False,
    }
    result = await mock_db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    token = create_token(user_id)
    return {"user_id": user_id, "token": token, "username": "testuser"}


@pytest.fixture
def auth_headers(registered_user):
    """Authorization-Header mit gültigem Bearer-Token."""
    return {"Authorization": f"Bearer {registered_user['token']}"}
