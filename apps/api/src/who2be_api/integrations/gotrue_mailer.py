"""Einladungs-Mail via Supabase GoTrue (`POST /auth/v1/invite`).

ADR-0023: Wir nutzen GoTrue als Mail-Versender, statt einen eigenen SMTP-Hook
zu bauen — der Stack bringt GoTrue ohnehin mit. Der Versand ist **best-effort**:
ist `supabase_url`/`supabase_service_key` nicht konfiguriert oder schlaegt der
Call fehl, wird das nur geloggt; die Invitation bleibt gueltig und der Caller
kann den Klartext-Token aus dem 201-Body manuell teilen.

Der Magic-Link von GoTrue zeigt via `redirect_to` auf die Web-Accept-Route
`{web_base_url}/invitations/{token}/accept`, die den Token an
`POST /v1/invitations/{token}/accept` weiterreicht.
"""

import logging

import httpx

from who2be_api.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


def build_accept_url(token: str) -> str:
    """Web-Accept-Route fuer einen Klartext-Token."""
    base = get_settings().web_base_url.rstrip("/")
    return f"{base}/invitations/{token}/accept"


async def send_invitation_email(email: str, token: str) -> bool:
    """Schickt die Einladungs-Mail ueber GoTrue. True bei erfolgreichem Versand.

    Fehler werden geschluckt (best-effort) — der Aufrufer darf den Rueckgabewert
    ignorieren; die Invitation ist unabhaengig davon persistiert.
    """
    settings = get_settings()
    base = settings.supabase_url.rstrip("/")
    service_key = settings.supabase_service_key
    if not base or not service_key:
        logger.info("GoTrue nicht konfiguriert — Invitation-Mail uebersprungen.")
        return False

    accept_url = build_accept_url(token)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base}/auth/v1/invite",
                params={"redirect_to": accept_url},
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                },
                json={"email": email, "data": {"who2be_accept_url": accept_url}},
            )
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Invitation-Mail an %s fehlgeschlagen: %s", email, exc)
        return False
    return True
