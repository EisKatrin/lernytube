"""Hilfsfunktionen für JWT-Authentifizierung und Passwort-Hashing.

Enthält alle Funktionen für sichere Passwortverwaltung
und tokenbasierte Authentifizierung.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "48"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """Erstellt einen sicheren bcrypt-Hash des Passworts.

    Args:
        password: Das Klartext-Passwort.

    Returns:
        Der bcrypt-Hash als Zeichenkette.
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Überprüft ein Klartext-Passwort gegen seinen gespeicherten Hash.

    Args:
        plain: Das eingegebene Klartext-Passwort.
        hashed: Der gespeicherte bcrypt-Hash.

    Returns:
        True wenn das Passwort übereinstimmt, sonst False.
    """
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str) -> str:
    """Erstellt ein signiertes JWT-Token für den angegebenen Benutzer.

    Args:
        user_id: Die MongoDB-ID des Benutzers als Zeichenkette.

    Returns:
        Das signierte JWT-Token.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI-Abhängigkeit: Extrahiert und validiert die Benutzer-ID aus dem Bearer-Token.

    Args:
        credentials: Die HTTP-Authorization-Credentials aus dem Request-Header.

    Returns:
        Die Benutzer-ID aus dem validen Token.

    Raises:
        HTTPException: Bei ungültigem oder abgelaufenem Token (401).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Ungültiges Token",
            )
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token abgelaufen oder ungültig",
        )
