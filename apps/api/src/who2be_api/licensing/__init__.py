"""Licensing/Entitlement-Schicht (Track D).

Hexagonale Umsetzung der Notion-Vault-Standards *Deployment-Standards (Single
Codebase)* + *Licensing-Standards (Entitlements)*:

- **Ein Build, eine Codebasis** — der Unterschied Cloud vs. On-Prem ist reine
  Runtime-Config (`WHO2BE_EDITION`, siehe `edition.py`), kein Fork.
- **Das Entitlement ist die Single Source of Truth** pro Org (`entitlement.py`):
  jede gated Abfrage prueft das aufgeloeste Entitlement, **nie** den rohen
  Zahlungsstatus.
- **`EntitlementPort` + austauschbare Adapter** (`port.py`, `adapters/`): der Kern
  liest nur das aufgeloeste Entitlement; die Herkunft (Cloud-Webhook bzw.
  On-Prem-Lizenzdatei) ist Infrastruktur hinter dem Port.
- **Billing ist ein Cloud-Adapter**, nicht im Kern (`billing.py` wird nur unter
  `is_cloud()` aktiviert).
"""

from who2be_api.licensing.edition import current_edition, is_cloud, is_onprem
from who2be_api.licensing.entitlement import (
    ALL_FEATURES,
    CLOUD_FREE_ENTITLEMENT,
    OSS_ENTITLEMENT,
    Entitlement,
    Feature,
)
from who2be_api.licensing.port import EntitlementPort
from who2be_api.licensing.service import EntitlementService, build_entitlement_port

__all__ = [
    "ALL_FEATURES",
    "CLOUD_FREE_ENTITLEMENT",
    "OSS_ENTITLEMENT",
    "Entitlement",
    "EntitlementPort",
    "EntitlementService",
    "Feature",
    "build_entitlement_port",
    "current_edition",
    "is_cloud",
    "is_onprem",
]
