"""On-Prem-Adapter: offline signierte Lizenz, mit `K_pub` verifiziert (Plan §3.5).

Faellt in zwei Faellen bewusst auf `OSS_ENTITLEMENT` (unbegrenzt) zurueck:
- **Kein `WHO2BE_LICENSE_KEY` gesetzt** ⇒ reines OSS, On-Prem ist ohnehin
  unbegrenzt (Entscheidung #1).
- **Kein `K_pub` hinterlegt** (heute der Normalfall, nur `.gitkeep`) ⇒ es laesst
  sich nichts verifizieren; statt zu scheitern bleibt es bei OSS-unbegrenzt.

Eine **ungueltige Signatur** dagegen wird geloggt und der unverifizierte Payload
**ignoriert** — es werden niemals Features aus einer nicht verifizierbaren Lizenz
gewaehrt (Guardrail §3.6).
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from who2be_api.core.config import Settings, get_settings
from who2be_api.licensing.crypto import LicenseError, load_public_key
from who2be_api.licensing.entitlement import OSS_ENTITLEMENT, Entitlement
from who2be_api.licensing.license import entitlement_from_license

logger = logging.getLogger(__name__)


class OnPremEntitlementAdapter:
    """Loest das Entitlement aus der lokalen, signierten Lizenzdatei auf."""

    def __init__(self, settings: Settings | None = None, keys_dir: Path | None = None) -> None:
        self._settings = settings or get_settings()
        self._keys_dir = keys_dir

    async def resolve(self, org_id: UUID) -> Entitlement:
        license_key = self._settings.license_key.strip()
        if not license_key:
            return OSS_ENTITLEMENT
        try:
            public_key = load_public_key(self._keys_dir)
        except LicenseError:
            logger.error("K_pub ist unbrauchbar — falle auf OSS-Entitlement zurueck.")
            return OSS_ENTITLEMENT
        if public_key is None:
            logger.warning(
                "WHO2BE_LICENSE_KEY gesetzt, aber kein K_pub hinterlegt — "
                "keine Verifikation moeglich, OSS-Entitlement bleibt aktiv."
            )
            return OSS_ENTITLEMENT
        try:
            from who2be_api.licensing.crypto import verify_license_token

            payload = verify_license_token(license_key, public_key)
            return entitlement_from_license(payload)
        except LicenseError as exc:
            logger.error("On-Prem-Lizenz konnte nicht verifiziert werden: %s", exc)
            return OSS_ENTITLEMENT
