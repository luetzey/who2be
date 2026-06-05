"""Licensing/Entitlement-Schicht (Track D).

Hexagonale Umsetzung der Notion-Vault-Standards *Deployment-Standards (Single
Codebase)* + *Licensing-Standards (Entitlements)*:

- **Ein Codebase, zwei Build-Profile** (ADR-0029) — die Read-Seite ist editions-
  neutral und nach `WHO2BE_EDITION` aufgeloest (`edition.py`); die Billing-
  *Schreibseite* lebt im optionalen Paket `who2be-billing` und ist im On-Prem-
  Artefakt physisch nicht vorhanden (Build-Zeit-Isolation, nicht nur Runtime).
- **Das Entitlement ist die Single Source of Truth** pro Org (`entitlement.py`):
  jede gated Abfrage prueft das aufgeloeste Entitlement, **nie** den rohen
  Zahlungsstatus. Geschrieben wird es nur von klar benannten Quellen
  (`mollie`/`cloud`/`manual_override`/`signed_license`, ADR-0028), nie von der
  ausgelieferten Read-App.
- **`EntitlementPort` + austauschbare Adapter** (`port.py`, `adapters/`): der Kern
  liest nur das aufgeloeste Entitlement; die Herkunft (Cloud-DB bzw.
  On-Prem-Lizenz-Token) ist Infrastruktur hinter dem Port.
- **Billing ist ein separates Cloud-Paket** (`who2be-billing`), nicht im Kern:
  `who2be_api.main` bindet es ueber optionalen Import unter `is_cloud()` ein.
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
