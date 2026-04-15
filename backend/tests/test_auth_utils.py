"""Unit-Tests für auth_utils: Passwort-Hashing und JWT-Token."""

import os
import pytest
from datetime import datetime, timezone
from jose import jwt

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests")

from auth_utils import (
    hash_password,
    verify_password,
    create_token,
    JWT_SECRET,
    JWT_ALGORITHM,
)


class TestPasswordHashing:
    def test_hash_und_verify_korrekt(self):
        pw = "MeinSicheresPasswort!123"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_falsches_passwort(self):
        hashed = hash_password("Richtig!123456789")
        assert verify_password("Falsch!123456789", hashed) is False

    def test_hash_ist_nicht_klartext(self):
        pw = "TestPasswort!2024abc"
        hashed = hash_password(pw)
        assert hashed != pw
        assert hashed.startswith("$2b$")


class TestCreateToken:
    def test_token_enthaelt_user_id(self):
        token = create_token("user123")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "user123"

    def test_token_hat_ablaufzeit(self):
        token = create_token("user456")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_token_ist_string(self):
        token = create_token("abc")
        assert isinstance(token, str)
        assert len(token) > 20
