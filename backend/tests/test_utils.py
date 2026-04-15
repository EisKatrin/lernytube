"""Unit-Tests für Hilfsfunktionen aus routes/sessions.py und routes/snapshots.py."""

import pytest
from fastapi import HTTPException

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routes.sessions import _extract_youtube_id, _clean_tags
from routes.snapshots import _format_timestamp


class TestExtractYoutubeId:
    def test_standard_watch_url(self):
        assert _extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_short_url(self):
        assert _extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_embed_url(self):
        assert _extract_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        assert _extract_youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert _extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_ungueltige_url(self):
        with pytest.raises(HTTPException) as exc_info:
            _extract_youtube_id("https://example.com/not-youtube")
        assert exc_info.value.status_code == 400


class TestCleanTags:
    def test_normale_tags(self):
        assert _clean_tags(["python", "basics"]) == ["python", "basics"]

    def test_deduplizierung(self):
        assert _clean_tags(["python", "python", "js"]) == ["python", "js"]

    def test_leere_strings_entfernt(self):
        assert _clean_tags(["", "python", " ", "js"]) == ["python", "js"]

    def test_max_8_tags(self):
        tags = [f"tag{i}" for i in range(12)]
        result = _clean_tags(tags)
        assert len(result) == 8

    def test_trim_whitespace(self):
        assert _clean_tags(["  python  ", "js "]) == ["python", "js"]

    def test_truncate_50_chars(self):
        long_tag = "a" * 100
        result = _clean_tags([long_tag])
        assert len(result[0]) == 50


class TestFormatTimestamp:
    def test_null_sekunden(self):
        assert _format_timestamp(0) == "0:00"

    def test_eine_minute_fuenf(self):
        assert _format_timestamp(65) == "1:05"

    def test_mit_stunden(self):
        assert _format_timestamp(3661) == "1:01:01"

    def test_genau_eine_stunde(self):
        assert _format_timestamp(3600) == "1:00:00"

    def test_59_minuten_59(self):
        assert _format_timestamp(3599) == "59:59"
