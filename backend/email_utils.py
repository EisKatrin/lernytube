"""Versand der Bestätigungs-E-Mail nach der Registrierung.

Solange keine SMTP-Zugangsdaten hinterlegt sind (EMAIL_SMTP_USER
fehlt), wird der Versand übersprungen und nur geloggt — die
Registrierung funktioniert dann trotzdem, der Bestätigungslink
landet nur im Log statt im Postfach.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("lernytube.email")


def _email_configured() -> bool:
    return bool(os.environ.get("EMAIL_SMTP_USER") and os.environ.get("EMAIL_SMTP_PASSWORD"))


def send_verification_email(to_email: str, username: str, token: str) -> bool:
    """Verschickt die Bestätigungs-E-Mail mit Verifizierungslink.

    Returns True, wenn eine E-Mail tatsächlich verschickt wurde.
    """
    base_url = os.environ.get("APP_BASE_URL", "https://lernytube.eiskopani.de")
    verify_link = f"{base_url}/api/auth/verify-email?token={token}"

    if not _email_configured():
        logger.info(
            "E-Mail-Versand nicht konfiguriert (EMAIL_SMTP_USER/PASSWORD fehlen) — "
            "Bestätigungslink nur geloggt für %s: %s", to_email, verify_link,
        )
        return False

    host = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    user = os.environ["EMAIL_SMTP_USER"]
    password = os.environ["EMAIL_SMTP_PASSWORD"]

    msg = EmailMessage()
    msg["Subject"] = "Bitte bestätige deine E-Mail-Adresse – LernyTube"
    msg["From"] = user
    msg["To"] = to_email
    msg.set_content(
        f"Hallo {username},\n\n"
        "willkommen bei LernyTube! Bitte bestätige deine E-Mail-Adresse, "
        "indem du auf den folgenden Link klickst:\n\n"
        f"{verify_link}\n\n"
        "Erst nach der Bestätigung kannst du dich anmelden.\n"
        "Falls du dich nicht bei LernyTube registriert hast, kannst du diese E-Mail ignorieren.\n\n"
        "— Dein LernyTube-Team"
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Bestätigungs-E-Mail konnte nicht an %s gesendet werden", to_email)
        return False
