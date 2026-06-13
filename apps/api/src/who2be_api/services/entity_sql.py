"""Geteilte SQL-Identifier-Whitelist fuer Inhalts-Aggregate (Zero-Trust).

`persona`/`playbook`/`resource` fliessen an mehreren Stellen als f-String-
Tabellennamen in rohes SQL (Einzel-Export, GDPR-Export). Heute immer Literale
aus dem Router — aber ein kuenftiger dynamischer Aufrufer waere sonst
injizierbar. Daher EINE harte Whitelist, gegen die jeder SQL-bauende Pfad
zuerst prueft (Defense-in-Depth, statt Call-Site-Disziplin per Kommentar).
"""

from __future__ import annotations

from typing import Literal

EntityKind = Literal["persona", "playbook", "resource"]

# Erlaubte Inhalts-Tabellen als SQL-Identifier. `system_prompt_template` ist
# bewusst nicht enthalten — Export/GDPR decken nur die drei Kern-Aggregate ab.
ALLOWED_ENTITIES: frozenset[str] = frozenset({"persona", "playbook", "resource"})


def safe_entity(entity: str) -> EntityKind:
    """Erlaubt nur die drei bekannten Inhalts-Tabellen als SQL-Identifier.

    Greift, falls ueber einen `Any`-Pfad doch ein Nicht-Literal hereinkommt.
    """
    if entity not in ALLOWED_ENTITIES:
        raise ValueError(f"Unbekannte Inhalts-Entity: {entity!r}")
    # Nach der Whitelist-Pruefung ist der Wert garantiert einer der Literale.
    return entity  # type: ignore[return-value]
