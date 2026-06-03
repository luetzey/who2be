"""GoTrue-Admin-Calls mit dem Service-Role-Key (Account-Lifecycle, Track O).

Aktuell: Loeschen eines Auth-Users im Hard-Purge (`DELETE /auth/v1/admin/users/{id}`).
Analog zu `gotrue_mailer` ist der Call **best-effort** — ist `supabase_url`/
`supabase_service_key` nicht konfiguriert (On-Prem/Dev/Tests) oder schlaegt der
Call fehl, wird das nur geloggt; der DB-seitige Purge laeuft unabhaengig weiter.
Der Service-Key wird nie geloggt und verlaesst den Server nicht.
"""

import logging
from uuid import UUID

import httpx

from who2be_api.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


async def delete_auth_user(user_id: UUID) -> bool:
    """Loescht den GoTrue-User per Admin-API. True bei Erfolg (oder 404 ⇒ schon weg).

    Fehler werden geschluckt (best-effort); der Aufrufer (Purge-Job) darf den
    Rueckgabewert zur Protokollierung nutzen, ist aber nicht davon abhaengig.
    """
    settings = get_settings()
    base = settings.supabase_url.rstrip("/")
    service_key = settings.supabase_service_key
    if not base or not service_key:
        logger.info("GoTrue nicht konfiguriert — Auth-User-Loeschung uebersprungen.")
        return False

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.delete(
                f"{base}/auth/v1/admin/users/{user_id}",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
            )
            # 404 ⇒ User existiert nicht (mehr) — fuer den Purge ein Erfolg.
            if response.status_code == httpx.codes.NOT_FOUND:
                return True
            response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Auth-User-Loeschung fuer %s fehlgeschlagen: %s", user_id, exc)
        return False
    return True
