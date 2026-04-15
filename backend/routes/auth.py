"""Router für Authentifizierungs-Endpunkte.

Stellt Endpunkte für Registrierung, Login, Profil
und Nutzungsbedingungen bereit.
"""

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, status

from database import get_db
from models import UserRegister, UserLogin, Token, UserOut
from auth_utils import hash_password, verify_password, create_token, get_current_user_id

router = APIRouter()


def _user_to_out(user: dict) -> UserOut:
    return UserOut(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        created_at=user["created_at"],
        tos_accepted=user.get("tos_accepted", False),
    )


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister):
    db = get_db()
    existing = await db.users.find_one(
        {"$or": [{"username": data.username}, {"email": data.email}]}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Benutzername oder E-Mail bereits vergeben")

    user_doc = {
        "username": data.username,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "created_at": datetime.now(timezone.utc),
        "tos_accepted": False,
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    token = create_token(str(result.inserted_id))
    return Token(access_token=token, user=_user_to_out(user_doc))


@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    db = get_db()
    user = await db.users.find_one({"username": data.username})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Falscher Benutzername oder Passwort")
    token = create_token(str(user["_id"]))
    return Token(access_token=token, user=_user_to_out(user))


@router.get("/me", response_model=UserOut)
async def me(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return _user_to_out(user)


@router.get("/tos")
async def get_tos():
    """Gibt den aktuellen ToS-Text aus der Datenbank zurück."""
    db = get_db()
    doc = await db.settings.find_one({"key": "tos"})
    if not doc:
        raise HTTPException(status_code=404, detail="Nutzungsbedingungen nicht gefunden")
    return {"content": doc["content"], "version": doc.get("version", "")}


@router.post("/accept-tos", response_model=UserOut)
async def accept_tos(user_id: str = Depends(get_current_user_id)):
    """Markiert den aktuellen Benutzer als ToS-akzeptiert."""
    db = get_db()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"tos_accepted": True, "tos_accepted_at": datetime.now(timezone.utc)}},
    )
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    return _user_to_out(user)
