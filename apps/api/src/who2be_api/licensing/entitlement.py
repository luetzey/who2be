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

# Free-Tier-Obergrenze fuer Inhalts-Entities (Persona/Playbook/Resource/Agent)
# je Workspace (Plan §3.2 — Downgrade-Enforcement). Bestand bleibt lesbar; nur
# NEUE Creates ueber diese Grenze werden geblockt. Paid-Plaene + On-Prem sind
# unbegrenzt (siehe `Entitlement.entity_limit`).
FREE_ENTITY_QUOTA = 50

# Speicher-Obergrenze je Org (Issue #536, Owner-Entscheidung Option A):
# Summe der abgelegten Blob-Bytes (`wa_blob.size_bytes`). Anders als
# `entity_limit()` ist das KEINE abgeleitete Groesse, sondern ein eigenes
# Entitlement-Feld — der gebuchte Tier traegt den Wert als Provider-Metadatum
# (`storage_quota_bytes`), damit ein spaeterer dritter Tarif eine eigene Zahl
# bekommen kann, ohne dass die Ableitung „Paid ⇒ unbegrenzt" im Weg steht.
FREE_STORAGE_QUOTA_BYTES = 100 * 1024 * 1024  # 100 MiB
PRO_STORAGE_QUOTA_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB


class Entitlement(BaseModel):
    """Aufgeloeste Nutzungsrechte einer Org.

    `mcp_monthly_quota` / `mcp_rate_per_min` / `storage_quota_bytes` sind
    `None` = unbegrenzt (On-Prem/OSS-Default). `status`
    plus `expires_at` bestimmen `is_active()`; nur ein aktives Entitlement laesst
    gated Reads durch.

    `grace_until` ist ein reines **Dunning-Signal** (Banner): es liegt vor, solange
    eine fehlgeschlagene Zahlung in der Grace-Period nachgeholt werden kann. Es
    steuert den Zugriff nicht selbst — die Sperre nach Ablauf laeuft ueber
    `expires_at` (das der Webhook auf dieselbe Frist setzt), sodass `is_active()`
    unveraendert die einzige Zugriffs-Wahrheit bleibt.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["active", "inactive"] = "active"
    features: frozenset[str] = Field(default_factory=frozenset)
    expires_at: datetime | None = None
    mcp_monthly_quota: int | None = None
    mcp_rate_per_min: int | None = None
    # Summe der abgelegten Blob-Bytes je Workspace (Issue #536). `None` =
    # unbegrenzt — der On-Prem/OSS-Default und der Zustand jeder Bestands-Zeile
    # in `org_entitlement`, die vor Migration 0084 geschrieben wurde.
    storage_quota_bytes: int | None = None
    grace_until: datetime | None = None

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

    def entity_limit(self, now: datetime | None = None) -> int | None:
        """Max. Anzahl Inhalts-Entities je Workspace (None = unbegrenzt, Plan §3.2).

        Aus den Feature-Codes abgeleitet, bewusst **ohne** zusaetzliche
        DB-Spalte — so wirkt die Grenze auch dann, wenn der Billing-Webhook
        (Track P) ein heruntergestuftes Entitlement schreibt, ohne dieses Feld
        zu kennen:
          * **Free** (nur `core`) oder **inaktiv** (Kuendigung/Fehlzahlung nach
            Ablauf der Grace) ⇒ `FREE_ENTITY_QUOTA`.
          * Jeder Plan mit Paid-Features (Pro/Enterprise) und On-Prem/OSS
            (`ALL_FEATURES`) ⇒ unbegrenzt.
        """
        if not self.is_active(now):
            return FREE_ENTITY_QUOTA
        paid_features = self.features - {Feature.CORE}
        return None if paid_features else FREE_ENTITY_QUOTA


# On-Prem/OSS-Default: alle Features, unbegrenzt, kein Ablauf (Plan §3.5).
OSS_ENTITLEMENT = Entitlement(
    status="active",
    features=ALL_FEATURES,
    expires_at=None,
    mcp_monthly_quota=None,
    mcp_rate_per_min=None,
    storage_quota_bytes=None,
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
    storage_quota_bytes=FREE_STORAGE_QUOTA_BYTES,
)
