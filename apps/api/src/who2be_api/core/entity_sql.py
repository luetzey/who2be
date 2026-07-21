"""Geteilte SQL-Identifier-Whitelist fuer Inhalts-Aggregate (Zero-Trust).

`persona`/`playbook`/`resource` fliessen an mehreren Stellen als f-String-
Tabellennamen in rohes SQL (Einzel-Export, GDPR-Export). Heute immer Literale
aus dem Router — aber ein kuenftiger dynamischer Aufrufer waere sonst
injizierbar. Daher EINE harte Whitelist, gegen die jeder SQL-bauende Pfad
zuerst prueft (Defense-in-Depth, statt Call-Site-Disziplin per Kommentar).

Lebt in `core/`, weil sowohl Repositories als auch Services darauf aufbauen —
eine DB-nahe Utility ohne Service-Abhaengigkeiten (Schichtung: core → repositories → services).
"""

from __future__ import annotations

from typing import Literal

EntityKind = Literal["persona", "playbook", "resource", "external_tool"]

# Erlaubte Inhalts-Tabellen als SQL-Identifier. `system_prompt_template` ist
# bewusst nicht enthalten — dessen Repository ist handgerollt (kein
# `VersionedAggregateRepository`) und Export/GDPR decken es nicht ab.
ALLOWED_ENTITIES: frozenset[str] = frozenset({"persona", "playbook", "resource", "external_tool"})


def safe_entity(entity: str) -> EntityKind:
    """Erlaubt nur die bekannten Inhalts-Tabellen als SQL-Identifier.

    Greift, falls ueber einen `Any`-Pfad doch ein Nicht-Literal hereinkommt.
    """
    if entity not in ALLOWED_ENTITIES:
        raise ValueError(f"Unbekannte Inhalts-Entity: {entity!r}")
    # Nach der Whitelist-Pruefung ist der Wert garantiert einer der Literale.
    return entity  # type: ignore[return-value]
