"""Unit-Tests für Pydantic-Datenmodelle."""

import pytest
from pydantic import ValidationError
from models import UserRegister, SessionCreate, SnapshotCreate


class TestUserRegister:
    def test_gueltige_registrierung(self):
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="MeinSicheresPasswort!1",
        )
        assert user.username == "testuser"

    def test_passwort_zu_kurz(self):
        with pytest.raises(ValidationError):
            UserRegister(username="test", email="t@e.com", password="Kurz!1")

    def test_passwort_ohne_grossbuchstabe(self):
        with pytest.raises(ValidationError, match="Großbuchstaben"):
            UserRegister(
                username="test",
                email="t@example.com",
                password="kein_grossbuchstabe!1",
            )

    def test_passwort_ohne_sonderzeichen(self):
        with pytest.raises(ValidationError, match="Sonderzeichen"):
            UserRegister(
                username="test",
                email="t@example.com",
                password="KeinSonderzeichen123",
            )

    def test_username_zu_kurz(self):
        with pytest.raises(ValidationError):
            UserRegister(username="ab", email="t@e.com", password="MeinSicheresPasswort!1")

    def test_ungueltige_email(self):
        with pytest.raises(ValidationError):
            UserRegister(username="test", email="keine-email", password="MeinSicheresPasswort!1")


class TestSessionCreate:
    def test_gueltige_session(self):
        s = SessionCreate(
            title="Python Basics",
            date="2026-04-15",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            tags=["python", "basics"],
        )
        assert s.title == "Python Basics"
        assert len(s.tags) == 2

    def test_titel_leer(self):
        with pytest.raises(ValidationError):
            SessionCreate(title="", date="2026-01-01", video_url="https://youtube.com/watch?v=abc")

    def test_tags_default_leer(self):
        s = SessionCreate(title="Test", date="2026-01-01", video_url="https://youtube.com/watch?v=abc")
        assert s.tags == []


class TestSnapshotCreate:
    def test_gueltiger_snapshot(self):
        snap = SnapshotCreate(session_id="abc123", timestamp_sec=120, notes="Wichtig!")
        assert snap.timestamp_sec == 120

    def test_negativer_timestamp(self):
        with pytest.raises(ValidationError):
            SnapshotCreate(session_id="abc", timestamp_sec=-1)

    def test_notes_default_leer(self):
        snap = SnapshotCreate(session_id="abc", timestamp_sec=0)
        assert snap.notes == ""

    def test_frame_felder_optional(self):
        snap = SnapshotCreate(session_id="abc", timestamp_sec=10)
        assert snap.frame_data is None
        assert snap.frame_url is None
