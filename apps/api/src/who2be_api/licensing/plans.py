"""Cloud-Plan-Tiers (Free/Pro) — Code-Spiegel von `docs/licensing/plans.md`.

Single Source of Truth fuer Menschen ist die Markdown-Datei; dieses Modul haelt
die maschinenlesbaren Konstanten, die der **Checkout** in die Mollie-Metadata
schreibt. Der Pull-Adapter liest die Werte spaeter aus genau dieser Metadata
zurueck — es gibt also bewusst **kein** hartkodiertes Produkt→Feature-Mapping im
Webhook-Pfad (Guardrail §3.6), nur diese eine Stelle, die einen gebuchten Tier
beim Checkout in Metadata uebersetzt.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from who2be_api.licensing.entitlement import Feature

# Metadaten-Schluessel (Konvention, identisch zu docs/licensing/plans.md).
META_ORG_ID = "org_id"
META_LICENSE_POLICY = "license_policy"
META_MCP_MONTHLY_QUOTA = "mcp_monthly_quota"
META_MCP_RATE_PER_MIN = "mcp_rate_per_min"
# Operativer Zusatz-Key: erlaubt dem Webhook, beim Anlegen der Folge-Subscription
# Preis/Intervall des gebuchten Tiers wiederzufinden (nicht Teil der
# entitlement-ableitenden Konvention oben).
META_PLAN_CODE = "plan_code"


@dataclass(frozen=True)
class Plan:
    """Ein buchbarer Plan-Tier.

    `price_eur` ist der monatliche Preis als Mollie-Decimal-String (z. B.
    ``"29.00"``); `interval` folgt der Mollie-Syntax (``"1 month"``). `features`
    ist ein **Superset**-Set: Pro enthaelt `core`, damit core-gated Reads fuer
    zahlende Orgs nicht fehlschlagen.
    """

    code: str
    name: str
    price_eur: str
    interval: str
    features: frozenset[str]
    mcp_monthly_quota: int
    mcp_rate_per_min: int

    def metadata(self, org_id: UUID) -> dict[str, str]:
        """Baut die Mollie-Metadata fuer diesen Plan + Org (Konvention §3.2).

        `license_policy` ist die sortierte, whitespace-separierte Feature-Liste —
        der Pull-Adapter parst sie spaeter wieder zurueck.
        """
        return {
            META_ORG_ID: str(org_id),
            META_LICENSE_POLICY: " ".join(sorted(self.features)),
            META_MCP_MONTHLY_QUOTA: str(self.mcp_monthly_quota),
            META_MCP_RATE_PER_MIN: str(self.mcp_rate_per_min),
            META_PLAN_CODE: self.code,
        }


# Free == CLOUD_FREE_ENTITLEMENT (kein Abo, Default jeder frischen Cloud-Org).
FREE_PLAN = Plan(
    code="free",
    name="Free",
    price_eur="0.00",
    interval="",
    features=frozenset({Feature.CORE}),
    mcp_monthly_quota=1_000,
    mcp_rate_per_min=30,
)

# Pro = einzelne monatliche Mollie-Subscription; Superset von Free.
PRO_PLAN = Plan(
    code="pro",
    name="Pro",
    price_eur="29.00",
    interval="1 month",
    features=frozenset(
        {
            Feature.CORE,
            Feature.COMPOSITE_PLAYBOOKS,
            Feature.AGENTS,
            Feature.AUDIT_EXPORT,
        }
    ),
    mcp_monthly_quota=100_000,
    mcp_rate_per_min=240,
)

# Nur Free ist abo-frei; jeder andere Tier ist ueber Checkout buchbar.
PAID_PLANS: dict[str, Plan] = {PRO_PLAN.code: PRO_PLAN}


def plan_by_code(code: str) -> Plan | None:
    """Liefert einen buchbaren (kostenpflichtigen) Plan oder `None`."""
    return PAID_PLANS.get(code.strip().lower())
