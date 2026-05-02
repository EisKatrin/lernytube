"""Zufällige 404-Seiten für LernyTube."""

import random
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse

_404_DIR = Path("/home/ekaterina/404-pages")
_404_FILES = ["404-terminal.html", "404-gameover.html", "404-literary.html"]


def random_404_response(request: Request) -> HTMLResponse:
    """Gibt eine zufällig gewählte 404-Seite als HTMLResponse zurück."""
    chosen = random.choice(_404_FILES)
    html = (_404_DIR / chosen).read_text(encoding="utf-8")
    return HTMLResponse(content=html, status_code=404)
