"""E2E-Fixtures für LernyTube mit Playwright.

Dieses conftest überschreibt die mock_db Fixture aus dem Eltern-conftest,
da E2E-Tests keine DB-Mock brauchen.
"""

import pytest

BASE_URL = "https://lernytube.eiskopani.de"


@pytest.fixture(scope="session")
def browser_context_args():
    return {"base_url": BASE_URL, "ignore_https_errors": True}


@pytest.fixture(autouse=True)
def mock_db():
    """Überschreibt die autouse mock_db Fixture — E2E braucht keine Test-DB."""
    yield None
