"""Edition-Flag: Cloud vs. On-Prem (Plan §3.5/§3.6, Entscheidung #1).

Ein unveraendertes Docker-Artefakt fuer beide Targets; der Unterschied liegt
allein in `WHO2BE_EDITION` (12-Factor III). `is_cloud()` ist das einzige Gate,
das Cloud-spezifische Adapter (Billing-Webhook, MCP-Limit) scharfschaltet —
On-Prem/OSS laeuft unbegrenzt und ohne Billing.
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
