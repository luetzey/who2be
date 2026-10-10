"""Betreiber-Pruefung im Kern (ADR-0057 §7 mit Nachtrag 2026-10-10).

Betreiber sind die Menschen, die eine Who2Be-Instanz betreiben — nicht die
Admins einer Kunden-Organisation. Nur sie sehen workspace-uebergreifende
Betriebsdaten wie die Hintergrund-Routinen des Workers.

Wer Betreiber ist, steht in einer Allowlist aus User-UUIDs in der Variable
`WHO2BE_OPERATORS`. Die Regel gilt fuer **beide Editionen** (Owner-Entscheidung
E2a, 2026-10-10): die in ADR-0057 §7 urspruenglich vorgesehene On-Prem-Regel
„Org-Admin der Bootstrap-Org" ist im Code nicht eindeutig bestimmbar, siehe
Nachtrag in der ADR.

Semantik (verbindlich, ADR-0057 §7; gleich wie die Billing-Allowlist aus
ADR-0028):

- kommaseparierte User-UUIDs, Leerzeichen um die Eintraege werden getrimmt;
- Default leer ⇒ **niemand** ist Betreiber (fail-closed);
- unparsbare Eintraege werden geloggt und verworfen — ein Tippfehler darf die
  Liste nie oeffnen;
- je Aufruf gelesen, nicht gecacht: eine Rotation greift ohne Neustart;
- API-Tokens sind nie Betreiber, auch wenn ihr Besitzer gelistet ist.

`parse_uuid_allowlist` ist der **einzige** Parser fuer solche Allowlists.
Billing ruft ihn fuer seine eigene, unveraenderte Variable
`WHO2BE_BILLING_OVERRIDE_OPERATORS` auf (`who2be_billing/router.py#_override_operator_ids`);
die Variable selbst bleibt paketlokal, weil der Kern keine billing-only-
Konfiguration traegt (ADR-0029).
"""

from __future__ import annotations

import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status

from who2be_api.core.security import (
    CurrentPrincipal,
    WorkspaceContext,
    get_current_principal,
    is_machine_token,
)

logger = logging.getLogger(__name__)

OPERATORS_ENV = "WHO2BE_OPERATORS"


def parse_uuid_allowlist(env_name: str) -> frozenset[UUID]:
    """Liest eine kommaseparierte UUID-Allowlist aus der Variable `env_name`.

    Fehlt die Variable oder ist sie leer, ist das Ergebnis leer. Unparsbare
    Eintraege werden mit Variablennamen (nie mit dem Wert) geloggt und
    verworfen. Bewusst ungecacht, damit Rotation und `monkeypatch.setenv`
    ohne Neustart greifen.
    """
    ids: set[UUID] = set()
    for part in os.environ.get(env_name, "").split(","):
        candidate = part.strip()
        if not candidate:
            continue
        try:
            ids.add(UUID(candidate))
        except ValueError:
            logger.warning(
                "Unparsbarer Eintrag in %s ignoriert (erwartet: User-UUID).",
                env_name,
            )
    return frozenset(ids)


def operator_ids() -> frozenset[UUID]:
    """Die aktuell gelisteten Betreiber (`WHO2BE_OPERATORS`)."""
    return parse_uuid_allowlist(OPERATORS_ENV)


def is_operator(caller: CurrentPrincipal | WorkspaceContext) -> bool:
    """True, wenn der Aufrufer ein Mensch ist und in `WHO2BE_OPERATORS` steht.

    Nimmt beide Aufrufer-Formen an: den kontoweiten `CurrentPrincipal` (fuer
    Routen ausserhalb eines Workspaces wie die Betreiber-Sicht) und den
    `WorkspaceContext`. Ein API-Token ist in beiden Formen nie Betreiber — fuer
    Betreiber-Pfade gibt es keinen legitimen Maschinen-Aufrufer.
    """
    if isinstance(caller, WorkspaceContext):
        if caller.is_api_token:
            return False
    elif is_machine_token(caller):
        return False
    return caller.user_id in operator_ids()


async def require_operator(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> CurrentPrincipal:
    """FastAPI-Dependency: 403 fuer jeden, der kein Betreiber ist.

    Dieselbe Antwortform wie das Billing-Gate (`HTTPException` mit `detail`),
    damit das Web Nicht-Betreiber an genau einem Signal erkennt und den
    Abschnitt ausblendet (PM-W7). Leere Allowlist ⇒ immer 403.
    """
    if not is_operator(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Nur fuer Betreiber dieser Instanz (ADR-0057) — der aufrufende "
                f"User steht nicht in der Betreiber-Allowlist ({OPERATORS_ENV})."
            ),
        )
    return principal


__all__ = [
    "OPERATORS_ENV",
    "is_operator",
    "operator_ids",
    "parse_uuid_allowlist",
    "require_operator",
]
