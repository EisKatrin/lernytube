"""E2E-Tests für LernyTube Auth-Flow."""

import pytest
import uuid
from playwright.sync_api import expect


def test_startseite_laedt(page):
    """Startseite zeigt Login-Formular."""
    page.goto("/")
    expect(page.locator("#login-form")).to_be_visible()
    expect(page.locator("#login-username")).to_be_visible()


def test_register_tab_umschalten(page):
    """Klick auf Registrieren zeigt das Register-Formular."""
    page.goto("/")
    page.click("text=Registrieren")
    expect(page.locator("#register-form")).to_be_visible()
    expect(page.locator("#reg-username")).to_be_visible()
    expect(page.locator("#reg-email")).to_be_visible()
    expect(page.locator("#reg-password")).to_be_visible()


def test_registrierung_und_redirect(page):
    """Neuer User registriert sich und wird zum Dashboard weitergeleitet."""
    unique = uuid.uuid4().hex[:8]

    page.goto("/")
    page.click("text=Registrieren")

    page.fill("#reg-username", f"e2e_{unique}")
    page.fill("#reg-email", f"e2e_{unique}@test.com")
    page.fill("#reg-password", f"E2eTestPasswort!{unique}")
    page.fill("#reg-password-confirm", f"E2eTestPasswort!{unique}")

    page.click("#register-form button[type='submit']")

    # Warte auf Redirect (ToS oder Dashboard)
    page.wait_for_timeout(3000)
    # Nach erfolgreicher Registrierung sollte URL sich geändert haben
    assert page.url != "https://lernytube.eiskopani.de/" or page.locator("#tosModal").is_visible()
