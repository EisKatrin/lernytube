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


def test_registrierung_zeigt_bestaetigungshinweis(page):
    """Neuer User registriert sich und sieht den Hinweis, die E-Mail zu bestätigen."""
    unique = uuid.uuid4().hex[:8]

    page.goto("/")
    page.click("text=Registrieren")

    page.fill("#reg-username", f"e2e_{unique}")
    page.fill("#reg-email", f"e2e_{unique}@test.com")
    page.fill("#reg-password", f"E2eTestPasswort!{unique}")
    page.fill("#reg-password-confirm", f"E2eTestPasswort!{unique}")

    page.click("#register-form button[type='submit']")

    # Registrierung loggt nicht mehr automatisch ein — stattdessen Hinweis
    # zur E-Mail-Bestätigung, kein Zugriff auf das Dashboard ohne Bestätigung.
    expect(page.locator("#verify-notice")).to_be_visible()
    assert page.url == "https://lernytube.eiskopani.de/"
