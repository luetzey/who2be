"""Einladungs-Mail via Supabase GoTrue (`POST /auth/v1/invite`).

ADR-0023: Wir nutzen GoTrue als Mail-Versender, statt einen eigenen SMTP-Hook
zu bauen — der Stack bringt GoTrue ohnehin mit. Der Versand ist **best-effort**:
ist `supabase_url`/`supabase_service_key` nicht konfiguriert oder schlaegt der
Call fehl, wird das nur geloggt; die Invitation bleibt gueltig und der Caller
kann den Klartext-Token aus dem 201-Body manuell teilen.

Die Mail traegt **keinen** Einladungs-Token. `redirect_to` zeigt auf die
Web-Seite `{web_base_url}/invitations`: nach dem GoTrue-Verify ist der User
eingeloggt und sieht dort die offenen Einladungen an die Adresse seines Kontos
(`GET /v1/invitations/pending`), angenommen wird per Klick. So bleibt der Token
aus allem heraus, was unterwegs geloggt wird oder im JWT landet: aus der
`redirect_to`-Query (GoTrue setzt sie in den Mail-Link, Proxies loggen sie mit)
und aus den User-Metadaten (`data` wird zu `user_metadata` und steht damit in
jedem Access-Token). Der Token gilt nur noch fuer den manuell geteilten Link.
"""

import logging

import httpx

from who2be_api.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


def build_invitations_url() -> str:
    """Web-Seite mit den offenen Einladungen des eingeloggten Kontos."""
    base = get_settings().web_base_url.rstrip("/")
    return f"{base}/invitations"


async def send_invitation_email(email: str) -> bool:
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

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base}/auth/v1/invite",
                params={"redirect_to": build_invitations_url()},
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                },
                json={"email": email},
            )
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Invitation-Mail an %s fehlgeschlagen: %s", email, exc)
        return False
    return True
