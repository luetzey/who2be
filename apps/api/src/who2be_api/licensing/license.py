"""On-Prem-Lizenz-Payload → `Entitlement` (Plan §3.5).

Der verifizierte Lizenz-Payload (siehe `crypto.verify_license_token`) traegt die
freigeschalteten Features + optionale Limits. Diese Funktion bildet ihn auf das
herkunfts-agnostische `Entitlement` ab. Defensive Parser: ein fehlerhaftes Feld
fuehrt zu `LicenseError`, nie zu einer stillen Voll-Freischaltung.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from who2be_api.licensing.crypto import LicenseError
from who2be_api.licensing.entitlement import Entitlement


def _parse_features(raw: Any) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise LicenseError("Lizenz-Feld 'features' muss eine String-Liste sein.")
    return frozenset(raw)


def _parse_expires_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return datetime.fromtimestamp(raw, tz=UTC)
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise LicenseError("Lizenz-Feld 'expires_at' ist kein ISO-Datum.") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise LicenseError("Lizenz-Feld 'expires_at' hat einen unerwarteten Typ.")


def _parse_optional_int(raw: Any, field: str) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise LicenseError(f"Lizenz-Feld '{field}' muss eine Ganzzahl sein.")
    return raw


def entitlement_from_license(payload: dict[str, Any]) -> Entitlement:
    """Baut ein `Entitlement` aus dem verifizierten Lizenz-Payload."""
    return Entitlement(
        status="active",
        features=_parse_features(payload.get("features")),
        expires_at=_parse_expires_at(payload.get("expires_at")),
        mcp_monthly_quota=_parse_optional_int(
            payload.get("mcp_monthly_quota"), "mcp_monthly_quota"
        ),
        mcp_rate_per_min=_parse_optional_int(payload.get("mcp_rate_per_min"), "mcp_rate_per_min"),
    )
