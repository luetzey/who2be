"""Berechnet die „zugewiesenen" Lese-Mengen eines Agenten (Read-Scoping).

Wenn die Tool-Policy eines Agenten `playbook_read`/`resource_read` auf
``assigned`` setzt, darf der Agent nur die ueber seine Persona zugewiesenen
Playbooks und die daraus erreichbaren Resources sehen — nicht den ganzen
Workspace. Diese Modul-Funktionen liefern die erlaubten ID-Mengen, die die
Read-Services dann als `restrict_ids`-Filter an die Repositories durchreichen.

Erreichbarkeit (transitiv, damit Composite-Playbooks/Sub-Resources nutzbar
bleiben):
- **Playbooks**: die der Persona direkt verknuepften Playbooks plus deren
  Composition-Closure (`playbook_composition`).
- **Resources**: alle Resources, die von einem zugewiesenen Playbook verlinkt
  sind (`playbook_resource_link`), plus deren Sub-Resource-Closure
  (`resource_composition`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TypeAlias
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_models import AgentCapability, ReadScope

# Persona → direkt verknuepfte Playbooks + transitive Composition-Kinder.
_ASSIGNED_PLAYBOOKS_SQL = """
WITH RECURSIVE seed(id) AS (
    SELECT pp.playbook_id
    FROM agent a
    JOIN persona_playbook pp ON pp.persona_id = a.persona_id
    WHERE a.id = $1 AND a.workspace_id = $2
),
closure(id) AS (
    SELECT id FROM seed
    UNION
    SELECT pc.child_id
    FROM playbook_composition pc
    JOIN closure c ON pc.parent_id = c.id
    WHERE pc.workspace_id = $2
)
SELECT id FROM closure
"""

# Zugewiesene Playbooks → verlinkte Resources + transitive Sub-Resource-Kinder.
_ASSIGNED_RESOURCES_SQL = """
WITH RECURSIVE pb(id) AS (
    SELECT pp.playbook_id
    FROM agent a
    JOIN persona_playbook pp ON pp.persona_id = a.persona_id
    WHERE a.id = $1 AND a.workspace_id = $2
    UNION
    SELECT pc.child_id
    FROM playbook_composition pc
    JOIN pb ON pc.parent_id = pb.id
    WHERE pc.workspace_id = $2
),
seed(id) AS (
    SELECT prl.resource_id
    FROM playbook_resource_link prl
    WHERE prl.workspace_id = $2 AND prl.playbook_id IN (SELECT id FROM pb)
),
closure(id) AS (
    SELECT id FROM seed
    UNION
    SELECT rc.child_id
    FROM resource_composition rc
    JOIN closure c ON rc.parent_id = c.id
    WHERE rc.workspace_id = $2
)
SELECT id FROM closure
"""


# `Pool | Connection`: die REST-Services reichen den Pool durch, der Render-Pfad
# (Placeholder-Resolver) eine bereits acquirte Single-Connection — beide haben
# `.fetch` mit identischer Signatur.
_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_AGENT_PERSONA_SQL = "SELECT persona_id FROM agent WHERE id = $1 AND workspace_id = $2"


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


async def _require_agent_persona(pool: _Fetcher, workspace_id: UUID, agent_id: UUID) -> UUID | None:
    """Persona-ID des Agenten; 404 fuer unbekannte/workspace-fremde Agenten.

    Der `?agent=`-Listenfilter darf keine Existenz-Orakel ueber fremde
    Workspaces bilden — ein Agent ausserhalb des Request-Workspace ist von
    einem nicht existierenden nicht unterscheidbar (beides 404).
    """
    row = await pool.fetchrow(_AGENT_PERSONA_SQL, agent_id, workspace_id)
    if row is None:
        raise _agent_not_found()
    persona_id: UUID | None = row["persona_id"]
    return persona_id


async def agent_filter_persona_ids(
    pool: _Fetcher, workspace_id: UUID, agent_id: UUID
) -> list[UUID]:
    """`?agent=`-Filter fuer die Persona-Liste: genau die Persona des Agenten.

    Leere Liste (= keine Treffer) fuer eine Agent-Huelle ohne Persona;
    404 fuer unbekannte/workspace-fremde Agenten.
    """
    persona_id = await _require_agent_persona(pool, workspace_id, agent_id)
    return [] if persona_id is None else [persona_id]


async def agent_filter_playbook_ids(
    pool: _Fetcher, workspace_id: UUID, agent_id: UUID
) -> list[UUID]:
    """`?agent=`-Filter fuer die Playbook-Liste (inkl. Composite-Closure).

    404 fuer unbekannte/workspace-fremde Agenten (anders als
    `assigned_playbook_ids`, das dann still leer liefert).
    """
    await _require_agent_persona(pool, workspace_id, agent_id)
    return sorted(await assigned_playbook_ids(pool, workspace_id, agent_id))


async def agent_filter_resource_ids(
    pool: _Fetcher, workspace_id: UUID, agent_id: UUID
) -> list[UUID]:
    """`?agent=`-Filter fuer die Resource-Liste (inkl. Sub-Resource-Closure)."""
    await _require_agent_persona(pool, workspace_id, agent_id)
    return sorted(await assigned_resource_ids(pool, workspace_id, agent_id))


async def assigned_playbook_ids(pool: _Fetcher, workspace_id: UUID, agent_id: UUID) -> set[UUID]:
    """IDs der dem Agenten (ueber seine Persona) zugewiesenen Playbooks."""
    rows = await pool.fetch(_ASSIGNED_PLAYBOOKS_SQL, agent_id, workspace_id)
    return {row["id"] for row in rows}


async def assigned_resource_ids(pool: _Fetcher, workspace_id: UUID, agent_id: UUID) -> set[UUID]:
    """IDs der aus den zugewiesenen Playbooks erreichbaren Resources."""
    rows = await pool.fetch(_ASSIGNED_RESOURCES_SQL, agent_id, workspace_id)
    return {row["id"] for row in rows}


def require_read_flag(ctx: WorkspaceContext, flag: str, domain: str) -> None:
    """An/Aus-Lesegate (No-Op fuer ungebundene Tokens).

    Fuer Reads ohne Scope-Abstufung (`persona_read`): ist der Token an einen
    Agenten gebunden und das Flag aus, wirft das ein 403.
    """
    policy = ctx.tool_policy
    if policy is None:
        return
    if not getattr(policy, flag):
        raise _tool_unavailable(domain)


def agent_read_restrict(ctx: WorkspaceContext) -> set[UUID] | None:
    """`restrict_ids` fuer Agent-Reads gemaess `agent_read`-Scope (DB-frei).

    `None` = keine Einschraenkung (ungebundener Token/Mensch oder Scope `all`).
    Bei `assigned` die Menge ``{ctx.agent_id}`` — der Agent sieht nur sich selbst.
    Bei `none` ein 403, weil das Tool fuer den Agenten gar nicht verfuegbar ist.
    """
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.agent_read == ReadScope.all:
        return None
    if policy.agent_read == ReadScope.none:
        raise _tool_unavailable("Agenten")
    return {ctx.agent_id}


def _tool_unavailable(domain: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Dieser Agent darf keine {domain} lesen. "
            "Der Workspace-Besitzer kann den Lesezugriff in der Agent-Konfiguration freischalten."
        ),
    )


async def playbook_read_restrict(pool: asyncpg.Pool, ctx: WorkspaceContext) -> list[UUID] | None:
    """`restrict_ids` fuer Playbook-Reads gemaess Policy.

    `None` = keine Einschraenkung (ungebundener Token oder Scope `all`). Bei
    `assigned` die sortierte Liste der zugewiesenen Playbook-IDs (ggf. leer);
    bei `none` ein 403, weil das Tool fuer den Agenten gar nicht verfuegbar ist.
    """
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.playbook_read == ReadScope.all:
        return None
    if policy.playbook_read == ReadScope.none:
        raise _tool_unavailable("Playbooks")
    return sorted(await assigned_playbook_ids(pool, ctx.workspace_id, ctx.agent_id))


async def resource_read_restrict(pool: asyncpg.Pool, ctx: WorkspaceContext) -> list[UUID] | None:
    """`restrict_ids` fuer Resource-Reads gemaess Policy (siehe playbook-Variante)."""
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.resource_read == ReadScope.all:
        return None
    if policy.resource_read == ReadScope.none:
        raise _tool_unavailable("Resources")
    return sorted(await assigned_resource_ids(pool, ctx.workspace_id, ctx.agent_id))


async def visible_playbook_ids(
    pool: asyncpg.Pool | None, ctx: WorkspaceContext
) -> set[UUID] | None:
    """Sichtbare Playbook-IDs fuer Sekundaer-Reads (Composition/Links/Usages).

    Diese Reads laufen nicht ueber die `restrict_ids`-Repos der Haupt-Lesepfade
    und brauchen daher denselben `assigned`-Scope explizit: Gate die per-ID
    abgefragte Entitaet bzw. filtere zurueckgegebene Listen gegen diese Menge.

    `None` = keine Einschraenkung (ungebundener Token oder Scope `all`; oder
    Test-Fake ohne Pool). Sonst die Menge der zugewiesenen Playbook-IDs. Bei
    Scope `none` wirft `playbook_read_restrict` ein 403.
    """
    if pool is None:
        return None
    restrict = await playbook_read_restrict(pool, ctx)
    return None if restrict is None else set(restrict)


async def visible_resource_ids(
    pool: asyncpg.Pool | None, ctx: WorkspaceContext
) -> set[UUID] | None:
    """Sichtbare Resource-IDs fuer Sekundaer-Reads (siehe `visible_playbook_ids`)."""
    if pool is None:
        return None
    restrict = await resource_read_restrict(pool, ctx)
    return None if restrict is None else set(restrict)


@dataclass(frozen=True)
class ReadableScope:
    """Was ein Aufrufer inhaltlich finden darf (ADR-0037 §47, ADR-0046).

    `types` sind die nach Policy verbliebenen Element-Typen. `restrict` bildet
    Typ → erlaubte IDs ab und geht als Praedikat IN die Such-Query: ein
    fehlender Schluessel heisst „keine Einschraenkung", eine leere Liste
    „nichts sichtbar". `playbooks`/`resources` tragen dieselben Mengen als Set
    fuer den nachgelagerten Defense-in-Depth-Filter (`None` = unbeschraenkt).
    """

    types: list[str]
    restrict: dict[str, list[UUID]] = field(default_factory=dict)
    playbooks: set[UUID] | None = None
    resources: set[UUID] | None = None


async def readable_content_scope(
    pool: asyncpg.Pool | None, ctx: WorkspaceContext, requested: Sequence[str]
) -> ReadableScope:
    """Berechnet den Such-Scope eines Aufrufers ueber Inhalts-Elemente.

    Single-Source fuer beide Suchpfade (Entity-Suche und Passage-Suche), damit
    sie nicht auseinanderlaufen.

    Zwei Eigenschaften sind hier wesentlich:

    1. Die ID-Mengen werden VOR dem Ranking gebildet, damit die Query sie als
       Praedikat nutzen kann. Nachfiltern hinter dem `LIMIT` liefert `[]`,
       sobald die globalen Top-k ausserhalb des zugewiesenen Sets liegen.
    2. Sie werden nur fuer TATSAECHLICH angefragte Typen geholt. Die
       `*_read_restrict`-Helfer werfen bei Scope `none` ein 403 — ein Typ, der
       ohnehin schon aus der Anfrage gefallen ist, darf die uebrige Suche
       nicht mit 403 abbrechen.

    `system_prompt_template` haengt an der Capability `system_prompt_write`
    (ADR-0040), nicht an einem Read-Scope — Templates sind kein Agenten-
    Lesestoff, solange der Agent sie nicht auch pflegen darf.
    """
    policy = ctx.tool_policy
    allowed: list[str] = []
    for entity_type in requested:
        if policy is not None:
            if entity_type == "persona" and not policy.persona_read:
                continue
            if entity_type == "playbook" and policy.playbook_read == ReadScope.none:
                continue
            if entity_type == "resource" and policy.resource_read == ReadScope.none:
                continue
            if entity_type == "external_tool" and policy.external_tool_read == ReadScope.none:
                continue
            if entity_type == "system_prompt_template" and not policy.allows(
                AgentCapability.system_prompt_write
            ):
                continue
        allowed.append(entity_type)

    if not allowed:
        return ReadableScope(types=[])

    restrict: dict[str, list[UUID]] = {}
    playbooks: set[UUID] | None = None
    resources: set[UUID] | None = None
    if "playbook" in allowed:
        playbooks = await visible_playbook_ids(pool, ctx)
        if playbooks is not None:
            restrict["playbook"] = sorted(playbooks)
    if "resource" in allowed:
        resources = await visible_resource_ids(pool, ctx)
        if resources is not None:
            restrict["resource"] = sorted(resources)
    return ReadableScope(types=allowed, restrict=restrict, playbooks=playbooks, resources=resources)


def require_external_tool_read(ctx: WorkspaceContext) -> None:
    """Read-Gate fuer das ExternalTool-Aggregat (WP-3): `none` sperrt komplett.

    Anders als Playbook/Resource/Agent gibt es fuer `external_tool_read` KEINE
    `assigned`-Teilmenge zu berechnen (ExternalTool ist ein flacher
    Workspace-Katalog ohne Persona-/Playbook-Zuordnung) — deshalb liefert diese
    Funktion (anders als `playbook_read_restrict`/`resource_read_restrict`)
    keine `restrict_ids`-Liste, sondern ist ein reines An/Aus-Gate: `assigned`
    verhaelt sich wie `all` (No-Op), nur `none` wirft 403. No-Op fuer
    ungebundene Tokens/Mensch (`tool_policy is None`).
    """
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return
    if policy.external_tool_read == ReadScope.none:
        raise _tool_unavailable("Externe Tools")
