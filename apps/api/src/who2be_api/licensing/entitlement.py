"""Entitlement — Single Source of Truth pro Org (Plan §3.5).

Leitprinzip der Licensing-Standards: *Das Nutzungsrecht entscheidet die App
ueber Entitlements — der Zahlungsanbieter meldet nur Ereignisse, er steuert den
Zugriff nicht.* Jede gated Feature-/Read-Abfrage prueft dieses Objekt, niemals
den rohen Zahlungsstatus.

Das Modell ist bewusst herkunfts-agnostisch: ob es aus einem Cloud-Webhook
(`adapters/cloud.py`) oder einer signierten On-Prem-Lizenz (`adapters/onprem.py`)
stammt, ist fuer den Kern unsichtbar. `OSS_ENTITLEMENT` ist der unbegrenzte
Default fuer On-Prem/OSS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Feature:
    """Stabile Feature-Codes (Provider-Metadaten mappen auf genau diese Strings).

    Bewusst **kein** hartkodiertes Produkt→Feature-Mapping: der Zahlungsanbieter
    traegt die freigeschalteten Codes als Metadaten (`license_policy`); hier
    stehen nur die bekannten Code-Konstanten zur typsicheren Verwendung im Kern.
    """

    CORE = "core"
    COMPOSITE_PLAYBOOKS = "composite_playbooks"
    AGENTS = "agents"
    SSO = "sso"
    AUDIT_EXPORT = "audit_export"


# Vollsatz aller bekannten Features — `OSS_ENTITLEMENT` schaltet alles frei.
ALL_FEATURES: frozenset[str] = frozenset(
    {
        Feature.CORE,
        Feature.COMPOSITE_PLAYBOOKS,
        Feature.AGENTS,
        Feature.SSO,
        Feature.AUDIT_EXPORT,
    }
)


class Entitlement(BaseModel):
    """Aufgeloeste Nutzungsrechte einer Org.

    `mcp_monthly_quota` / `mcp_rate_per_min` sind `None` = unbegrenzt. `status`
    plus `expires_at` bestimmen `is_active()`; nur ein aktives Entitlement laesst
    gated Reads durch.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["active", "inactive"] = "active"
    features: frozenset[str] = Field(default_factory=frozenset)
    expires_at: datetime | None = None
    mcp_monthly_quota: int | None = None
    mcp_rate_per_min: int | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        """True, wenn `status='active'` und (falls gesetzt) `expires_at` in der Zukunft liegt."""
        if self.status != "active":
            return False
        if self.expires_at is not None:
            reference = now or datetime.now(UTC)
            if self.expires_at <= reference:
                return False
        return True

    def has_feature(self, feature: str) -> bool:
        """True, wenn das Feature freigeschaltet ist (und das Entitlement aktiv ist)."""
        return self.is_active() and feature in self.features


# On-Prem/OSS-Default: alle Features, unbegrenzt, kein Ablauf (Plan §3.5).
OSS_ENTITLEMENT = Entitlement(
    status="active",
    features=ALL_FEATURES,
    expires_at=None,
    mcp_monthly_quota=None,
    mcp_rate_per_min=None,
)

# Cloud-Default fuer Orgs ohne aktiven Plan (z. B. frisch registriert, vor dem
# ersten Webhook). Aktiv, aber mit knappem Kontingent — der Webhook hebt das
# Entitlement bei Bezahlung an, Kuendigung/Fehlzahlung setzt es auf `inactive`.
CLOUD_FREE_ENTITLEMENT = Entitlement(
    status="active",
    features=frozenset({Feature.CORE}),
    expires_at=None,
    mcp_monthly_quota=1_000,
    mcp_rate_per_min=30,
)
