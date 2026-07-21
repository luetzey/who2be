"""Edition-Flag: Cloud vs. On-Prem (Plan §3.5/§3.6, Entscheidung #1).

Ein Codebase, zwei Build-Profile (ADR-0029): `WHO2BE_EDITION` waehlt zur
Laufzeit den Adapter, aber die Artefakte unterscheiden sich physisch um das
Billing-Paket (`who2be-billing` nur im Cloud-Build). `is_cloud()` ist das
einzige Gate, das Cloud-spezifische Adapter (Billing-Webhook, MCP-Limit)
scharfschaltet — On-Prem/OSS laeuft unbegrenzt und ohne Billing.
"""

from who2be_api.core.config import Settings, get_settings


def current_edition(settings: Settings | None = None) -> str:
    """Liefert die aktive Edition (`'cloud'` oder `'onprem'`)."""
    return (settings or get_settings()).edition


def is_cloud(settings: Settings | None = None) -> bool:
    """True nur in der Cloud-Edition — schaltet Limits + Billing-Adapter scharf."""
    return current_edition(settings) == "cloud"


def is_onprem(settings: Settings | None = None) -> bool:
    """True fuer On-Prem/OSS (unbegrenzt, kein Billing)."""
    return not is_cloud(settings)
