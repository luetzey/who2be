"""Persistenz fuer das Workspace-Aggregat (TASK-301).

Liest und schreibt `workspace`. Die Membership-Pruefung ist Aufgabe der
`WorkspaceMemberRepository`; dieses Repo arbeitet auf der Workspace-Ebene
und bekommt die User-Identitaet vom Service-Layer durchgereicht.
"""

import json
from pathlib import Path
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.core.errors import ApiGateError
from who2be_models import AgentToolPolicy, ReadScope, WorkspaceRead


async def resolve_org_id(pool: asyncpg.Pool, workspace_id: UUID) -> UUID:
    """Org des Workspace fuer org-scoped Aufloesungen (Entitlement, whoami).

    Gemeinsamer Helper fuer `routers/entitlement.py` und `routers/whoami.py`
    (COD-2, Standards-Review 2026-07-08) — vorher als `_resolve_org_id`
    copy-gepastet. Ein Workspace ohne Org ist ein inkonsistenter Zustand →
    403 statt stiller Voll-/Null-Annahme; expliziter `isinstance`-Check statt
    `assert` (asserts entfallen unter `-O`, COD-9). `ApiGateError` statt
    `HTTPException`, damit das Repository fastapi-frei bleibt (ADR-0002); der
    zentrale Handler in `main.py` serialisiert `application/problem+json`.
    """
    org_id = await pool.fetchval("SELECT org_id FROM workspace WHERE id = $1", workspace_id)
    if not isinstance(org_id, UUID):
        raise ApiGateError(
            status=403,
            reason="insufficient_role",
            actionable_by="human",
            detail="Workspace ohne Organisation.",
        )
    return org_id


class LastWorkspaceError(Exception):
    """Der letzte Workspace einer Organization sollte geloescht werden.

    Wuerde die Org fuehrungslos zuruecklassen (und den Owner aussperren) —
    deshalb verboten. Konsistent mit der Last-admin-Invariante auf Member-Ebene.
    """


async def ensure_personal_workspace(
    conn: asyncpg.Connection,
    user_id: UUID,
    *,
    user_email: str | None,
) -> UUID:
    """Lazy-Seed einer Personal-Org + Workspace + Admin-Membership.

    Idempotent: laeuft ein zweites Mal durch, ohne Duplikate anzulegen.
    Naming-Strategie fuer die Org:
      1. Local-Part der ``user_email``, falls gesetzt und valide.
      2. Fallback: ``"Personal"``.

    Gibt die ``workspace_id`` zurueck.
    """
    org_name = _org_name_from_email(user_email)
    org_id = await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) "
        "VALUES ($1, $2, 'personal') "
        "ON CONFLICT (kind, slug) DO UPDATE SET name = excluded.name "
        "RETURNING id",
        org_name,
        str(user_id),
    )
    await conn.execute(
        "INSERT INTO org_member (org_id, user_id, role) VALUES ($1, $2, 'owner') "
        "ON CONFLICT (org_id, user_id) DO NOTHING",
        org_id,
        user_id,
    )
    workspace_id: UUID = await conn.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'Personal', 'personal') "
        "ON CONFLICT (org_id, slug) DO UPDATE SET name = excluded.name "
        "RETURNING id",
        org_id,
    )
    await conn.execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) "
        "VALUES ($1, $2, 'admin') ON CONFLICT (workspace_id, user_id) DO NOTHING",
        workspace_id,
        user_id,
    )
    await _seed_default_templates(conn, workspace_id, user_id)
    await _seed_default_agents(conn, workspace_id, user_id)
    return workspace_id


def _org_name_from_email(email: str | None) -> str:
    """Leitet den Org-Namen aus dem Local-Part der E-Mail ab.

    Nur der Teil vor ``@`` wird genutzt; leere Strings und ``None`` fallen
    auf ``"Personal"`` zurueck.
    """
    if email:
        local = email.split("@")[0].strip()
        if local:
            return local
    return "Personal"


class WorkspaceRepository(Protocol):
    """Service-seitige Abstraktion fuer den Workspace-Zugriff."""

    async def list_by_org_for_user(self, org_id: UUID, user_id: UUID) -> list[WorkspaceRead]: ...

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None: ...

    async def create(self, org_id: UUID, user_id: UUID, name: str, slug: str) -> WorkspaceRead: ...

    async def update_name(self, workspace_id: UUID, name: str) -> WorkspaceRead | None: ...

    async def delete(self, workspace_id: UUID) -> bool: ...


class PgWorkspaceRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_org_for_user(self, org_id: UUID, user_id: UUID) -> list[WorkspaceRead]:
        rows = await self._pool.fetch(
            "SELECT w.id, w.org_id, w.name, w.slug, w.created_at "
            "FROM workspace w "
            "JOIN workspace_member m ON m.workspace_id = w.id "
            "WHERE w.org_id = $1 AND m.user_id = $2 "
            "ORDER BY w.created_at ASC, w.id ASC",
            org_id,
            user_id,
        )
        return [WorkspaceRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None:
        row = await self._pool.fetchrow(
            "SELECT id, org_id, name, slug, created_at FROM workspace WHERE id = $1",
            workspace_id,
        )
        return WorkspaceRead.model_validate(dict(row)) if row is not None else None

    async def create(self, org_id: UUID, user_id: UUID, name: str, slug: str) -> WorkspaceRead:
        """Neuer Workspace + Admin-Membership fuer den Anlegenden, atomar.

        Seedet zudem die drei Default-SystemPromptTemplates (Phase 3 Runde 3
        Track 3 — analog Migration 0023b fuer Bestandsworkspaces). Idempotent
        ueber `ON CONFLICT (workspace_id, slug) DO NOTHING`; bei Migration-
        plus-Create-Race greift derselbe Schutz.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO workspace (org_id, name, slug) VALUES ($1, $2, $3) "
                "RETURNING id, org_id, name, slug, created_at",
                org_id,
                name,
                slug,
            )
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'admin')",
                row["id"],
                user_id,
            )
            await _seed_default_templates(conn, row["id"], user_id)
            await _seed_default_agents(conn, row["id"], user_id)
        return WorkspaceRead.model_validate(dict(row))

    async def update_name(self, workspace_id: UUID, name: str) -> WorkspaceRead | None:
        row = await self._pool.fetchrow(
            "UPDATE workspace SET name = $1 WHERE id = $2 "
            "RETURNING id, org_id, name, slug, created_at",
            name,
            workspace_id,
        )
        return WorkspaceRead.model_validate(dict(row)) if row is not None else None

    async def delete(self, workspace_id: UUID) -> bool:
        """Loescht einen Workspace samt aller Inhalte (FK-Cascade).

        Schutz-Invariante: der **letzte** Workspace einer Org darf nicht
        geloescht werden (`LastWorkspaceError`). Die Pruefung laeuft
        transaktional mit `FOR UPDATE` auf der Workspace-Zeile, damit zwei
        parallele Loeschungen nicht beide durchrutschen.

        `agent`-Zeilen werden zuerst explizit entfernt: Ihre Composite-FKs auf
        `persona`/`system_prompt_template` sind `ON DELETE RESTRICT`. Beim
        Workspace-Cascade wuerden Persona/Template ebenfalls geloescht — die
        RESTRICT-Pruefung koennte dann je nach Cascade-Reihenfolge feuern.
        Erst Agents weg, dann Workspace → der Cascade laeuft konfliktfrei.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            org_id = await conn.fetchval(
                "SELECT org_id FROM workspace WHERE id = $1 FOR UPDATE",
                workspace_id,
            )
            if org_id is None:
                return False
            remaining = await conn.fetchval(
                "SELECT count(*) FROM workspace WHERE org_id = $1",
                org_id,
            )
            if remaining <= 1:
                raise LastWorkspaceError
            await conn.execute("DELETE FROM agent WHERE workspace_id = $1", workspace_id)
            await conn.execute("DELETE FROM workspace WHERE id = $1", workspace_id)
        return True


# BlockNote-Bodies der Default-Templates leben als Sidecar-JSON-Dateien neben
# dem Modul (Track B: Nur-BlockNote). Triple-Quoted-Stringliterale wurden von
# ruff (line-length=100) wegen der inneren JSON-Keys flach abgelehnt; die
# Sidecar-Dateien sind ausserdem die einzige Pflege-Quelle der Pill-Bodies.
def _sidecar(name: str) -> str:
    return (Path(__file__).parent / name).read_text(encoding="utf-8")


_WORKFLOW_STARTER_BLOCKNOTE_BODY = _sidecar("workflow_starter_body.json")


# Seed-Bodies fuer die Default-Templates eines neuen Workspaces. Track B
# (Nur-BlockNote): alle vier Bodies sind BlockNote-JSON mit Placeholder-Pills
# (persona-field, playbooks-catalog, tools-overview, date). Format:
# (slug, name, blocknote_body).
#
# E4-Checkliste (jedes Template enthaelt): Persona-Profil-Pill, Playbooks-
# Katalog-Pill, tools-overview-Pill, date-Pill + Agenten-Hinweise (Modi /
# Composite / Applied-vs-Triggered).
_DEFAULT_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "customer-support-agent",
        "Customer-Support-Agent",
        _sidecar("customer_support_body.json"),
    ),
    (
        "knowledge-worker",
        "Knowledge-Worker",
        _sidecar("knowledge_worker_body.json"),
    ),
    (
        "conversational-coach",
        "Conversational-Coach",
        _sidecar("conversational_coach_body.json"),
    ),
    (
        "workflow-starter",
        "Workflow-Starter",
        _WORKFLOW_STARTER_BLOCKNOTE_BODY,
    ),
    (
        "agent-builder",
        "Agent-Builder",
        _sidecar("agent_builder_body.json"),
    ),
    (
        "agent-builder-lite",
        "Agent-Builder-Lite",
        _sidecar("agent_builder_lite_body.json"),
    ),
)


async def _seed_default_templates(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID
) -> None:
    """Legt die vier Default-Templates eines neuen Workspaces an.

    Idempotent ueber ``ON CONFLICT (workspace_id, slug) DO NOTHING`` auf
    `system_prompt_template`. Versions-Insert per ``NOT EXISTS`` — wenn ein
    Template existiert (z. B. nach Re-Lauf), wird kein v1 mehr angelegt.
    Initial-Status ist `active`, sodass der Render-Endpoint sofort ohne
    Promote-Schritt feuert.
    """
    for slug, name, body in _DEFAULT_TEMPLATES:
        # Die agent-builder-Templates (voll + lite) sind managed (gesperrt +
        # zentral gepflegt); die uebrigen Default-Templates bleiben frei editierbar.
        managed = slug in (_AGENT_BUILDER_TEMPLATE_SLUG, _AGENT_BUILDER_LITE_TEMPLATE_SLUG)
        template_id = await conn.fetchval(
            "INSERT INTO system_prompt_template "
            "(workspace_id, owner_id, name, slug, is_managed, managed_content_version) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "ON CONFLICT (workspace_id, slug) DO NOTHING "
            "RETURNING id",
            workspace_id,
            owner_id,
            name,
            slug,
            managed,
            BUILDER_CONTENT_VERSION if managed else 0,
        )
        if template_id is None:
            # Template gab es schon — der Versions-Insert unten wuerde
            # ebenfalls per NOT EXISTS abprallen, aber wir sparen den
            # Roundtrip.
            continue
        await conn.execute(
            "INSERT INTO system_prompt_template_version "
            "(template_id, version, content, status, created_by) "
            "SELECT $1, 1, $2::jsonb, 'active', $3 "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM system_prompt_template_version "
            "  WHERE template_id = $1 AND version = 1"
            ")",
            template_id,
            # WICHTIG: dict uebergeben, KEINEN bereits serialisierten JSON-String.
            # Der jsonb-Codec in core/db.py ruft json.dumps auf jeden Bind-Wert —
            # eine pre-serialisierte Zeichenkette wuerde dadurch ein zweites Mal
            # in Quotes verpackt (doppelt-encodierter JSON-String statt Objekt).
            # Der ::jsonb-Cast oben aktiviert den Codec; ohne ihn fuehrt asyncpg
            # keine Typ-Inferenz fuer $2 durch und erwartet einen str.
            {"description": "", "body": body},
            owner_id,
        )


# ---------------------------------------------------------------------------
# Default-Agent „Builder" (Meta-Agent — der Agent, der Agenten baut).
#
# Wird nach den Default-Templates in jedem neuen Workspace mitgeseedet und
# spiegelt exakt die SQL-Backfill-Migration 0047 (beide Schichten synchron
# halten — bekannte Drift-Quelle, siehe Kommentar in 0023b). Inhaltlich
# re-targeted auf die Who2Be-MCP-Write-Tools (kein externer Store).
#
# Reihenfolge wegen der Composite-FKs (agent -> persona, agent -> template):
#   1. Persona „Builder"      (persona + persona_version v1 active)
#   2. 4 Playbooks            (playbook + playbook_version v1 active)
#   3. persona_playbook-Links (Persona <-> 4 Playbooks)
#   4. agent-Row              (persona_id + Template 'agent-builder' +
#                              write-faehige tool_policy, status 'enabled')
# Das Template 'agent-builder' selbst legt bereits `_seed_default_templates`
# an (Eintrag in `_DEFAULT_TEMPLATES`); hier wird nur seine id nachgeschlagen.
#
# Idempotenz: jede Identitaets-Zeile wird per NOT EXISTS (workspace_id + name
# bzw. slug) angelegt, die Links via ON CONFLICT DO NOTHING. JSONB-Bind: dict
# uebergeben, KEINEN vor-serialisierten String (Codec-Falle, siehe oben).
_BUILDER_PERSONA_NAME = "Builder"
_BUILDER_AGENT_NAME = "Builder"
_BUILDER_LITE_AGENT_NAME = "Builder-Lite"
_AGENT_BUILDER_TEMPLATE_SLUG = "agent-builder"
_AGENT_BUILDER_LITE_TEMPLATE_SLUG = "agent-builder-lite"

# Kanonischer Content-Stand des verwalteten Builders. Wird bei jeder zentralen
# Aenderung an Persona/Template/Playbooks (Sidecars) hochgezaehlt; der Start-Sync
# hebt managed-Aggregate, deren `managed_content_version` zurueckliegt, auf diesen
# Stand. Seed stempelt neue Builder direkt hierauf.
BUILDER_CONTENT_VERSION = 2

_BUILDER_PERSONA_DESCRIPTION = (
    "Meta-Agent, der Personas, Playbooks, Resources und Agenten im Workspace "
    "anlegt und pflegt — der Agent, der Agenten baut."
)
_BUILDER_PERSONA_TRAITS: tuple[str, ...] = (
    "strukturell",
    "kritisch",
    "phasen-orientiert",
    "trade-offs-explizit",
)
_BUILDER_PERSONA_TAGS: tuple[str, ...] = ("meta-agent", "agent-building", "crud")

_BUILDER_AGENT_DESCRIPTION = (
    "Standard-Meta-Agent zum Anlegen und Pflegen von Personas, Playbooks, Resources und Agenten."
)
_BUILDER_LITE_AGENT_DESCRIPTION = (
    "Schlanke Builder-Variante mit kompaktem System-Prompt — fuer LLMs mit kleinem "
    "System-Prompt-Budget. Gleiche Persona und Schreib-Policy wie der Builder."
)

# (name, type, triggers, tags, description, sidecar) — Reihenfolge fix, damit
# Python-Seed und Migration 0047 dieselben Playbooks erzeugen.
_BUILDER_PLAYBOOKS: tuple[tuple[str, str, str, tuple[str, ...], str, str], ...] = (
    (
        "Persona anlegen & pflegen",
        "workflow",
        "persona anlegen, persona bearbeiten, persona pflegen, neue persona",
        ("persona", "crud", "agent-building"),
        "Eine Persona via MCP-Write-Tools anlegen, als Draft aendern und nach active schalten.",
        "builder_playbook_persona_body.json",
    ),
    (
        "Playbook anlegen & pflegen",
        "workflow",
        "playbook anlegen, playbook bearbeiten, composite, neues playbook",
        ("playbook", "crud", "agent-building"),
        "Playbooks anlegen und pflegen — inkl. Resource-Verweisen und Composite-Sequenzen.",
        "builder_playbook_playbook_body.json",
    ),
    (
        "Agent anlegen & pflegen",
        "workflow",
        "agent anlegen, agent konfigurieren, agent bearbeiten, tool policy, agent kopieren",
        ("agent", "crud", "agent-building"),
        "Einen Agenten konfigurieren: Persona + Template verdrahten, Tool-Policy setzen, kopieren.",
        "builder_playbook_agent_body.json",
    ),
    (
        "Konsistenz- & Drift-Check",
        "checklist",
        "konsistenz, drift, pruefen, aktivierbar, activatable, qualitaetscheck",
        ("konsistenz", "qa", "agent-building"),
        "Read-only-Pruefung auf Aktivierbarkeit, aktive Versionen und sauberes Prompt-Rendering.",
        "builder_playbook_consistency_body.json",
    ),
)


def _builder_persona_content() -> dict[str, object]:
    """Persona-Versions-Content (PersonaVersionContent-Form) als dict fuer JSONB.

    Der BlockNote-Profil-Body kommt aus dem Sidecar (Array von Blocks) und wird
    unter `content.blocks` gehaengt; `modes` ist bewusst leer (Single-Mode).
    """
    blocks = json.loads(_sidecar("builder_persona_content.json"))
    return {
        "description": _BUILDER_PERSONA_DESCRIPTION,
        "traits": list(_BUILDER_PERSONA_TRAITS),
        "tags": list(_BUILDER_PERSONA_TAGS),
        "content": {"description": "", "blocks": blocks},
        "modes": [],
        "skills": [],
    }


def _builder_playbook_content(
    sidecar: str, ptype: str, tags: tuple[str, ...], triggers: str, description: str
) -> dict[str, object]:
    """Playbook-Versions-Content (PlaybookContent-Form) als dict fuer JSONB.

    `body` ist das stringifizierte BlockNote-Dokument (`json.dumps` des Sidecar-
    Arrays) — analog zum Frontend-`JSON.stringify(editor.document)`.
    """
    body = json.dumps(json.loads(_sidecar(sidecar)), ensure_ascii=False)
    return {
        "description": description,
        "body": body,
        "type": ptype,
        "tags": list(tags),
        "triggers": triggers,
    }


def _builder_tool_policy() -> dict[str, object]:
    """Write-faehige Policy fuer den Meta-Agenten (Plan §5.2).

    Alle Schreib-Capabilities + `promote_retire` + `system_prompt_write`
    (ADR-0040: Templates verfassen + zur Review einreichen; das Aktivieren bleibt
    serverseitig auch fuer den Builder gesperrt), Reads = `all`. Die Reads sind
    bewusst EXPLIZIT auf `all` gesetzt: der Meta-Agent verwaltet den ganzen
    Workspace und darf nicht den (seit „secure by default") auf `assigned`
    abgesenkten Read-Default erben. Die Autorisierung bleibt serverseitig
    (editor; Promote/Retire admin) — die Policy steuert nur die
    Tool-Sichtbarkeit im System-Prompt.
    """
    return AgentToolPolicy(
        playbook_read=ReadScope.all,
        resource_read=ReadScope.all,
        agent_read=ReadScope.all,
        persona_write=True,
        playbook_write=True,
        resource_write=True,
        agent_write=True,
        system_prompt_write=True,
        promote_retire=True,
    ).model_dump(mode="json")


async def _seed_default_agents(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID
) -> None:
    """Legt den Default-Agenten „Builder" eines neuen Workspaces an.

    Laeuft NACH `_seed_default_templates` (braucht das 'agent-builder'-Template).
    Idempotent ueber NOT-EXISTS-Guards (workspace_id + name/slug) und
    ON-CONFLICT-DO-NOTHING auf den Links. Spiegelt Migration 0047.
    """
    # 1. Persona „Builder" + v1 (active). Der NOT-EXISTS-Guard liefert None,
    #    wenn der Builder-Seed bereits lief — der Lauf ist atomar, also sind
    #    in dem Fall auch Playbooks/Agent schon da: frueh raus.
    persona_id = await conn.fetchval(
        "INSERT INTO persona "
        "(workspace_id, owner_id, name, is_managed, managed_content_version) "
        "SELECT $1, $2, $3, true, $4 "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM persona WHERE workspace_id = $1 AND name = $3"
        ") "
        "RETURNING id",
        workspace_id,
        owner_id,
        _BUILDER_PERSONA_NAME,
        BUILDER_CONTENT_VERSION,
    )
    if persona_id is None:
        return
    await conn.execute(
        "INSERT INTO persona_version "
        "(persona_id, version, content, status, created_by, locale) "
        "VALUES ($1, 1, $2::jsonb, 'active', $3, 'de')",
        persona_id,
        _builder_persona_content(),
        owner_id,
    )

    # 2. 4 Playbooks + v1 (active); ids fuer die Verlinkung einsammeln.
    playbook_ids: list[UUID] = []
    for name, ptype, triggers, tags, description, sidecar in _BUILDER_PLAYBOOKS:
        playbook_id = await conn.fetchval(
            "INSERT INTO playbook "
            "(workspace_id, owner_id, name, type, tags, triggers, "
            " is_managed, managed_content_version) "
            "SELECT $1, $2, $3, $4, $5, $6, true, $7 "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM playbook WHERE workspace_id = $1 AND name = $3"
            ") "
            "RETURNING id",
            workspace_id,
            owner_id,
            name,
            ptype,
            list(tags),
            triggers,
            BUILDER_CONTENT_VERSION,
        )
        if playbook_id is None:
            # Gleichnamiges Playbook gab es schon (Re-Lauf/Race) — id nachladen,
            # damit der Link trotzdem gesetzt wird.
            playbook_id = await conn.fetchval(
                "SELECT id FROM playbook WHERE workspace_id = $1 AND name = $2 "
                "ORDER BY created_at ASC LIMIT 1",
                workspace_id,
                name,
            )
        else:
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, 1, $2::jsonb, 'active', $3, 'de')",
                playbook_id,
                _builder_playbook_content(sidecar, ptype, tags, triggers, description),
                owner_id,
            )
        if playbook_id is not None:
            playbook_ids.append(playbook_id)

    # 3. Persona <-> Playbook-Links (additiv-idempotent).
    if playbook_ids:
        await conn.execute(
            "INSERT INTO persona_playbook "
            "(persona_id, playbook_id, workspace_id, owner_id) "
            "SELECT $1, unnest($2::uuid[]), $3, $4 "
            "ON CONFLICT (persona_id, playbook_id) DO NOTHING",
            persona_id,
            playbook_ids,
            workspace_id,
            owner_id,
        )

    # 4. agent-Row. Template 'agent-builder' kommt aus _seed_default_templates.
    template_id = await conn.fetchval(
        "SELECT id FROM system_prompt_template WHERE workspace_id = $1 AND slug = $2",
        workspace_id,
        _AGENT_BUILDER_TEMPLATE_SLUG,
    )
    if template_id is None:
        return
    await conn.execute(
        "INSERT INTO agent (workspace_id, owner_id, name, description, "
        " persona_id, system_prompt_template_id, status, tool_policy, "
        " is_managed, managed_content_version) "
        "SELECT $1, $2, $3, $4, $5, $6, 'enabled', $7::jsonb, true, $8 "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM agent WHERE workspace_id = $1 AND name = $3"
        ")",
        workspace_id,
        owner_id,
        _BUILDER_AGENT_NAME,
        _BUILDER_AGENT_DESCRIPTION,
        persona_id,
        template_id,
        _builder_tool_policy(),
        BUILDER_CONTENT_VERSION,
    )

    # 5. Builder-Lite-agent — selbe Persona + Schreib-Policy, aber das schlanke
    #    'agent-builder-lite'-Template (kleinerer Render fuer LLMs mit kleinem
    #    System-Prompt-Budget). Reused die Builder-Persona aus Schritt 1.
    lite_template_id = await conn.fetchval(
        "SELECT id FROM system_prompt_template WHERE workspace_id = $1 AND slug = $2",
        workspace_id,
        _AGENT_BUILDER_LITE_TEMPLATE_SLUG,
    )
    if lite_template_id is None:
        return
    await conn.execute(
        "INSERT INTO agent (workspace_id, owner_id, name, description, "
        " persona_id, system_prompt_template_id, status, tool_policy, "
        " is_managed, managed_content_version) "
        "SELECT $1, $2, $3, $4, $5, $6, 'enabled', $7::jsonb, true, $8 "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM agent WHERE workspace_id = $1 AND name = $3"
        ")",
        workspace_id,
        owner_id,
        _BUILDER_LITE_AGENT_NAME,
        _BUILDER_LITE_AGENT_DESCRIPTION,
        persona_id,
        lite_template_id,
        _builder_tool_policy(),
        BUILDER_CONTENT_VERSION,
    )


async def sync_managed_builder_content(conn: asyncpg.Connection) -> int:
    """Hebt verwaltete Builder-Aggregate mit veraltetem Stempel auf den kanonischen
    Stand (`BUILDER_CONTENT_VERSION`).

    Zentrale Verteilung: bei jeder Aenderung an den Sidecars
    (Persona/Template/Playbooks) wird `BUILDER_CONTENT_VERSION` hochgezaehlt; dieser
    Sync ersetzt dann beim App-Start in JEDEM Workspace den aktiven Versions-Inhalt
    der managed Builder-Aggregate durch den kanonischen — sicher, weil managed =
    gesperrt (keine User-Edits zu erhalten). In-place-Replace (keine Versions-
    Proliferation); idempotent ueber den `managed_content_version`-Stempel.

    Erwartet eine privilegierte Verbindung (Owner/Migrations-URL) — der RLS-
    gescopte App-Pool saehe ohne Tenant keine Zeilen. JSONB wird als String
    gebunden (`$n::jsonb`), damit kein Pool-Codec noetig ist. Gibt die Anzahl
    aktualisierter Aggregate zurueck.
    """
    updated = 0

    persona_json = json.dumps(_builder_persona_content())
    for row in await conn.fetch(
        "SELECT id FROM persona WHERE name = $1 AND is_managed = true "
        "AND managed_content_version < $2",
        _BUILDER_PERSONA_NAME,
        BUILDER_CONTENT_VERSION,
    ):
        await conn.execute(
            "UPDATE persona_version SET content = $2::jsonb "
            "WHERE persona_id = $1 AND status = 'active'",
            row["id"],
            persona_json,
        )
        await conn.execute(
            "UPDATE persona SET managed_content_version = $2, updated_at = now() WHERE id = $1",
            row["id"],
            BUILDER_CONTENT_VERSION,
        )
        updated += 1

    template_json = json.dumps({"description": "", "body": _sidecar("agent_builder_body.json")})
    for row in await conn.fetch(
        "SELECT id FROM system_prompt_template WHERE slug = $1 AND is_managed = true "
        "AND managed_content_version < $2",
        _AGENT_BUILDER_TEMPLATE_SLUG,
        BUILDER_CONTENT_VERSION,
    ):
        await conn.execute(
            "UPDATE system_prompt_template_version SET content = $2::jsonb "
            "WHERE template_id = $1 AND status = 'active'",
            row["id"],
            template_json,
        )
        await conn.execute(
            "UPDATE system_prompt_template SET managed_content_version = $2, updated_at = now() "
            "WHERE id = $1",
            row["id"],
            BUILDER_CONTENT_VERSION,
        )
        updated += 1

    lite_template_json = json.dumps(
        {"description": "", "body": _sidecar("agent_builder_lite_body.json")}
    )
    for row in await conn.fetch(
        "SELECT id FROM system_prompt_template WHERE slug = $1 AND is_managed = true "
        "AND managed_content_version < $2",
        _AGENT_BUILDER_LITE_TEMPLATE_SLUG,
        BUILDER_CONTENT_VERSION,
    ):
        await conn.execute(
            "UPDATE system_prompt_template_version SET content = $2::jsonb "
            "WHERE template_id = $1 AND status = 'active'",
            row["id"],
            lite_template_json,
        )
        await conn.execute(
            "UPDATE system_prompt_template SET managed_content_version = $2, updated_at = now() "
            "WHERE id = $1",
            row["id"],
            BUILDER_CONTENT_VERSION,
        )
        updated += 1

    for name, ptype, triggers, tags, description, sidecar in _BUILDER_PLAYBOOKS:
        pb_json = json.dumps(_builder_playbook_content(sidecar, ptype, tags, triggers, description))
        for row in await conn.fetch(
            "SELECT id FROM playbook WHERE name = $1 AND is_managed = true "
            "AND managed_content_version < $2",
            name,
            BUILDER_CONTENT_VERSION,
        ):
            await conn.execute(
                "UPDATE playbook_version SET content = $2::jsonb "
                "WHERE playbook_id = $1 AND status = 'active'",
                row["id"],
                pb_json,
            )
            await conn.execute(
                "UPDATE playbook SET managed_content_version = $2, updated_at = now() "
                "WHERE id = $1",
                row["id"],
                BUILDER_CONTENT_VERSION,
            )
            updated += 1

    return updated
