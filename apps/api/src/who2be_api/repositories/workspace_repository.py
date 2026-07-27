"""Persistenz fuer das Workspace-Aggregat (TASK-301).

Liest und schreibt `workspace`. Die Membership-Pruefung ist Aufgabe der
`WorkspaceMemberRepository`; dieses Repo arbeitet auf der Workspace-Ebene
und bekommt die User-Identitaet vom Service-Layer durchgereicht.
"""

import json
import logging
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.core.chunk_backfill import backfill_chunks
from who2be_api.core.errors import ApiGateError
from who2be_api.repositories.builder_content import (
    SUPPORTED_LOCALES,
    ContentPack,
    PlaybookDef,
    get_content_pack,
)
from who2be_models import (
    DEFAULT_LOCALE,
    AgentToolPolicy,
    MemoryDirective,
    MemoryMode,
    ReadScope,
    WorkspaceRead,
)

logger = logging.getLogger(__name__)


async def _publish_seeded_chunks(conn: asyncpg.Connection, workspace_id: UUID) -> None:
    """Schreibt die Passagen (`content_chunk`) der frisch geseedeten Inhalte.

    Der Seed legt Persona, Playbooks, Resource und Templates per direktem
    Insert als `active` an — er laeuft also an
    `version_status._transition` vorbei, dem einzigen Ort, an dem sonst
    Passagen entstehen (ADR-0046). Ohne diesen Aufruf haette ein frisch
    angelegter Workspace null Passagen und `search_content` faende dort
    nichts — ausgerechnet im Builder-Bestand, der die Suche selbst empfiehlt.

    Best-effort in einem eigenen Savepoint: die Passagen sind abgeleitete
    Daten, ein Fehler beim Ableiten darf die Workspace-Anlage nicht kippen
    (und der Savepoint haelt die umgebende Transaktion nutzbar). Reparatur
    laeuft ueber `who2be-retrieval-backfill`.
    """
    try:
        async with conn.transaction():
            _, chunks, _ = await backfill_chunks(conn, workspace_id)
    except Exception:  # noqa: BLE001 - Workspace-Anlage darf daran nie scheitern
        logger.warning(
            "Passagen des neuen Workspaces %s nicht geschrieben — "
            "`who2be-retrieval-backfill` holt sie nach.",
            workspace_id,
            exc_info=True,
        )
        return
    logger.debug("Workspace %s geseedet: %d Passagen geschrieben.", workspace_id, chunks)


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
    content_locale: str = DEFAULT_LOCALE,
) -> UUID:
    """Lazy-Seed einer Personal-Org + Workspace + Admin-Membership.

    Idempotent: laeuft ein zweites Mal durch, ohne Duplikate anzulegen.
    Naming-Strategie fuer die Org:
      1. Local-Part der ``user_email``, falls gesetzt und valide.
      2. Fallback: ``"Personal"``.

    ``content_locale`` (ADR-0045) bestimmt die Content-Sprache des Workspaces
    und damit die Sprache der geseedeten Standard-Inhalte; abgeleitet wird sie
    vom Aufrufer (me-Flow: ``preferred_locale`` aus ``auth.users``). Bei einem
    Re-Lauf bleibt die bestehende Workspace-Sprache erhalten (kein Update im
    ON-CONFLICT-Zweig) — die Seeds prallen dann ohnehin an ihren Guards ab.

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
        "INSERT INTO workspace (org_id, name, slug, content_locale) "
        "VALUES ($1, 'Personal', 'personal', $2) "
        "ON CONFLICT (org_id, slug) DO UPDATE SET name = excluded.name "
        "RETURNING id",
        org_id,
        content_locale,
    )
    await conn.execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) "
        "VALUES ($1, $2, 'admin') ON CONFLICT (workspace_id, user_id) DO NOTHING",
        workspace_id,
        user_id,
    )
    await _seed_default_templates(conn, workspace_id, user_id, content_locale)
    await _seed_default_agents(conn, workspace_id, user_id, content_locale)
    await _publish_seeded_chunks(conn, workspace_id)
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

    async def create(
        self, org_id: UUID, user_id: UUID, name: str, slug: str, content_locale: str
    ) -> WorkspaceRead: ...

    async def update_name(self, workspace_id: UUID, name: str) -> WorkspaceRead | None: ...

    async def delete(self, workspace_id: UUID) -> bool: ...


class PgWorkspaceRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_org_for_user(self, org_id: UUID, user_id: UUID) -> list[WorkspaceRead]:
        rows = await self._pool.fetch(
            "SELECT w.id, w.org_id, w.name, w.slug, w.content_locale, w.created_at "
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
            "SELECT id, org_id, name, slug, content_locale, created_at "
            "FROM workspace WHERE id = $1",
            workspace_id,
        )
        return WorkspaceRead.model_validate(dict(row)) if row is not None else None

    async def create(
        self, org_id: UUID, user_id: UUID, name: str, slug: str, content_locale: str
    ) -> WorkspaceRead:
        """Neuer Workspace + Admin-Membership fuer den Anlegenden, atomar.

        Seedet zudem die Default-SystemPromptTemplates (Phase 3 Runde 3
        Track 3 — analog Migration 0023b fuer Bestandsworkspaces). Idempotent
        ueber `ON CONFLICT (workspace_id, slug) DO NOTHING`; bei Migration-
        plus-Create-Race greift derselbe Schutz. `content_locale` (ADR-0045)
        bestimmt die Sprache der geseedeten Standard-Inhalte und den Default
        fuer neue Elemente (`resolve_content_locale`).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO workspace (org_id, name, slug, content_locale) "
                "VALUES ($1, $2, $3, $4) "
                "RETURNING id, org_id, name, slug, content_locale, created_at",
                org_id,
                name,
                slug,
                content_locale,
            )
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'admin')",
                row["id"],
                user_id,
            )
            await _seed_default_templates(conn, row["id"], user_id, content_locale)
            await _seed_default_agents(conn, row["id"], user_id, content_locale)
            await _publish_seeded_chunks(conn, row["id"])
        return WorkspaceRead.model_validate(dict(row))

    async def update_name(self, workspace_id: UUID, name: str) -> WorkspaceRead | None:
        row = await self._pool.fetchrow(
            "UPDATE workspace SET name = $1 WHERE id = $2 "
            "RETURNING id, org_id, name, slug, content_locale, created_at",
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


# Alle Seed-/Sync-Inhalte (Default-Templates, Builder-Persona/-Playbooks/
# -Resource/-Agent-Beschreibungen) kommen seit WP8 (ADR-0045) aus den
# Sprach-Content-Packs in `builder_content.py` — EIN Pack pro Sprache, SSoT.
# Die BlockNote-Bodies liegen als Sidecar-JSON (DE flach neben dem Modul,
# andere Sprachen unter `<locale>/` mit identischem Dateinamen) und werden
# ueber `TemplateDef.load_body(locale)` etc. aufgeloest.


async def _seed_default_templates(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID, content_locale: str
) -> None:
    """Legt die Default-Templates eines neuen Workspaces an.

    Inhalte kommen aus dem ContentPack der Workspace-Sprache (`content_locale`,
    ADR-0045); Entity- UND Versions-Row tragen die Sprache explizit — bei
    EN-Workspaces sind die geseedeten Templates echte EN-Elemente.
    Idempotent ueber ``ON CONFLICT (workspace_id, slug) DO NOTHING`` auf
    `system_prompt_template`. Versions-Insert per ``NOT EXISTS`` — wenn ein
    Template existiert (z. B. nach Re-Lauf), wird kein v1 mehr angelegt.
    Initial-Status ist `active`, sodass der Render-Endpoint sofort ohne
    Promote-Schritt feuert.
    """
    pack = get_content_pack(content_locale)
    for template in pack.templates:
        # Die agent-builder-Templates (voll + lite) sind managed (gesperrt +
        # zentral gepflegt); die uebrigen Default-Templates bleiben frei editierbar.
        managed = template.slug in _MANAGED_TEMPLATE_SLUGS
        template_id = await conn.fetchval(
            "INSERT INTO system_prompt_template "
            "(workspace_id, owner_id, name, slug, is_managed, managed_content_version, locale) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (workspace_id, slug) DO NOTHING "
            "RETURNING id",
            workspace_id,
            owner_id,
            template.name,
            template.slug,
            managed,
            BUILDER_CONTENT_VERSION if managed else 0,
            content_locale,
        )
        if template_id is None:
            # Template gab es schon — der Versions-Insert unten wuerde
            # ebenfalls per NOT EXISTS abprallen, aber wir sparen den
            # Roundtrip.
            continue
        await conn.execute(
            "INSERT INTO system_prompt_template_version "
            "(template_id, version, content, status, created_by, locale) "
            "SELECT $1, 1, $2::jsonb, 'active', $3, $4 "
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
            {"description": "", "body": template.load_body(content_locale)},
            owner_id,
            content_locale,
        )


# ---------------------------------------------------------------------------
# Default-Agent „Builder" (Meta-Agent — der Agent, der Agenten baut).
#
# Wird nach den Default-Templates in jedem neuen Workspace mitgeseedet.
# Migration 0047 war der einmalige Backfill des damaligen Stands (Persona +
# 4 Playbooks + Agent) fuer Bestands-Workspaces; seither verteilt der
# Start-Sync (`sync_managed_builder_content`) jede zentrale Aenderung —
# inkl. spaeter ergaenzter Playbooks — ohne weitere Spiegel-Migration.
# Inhaltlich re-targeted auf die Who2Be-MCP-Write-Tools (kein externer Store).
#
# Reihenfolge wegen der Composite-FKs (agent -> persona, agent -> template):
#   1. Persona „Builder"      (persona + persona_version v1 active)
#   2. Playbooks              (alle `_BUILDER_PLAYBOOKS`, je v1 active)
#   3. persona_playbook-Links (Persona <-> alle Builder-Playbooks)
#   4. Resource „Agent-Bau-Konventionen" (resource + resource_version v1
#      active) + playbook_resource_link von ALLEN Builder-Playbooks darauf
#      (link_scope 'resource' — Single-Source der Bau-Konventionen)
#   5. agent-Row              (persona_id + Template 'agent-builder' +
#                              write-faehige tool_policy, status 'enabled')
# Das Template 'agent-builder' selbst legt bereits `_seed_default_templates`
# an (Eintrag in `_DEFAULT_TEMPLATES`); hier wird nur seine id nachgeschlagen.
#
# Idempotenz: jede Identitaets-Zeile wird per NOT EXISTS (workspace_id + name
# bzw. slug) angelegt, die Links via ON CONFLICT DO NOTHING. JSONB-Bind: dict
# uebergeben, KEINEN vor-serialisierten String (Codec-Falle, siehe oben).
#
# Namen/Trigger/Tags/Beschreibungen leben pro Sprache im ContentPack
# (`builder_content.py`); hier verbleiben nur die locale-unabhaengigen
# technischen Schluessel (Template-Slugs) und die Tool-Policy.
_AGENT_BUILDER_TEMPLATE_SLUG = "agent-builder"
_AGENT_BUILDER_LITE_TEMPLATE_SLUG = "agent-builder-lite"
_MANAGED_TEMPLATE_SLUGS = (_AGENT_BUILDER_TEMPLATE_SLUG, _AGENT_BUILDER_LITE_TEMPLATE_SLUG)

# Kanonischer Content-Stand des verwalteten Builders. Wird bei jeder zentralen
# Aenderung an Persona/Template/Playbooks/Resource (Sidecars) hochgezaehlt; der
# Start-Sync hebt managed-Aggregate, deren `managed_content_version` zurueckliegt,
# auf diesen Stand. Seed stempelt neue Builder direkt hierauf.
# v5: Persona-Modi (Architekt/Kurator/Berater) + Managed-Resource
# „Agent-Bau-Konventionen" inkl. Links aus allen Builder-Playbooks.
# v6: resolve_feedback im Pflege-Lauf (Sidecars referenzieren das Triage-Tool)
# + `feedback_resolve` in der Builder-Policy (Agent-Rows werden im Sync
# erstmals mit nachgezogen).
# v7: Konventionen-Prosa in allen 5 Builder-Playbooks + der Resource auf den
# realen lazy-Pointer korrigiert ('mitgeliefert (link_scope resource)' war
# falsch — der Link ist embedding_mode 'lazy', explizites fetch_resource-
# Nachladen noetig; Feedback-Signale Pflege-Lauf 10./11.07.2026) +
# Konsistenz-Check-Angebot im Hand-Off des Agent-Playbooks (Persona-Abgleich).
# v8: Agent-Memory-Wissen (ADR-0044) im Agent-Playbook (tool_policy-Sektion:
# memory_mode/memory_directive, Empfehlungslogik, is_within-Grenze mit
# Human-Hand-Off) + eigene Gedaechtnis-Sektion in den Agent-Bau-Konventionen.
# v9: expliziter `memory`-Placeholder im Agent-Builder-Template (nach der
# tools-overview-Pill) — positionierter Gedaechtnis-Hinweis statt Auto-Append.
# v10: Builder-Gedaechtnis aktiviert — `memory_mode='suggest'` +
# `memory_directive='recommended'` in der Builder-Policy (Kurations-Stufe,
# ADR-0044; der Policy-Sync verteilt das an alle Bestands-Builder).
# v11: External Tools (ADR-0043) fuer den Builder — `external_tool_write=True`
# in der Policy (damit via `is_within` auch an Fach-Agenten vergebbar), neues
# Playbook „External Tool anlegen & pflegen" + External-Tools-Sektion in den
# Agent-Bau-Konventionen.
# v12: Content-Packs als SSoT (ADR-0045, WP7/WP8) — Seed + Sync beziehen alle
# Inhalte aus `builder_content.get_content_pack(locale)`; die DE-Prosa des
# Persona-Playbooks wurde in WP7 sprachbewusst umformuliert (create_persona-
# Beispiele). WICHTIG: Der Stempel ist sprachuebergreifend — Bump bei jeder
# Content-Aenderung in IRGENDEINER Sprache (DE ODER EN), sonst verteilt der
# Sync die geaenderte Sprache nie.
# v13: Sprach-Wissen des Builders nachgezogen (ADR-0045-Nachzug, Issue #360
# WP-A bis WP-D) — Sprach-Abschnitt in den Agent-Bau-Konventionen, Sprache im
# Create-/Vorschlags-Schritt der Anlege-Playbooks (Playbook/Agent/External
# Tool), Sprach-Konsistenz als Pruefpunkt im Drift-Check, Sprach-Aspekt in
# der Builder-Persona-Erlaubt-Liste — DE + EN.
# v14: Retrieval-Wissen des Builders nachgezogen (ADR-0046) — neuer Abschnitt
# „Auffindbarkeit & Retrieval" in den Agent-Bau-Konventionen (Ueberschriften
# als Schnittkanten der Passagen-Suche, nur aktive Versionen sind auffindbar,
# Passage vor Volltext, `mode`-Wahl, Sprachgrenze, Retrieval ersetzt keine
# Trigger) plus semantisches Gedaechtnis in der Memory-Sektion; `search_content`
# im Beziehungs-Denken der Persona, in der Wiederverwendungs-Regel und in den
# Tool-Listen von Playbook- und Pflege-Playbook — DE + EN.
BUILDER_CONTENT_VERSION = 14


def _builder_persona_content(pack: ContentPack) -> dict[str, object]:
    """Persona-Versions-Content (PersonaVersionContent-Form) als dict fuer JSONB.

    Der BlockNote-Profil-Body kommt aus dem Sidecar der Pack-Sprache (Array von
    Blocks) und wird unter `content.blocks` gehaengt. `modes` traegt die drei
    Persona-Modi aus dem Modes-Sidecar (Multi-Mode: Architekt als Default,
    Kurator, Berater). Der Kurator bindet das Pflege-Playbook bewusst in Prosa
    statt via `playbook_id` — Playbook-UUIDs sind workspace-spezifisch, der
    kanonische Content muss workspace-uebergreifend identisch bleiben.
    """
    persona = pack.persona
    blocks = json.loads(persona.load_content(pack.locale))
    modes = json.loads(persona.load_modes(pack.locale))
    return {
        "description": persona.description,
        "traits": list(persona.traits),
        "tags": list(persona.tags),
        "content": {"description": "", "blocks": blocks},
        "modes": modes,
        "skills": [],
    }


def _builder_resource_content(pack: ContentPack) -> dict[str, object]:
    """Resource-Versions-Content (ResourceContent-Form) als dict fuer JSONB.

    `blocks` ist das BlockNote-Array aus dem Sidecar der Pack-Sprache (im
    Gegensatz zum Playbook-`body` NICHT stringifiziert —
    `ResourceContent.blocks` ist eine echte Block-Liste); `tags` leben hier im
    Content, nicht auf der Row.
    """
    resource = pack.resource
    blocks = json.loads(resource.load_body(pack.locale))
    return {
        "description": resource.description,
        "blocks": blocks,
        "tags": list(resource.tags),
    }


def _builder_playbook_content(playbook: PlaybookDef, locale: str) -> dict[str, object]:
    """Playbook-Versions-Content (PlaybookContent-Form) als dict fuer JSONB.

    `body` ist das stringifizierte BlockNote-Dokument (`json.dumps` des Sidecar-
    Arrays der Pack-Sprache) — analog zum Frontend-`JSON.stringify(editor.document)`.
    """
    body = json.dumps(json.loads(playbook.load_body(locale)), ensure_ascii=False)
    return {
        "description": playbook.description,
        "body": body,
        "type": playbook.type,
        "tags": list(playbook.tags),
        "triggers": playbook.triggers,
    }


def _builder_tool_policy() -> dict[str, object]:
    """Write-faehige Policy fuer den Meta-Agenten (Plan §5.2).

    Alle Schreib-Capabilities + `promote_retire` + `system_prompt_write`
    (ADR-0040: Templates verfassen + zur Review einreichen; das Aktivieren bleibt
    serverseitig auch fuer den Builder gesperrt), Reads = `all`. Die Reads sind
    bewusst EXPLIZIT auf `all` gesetzt: der Meta-Agent verwaltet den ganzen
    Workspace und darf nicht den (seit „secure by default") auf `assigned`
    abgesenkten Read-Default erben. `feedback_resolve` (Content-Stand 6):
    das Schliessen von Feedback-Signalen ist die Kurations-Handlung des
    Meta-Agenten im Pflege-Lauf — Fach-Agenten behalten den secure-by-default
    False und melden nur (`feedback_write`). Die Autorisierung bleibt
    serverseitig (editor; Promote/Retire admin) — die Policy steuert nur die
    Tool-Sichtbarkeit im System-Prompt.

    `memory_mode='suggest'` (Content-Stand 10, ADR-0044): der Builder bekommt
    das Gedaechtnis in der Kurations-Stufe — Vorschlaege landen als `pending`
    und werden vom Menschen freigegeben (konsistent zum eigenen
    Kurator-Prinzip; bewusst NICHT `auto`). Nebeneffekt via `is_within`: der
    Builder darf damit anderen Agenten das Gedaechtnis bis maximal `suggest`
    freischalten — `auto` bleibt eine Menschen-Entscheidung.

    `external_tool_write=True` (Content-Stand 11, ADR-0043): External-Tool-
    Bindungen anlegen/pflegen ist Verwaltungs-Arbeit des Meta-Agenten; via
    `is_within` kann er das Recht damit auch gezielt an Fach-Agenten vergeben.
    Memory-Kuration (Triage/Guard) bleibt bewusst ausserhalb — UI-only.
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
        feedback_resolve=True,
        promote_retire=True,
        external_tool_write=True,
        memory_mode=MemoryMode.suggest,
        memory_directive=MemoryDirective.recommended,
    ).model_dump(mode="json")


async def _seed_default_agents(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID, content_locale: str
) -> None:
    """Legt den Default-Agenten „Builder" eines neuen Workspaces an.

    Alle Inhalte kommen aus dem ContentPack der Workspace-Sprache
    (`content_locale`, ADR-0045); Entity- UND Versions-Rows tragen die Sprache
    explizit — bei EN-Workspaces sind Persona/Playbooks/Resource echte
    EN-Elemente. Laeuft NACH `_seed_default_templates` (braucht das
    'agent-builder'-Template). Idempotent ueber NOT-EXISTS-Guards
    (workspace_id + name/slug) und ON-CONFLICT-DO-NOTHING auf den Links.
    Migration 0047 war der einmalige Backfill des damaligen Stands; neuere
    Inhalte verteilt der Start-Sync.
    """
    pack = get_content_pack(content_locale)

    # 1. Persona „Builder" + v1 (active). Der NOT-EXISTS-Guard liefert None,
    #    wenn der Builder-Seed bereits lief — der Lauf ist atomar, also sind
    #    in dem Fall auch Playbooks/Resource/Agent schon da: frueh raus.
    persona_id = await conn.fetchval(
        "INSERT INTO persona "
        "(workspace_id, owner_id, name, is_managed, managed_content_version, locale) "
        "SELECT $1, $2, $3, true, $4, $5 "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM persona WHERE workspace_id = $1 AND name = $3"
        ") "
        "RETURNING id",
        workspace_id,
        owner_id,
        pack.persona.name,
        BUILDER_CONTENT_VERSION,
        content_locale,
    )
    if persona_id is None:
        return
    await conn.execute(
        "INSERT INTO persona_version "
        "(persona_id, version, content, status, created_by, locale) "
        "VALUES ($1, 1, $2::jsonb, 'active', $3, $4)",
        persona_id,
        _builder_persona_content(pack),
        owner_id,
        content_locale,
    )

    # 2. Alle Builder-Playbooks + v1 (active); ids fuer die Verlinkung einsammeln.
    playbook_ids: list[UUID] = []
    for playbook in pack.playbooks:
        playbook_id = await conn.fetchval(
            "INSERT INTO playbook "
            "(workspace_id, owner_id, name, type, tags, triggers, "
            " is_managed, managed_content_version, locale) "
            "SELECT $1, $2, $3, $4, $5, $6, true, $7, $8 "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM playbook WHERE workspace_id = $1 AND name = $3"
            ") "
            "RETURNING id",
            workspace_id,
            owner_id,
            playbook.name,
            playbook.type,
            list(playbook.tags),
            playbook.triggers,
            BUILDER_CONTENT_VERSION,
            content_locale,
        )
        if playbook_id is None:
            # Gleichnamiges Playbook gab es schon (Re-Lauf/Race) — id nachladen,
            # damit der Link trotzdem gesetzt wird.
            playbook_id = await conn.fetchval(
                "SELECT id FROM playbook WHERE workspace_id = $1 AND name = $2 "
                "ORDER BY created_at ASC LIMIT 1",
                workspace_id,
                playbook.name,
            )
        else:
            await conn.execute(
                "INSERT INTO playbook_version "
                "(playbook_id, version, content, status, created_by, locale) "
                "VALUES ($1, 1, $2::jsonb, 'active', $3, $4)",
                playbook_id,
                _builder_playbook_content(playbook, content_locale),
                owner_id,
                content_locale,
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

    # 4. Managed-Resource „Agent-Bau-Konventionen" + v1 (active) + Links von
    #    ALLEN Builder-Playbooks (link_scope='resource', embedding_mode Default
    #    'lazy' — Pointer; die Playbook-Prosa weist das fetch_resource-Nachladen an).
    #    Der Guard laeuft wie ueberall ueber workspace_id + name; die Links
    #    prallen per ON CONFLICT DO NOTHING an den partiellen Unique-Indexen
    #    aus Migration 0021 ab.
    resource_id = await conn.fetchval(
        "INSERT INTO resource "
        "(workspace_id, owner_id, name, slug, is_managed, managed_content_version, locale) "
        "SELECT $1, $2, $3, $5, true, $4, $6 "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM resource WHERE workspace_id = $1 AND name = $3"
        ") "
        "RETURNING id",
        workspace_id,
        owner_id,
        pack.resource.name,
        BUILDER_CONTENT_VERSION,
        pack.resource.slug,
        content_locale,
    )
    if resource_id is not None:
        await conn.execute(
            "INSERT INTO resource_version "
            "(resource_id, version, content, status, created_by, locale) "
            "VALUES ($1, 1, $2::jsonb, 'active', $3, $4)",
            resource_id,
            _builder_resource_content(pack),
            owner_id,
            content_locale,
        )
        if playbook_ids:
            await conn.execute(
                "INSERT INTO playbook_resource_link "
                "(playbook_id, resource_id, block_id, workspace_id, owner_id, "
                " position, link_scope) "
                "SELECT unnest($1::uuid[]), $2, NULL, $3, $4, 0, 'resource' "
                "ON CONFLICT DO NOTHING",
                playbook_ids,
                resource_id,
                workspace_id,
                owner_id,
            )

    # 5. agent-Row. Template 'agent-builder' kommt aus _seed_default_templates.
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
        pack.agent.name,
        pack.agent.description,
        persona_id,
        template_id,
        _builder_tool_policy(),
        BUILDER_CONTENT_VERSION,
    )

    # 6. Builder-Lite-agent — selbe Persona + Schreib-Policy, aber das schlanke
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
        pack.agent_lite.name,
        pack.agent_lite.description,
        persona_id,
        lite_template_id,
        _builder_tool_policy(),
        BUILDER_CONTENT_VERSION,
    )


async def sync_managed_builder_content(conn: asyncpg.Connection) -> int:
    """Hebt verwaltete Builder-Aggregate mit veraltetem Stempel auf den kanonischen
    Stand (`BUILDER_CONTENT_VERSION`).

    Zentrale Verteilung: bei jeder Aenderung an den Sidecars
    (Persona/Template/Playbooks/Resource — in IRGENDEINER Sprache) wird
    `BUILDER_CONTENT_VERSION` hochgezaehlt; dieser
    Sync ersetzt dann beim App-Start in JEDEM Workspace den aktiven Versions-Inhalt
    der managed Builder-Aggregate durch den kanonischen — sicher, weil managed =
    gesperrt (keine User-Edits zu erhalten). In-place-Replace (keine Versions-
    Proliferation); idempotent ueber den `managed_content_version`-Stempel.

    Locale-bewusst (ADR-0045, WP8): der Sync laeuft pro Sprache aus
    `SUPPORTED_LOCALES` mit dem jeweiligen ContentPack; JEDE Kandidaten-Query
    ist ueber `JOIN workspace w ... AND w.content_locale = $n` auf Workspaces
    dieser Sprache gescopet — pro Workspace gilt genau EIN Pack, EN-Inhalte
    landen nie in DE-Workspaces und umgekehrt. Das Name-Matching bleibt damit
    tragfaehig: die Pack-Namen sind pro Sprache eindeutig, und ein Workspace
    enthaelt nur die Namen seines Packs. Insert-missing-Zweige schreiben
    `locale` explizit auf Entity- UND Versions-Row.

    Playbooks werden dabei auf BEIDEN Ebenen nachgezogen: der aktive Versions-
    Inhalt UND die Metadaten der Playbook-Row (`type`/`tags`/`triggers`) —
    Letztere speisen Listen/`list_triggers` und wuerden sonst nie verteilen
    (Metadaten-Drift, sichtbar geworden bei der Trigger-Kollision des
    Konsistenz-Checks). Zusaetzlich legt der Sync im Pack neu hinzugekommene
    Playbooks in Bestands-Workspaces mit managed Builder-Persona
    an (Insert-missing, analog `_seed_default_agents`: Row + v1 active +
    persona_playbook-Link) — der Seed laeuft dort nie wieder. Dasselbe Muster
    gilt fuer die Managed-Resource „Agent-Bau-Konventionen" (Content-Stand 5):
    Content-Update + Stempel bei Rueckstand (die Tags leben im Versions-Content
    und verteilen darueber mit — die resource-Row hat keine Tag-Spalte) sowie
    Insert-missing der Resource + v1 active + der `playbook_resource_link`s
    aller Builder-Playbooks (link_scope 'resource') in Bestands-Workspaces.
    Seit Content-Stand 6 gehoeren auch die AGENT-Rows dazu: die `tool_policy`
    (und seit WP8 die Pack-Beschreibung) der Builder-Agenten
    (Builder/Builder-Lite) ist Teil des kanonischen
    Builder-Stands und wird bei Stempel-Rueckstand auf `_builder_tool_policy()`
    ersetzt — sicher, weil managed = gesperrt (keine User-Edits an der Policy
    zu erhalten); ohne diesen Zweig bekaemen Bestands-Builder neue
    Capabilities (z. B. `feedback_resolve`) nie.
    Damit braucht eine Content-/Playbook-/Resource-Erweiterung KEINE
    Spiegel-Migration mehr (Konvention seit 0057/Start-Sync; v1→v2 und v2→v3
    liefen ebenso rein ueber den Sync): Sidecar/ContentPack anpassen +
    Version hochzaehlen.

    Erwartet eine privilegierte Verbindung (Owner/Migrations-URL) — der RLS-
    gescopte App-Pool saehe ohne Tenant keine Zeilen. JSONB wird als String
    gebunden (`$n::jsonb`), damit kein Pool-Codec noetig ist. Gibt die Anzahl
    aktualisierter + neu angelegter Aggregate zurueck.
    """
    updated = 0
    # Die Tool-Policy ist locale-unabhaengig (reine Capability-Flags) — einmal
    # serialisieren, in jedem Sprach-Durchlauf verwenden.
    agent_policy_json = json.dumps(_builder_tool_policy())

    for locale in SUPPORTED_LOCALES:
        pack = get_content_pack(locale)

        # (1) Persona-Content-Update bei Stempel-Rueckstand.
        persona_json = json.dumps(_builder_persona_content(pack))
        for row in await conn.fetch(
            "SELECT p.id FROM persona p "
            "JOIN workspace w ON w.id = p.workspace_id "
            "WHERE p.name = $1 AND p.is_managed = true "
            "AND p.managed_content_version < $2 AND w.content_locale = $3",
            pack.persona.name,
            BUILDER_CONTENT_VERSION,
            locale,
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

        # (2)+(3) Managed-Templates (agent-builder + agent-builder-lite):
        # Content-Update bei Stempel-Rueckstand, Body aus dem Pack der
        # Workspace-Sprache.
        for template in pack.templates:
            if template.slug not in _MANAGED_TEMPLATE_SLUGS:
                continue
            template_json = json.dumps({"description": "", "body": template.load_body(locale)})
            for row in await conn.fetch(
                "SELECT t.id FROM system_prompt_template t "
                "JOIN workspace w ON w.id = t.workspace_id "
                "WHERE t.slug = $1 AND t.is_managed = true "
                "AND t.managed_content_version < $2 AND w.content_locale = $3",
                template.slug,
                BUILDER_CONTENT_VERSION,
                locale,
            ):
                await conn.execute(
                    "UPDATE system_prompt_template_version SET content = $2::jsonb "
                    "WHERE template_id = $1 AND status = 'active'",
                    row["id"],
                    template_json,
                )
                await conn.execute(
                    "UPDATE system_prompt_template "
                    "SET managed_content_version = $2, updated_at = now() "
                    "WHERE id = $1",
                    row["id"],
                    BUILDER_CONTENT_VERSION,
                )
                updated += 1

        for playbook in pack.playbooks:
            pb_json = json.dumps(_builder_playbook_content(playbook, locale))

            # (4) Insert-missing: neue managed Playbooks erreichen Bestands-
            # Workspaces nur hier (der Seed laeuft dort nie wieder). Match wie
            # im Seed ueber workspace_id + Pack-Name (gescopet auf Workspaces
            # der Pack-Sprache); created_by/owner = Owner der Builder-Persona.
            for prow in await conn.fetch(
                "SELECT p.id AS persona_id, p.workspace_id, p.owner_id FROM persona p "
                "JOIN workspace w ON w.id = p.workspace_id "
                "WHERE p.name = $1 AND p.is_managed = true AND w.content_locale = $3 "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM playbook pb "
                "  WHERE pb.workspace_id = p.workspace_id AND pb.name = $2"
                ")",
                pack.persona.name,
                playbook.name,
                locale,
            ):
                playbook_id = await conn.fetchval(
                    "INSERT INTO playbook "
                    "(workspace_id, owner_id, name, type, tags, triggers, "
                    " is_managed, managed_content_version, locale) "
                    "SELECT $1, $2, $3, $4, $5, $6, true, $7, $8 "
                    "WHERE NOT EXISTS ("
                    "  SELECT 1 FROM playbook WHERE workspace_id = $1 AND name = $3"
                    ") "
                    "RETURNING id",
                    prow["workspace_id"],
                    prow["owner_id"],
                    playbook.name,
                    playbook.type,
                    list(playbook.tags),
                    playbook.triggers,
                    BUILDER_CONTENT_VERSION,
                    locale,
                )
                if playbook_id is None:
                    # Race mit einem parallelen Sync/Seed — der andere Lauf hat
                    # bereits angelegt und gestempelt, nichts mehr zu tun.
                    continue
                await conn.execute(
                    "INSERT INTO playbook_version "
                    "(playbook_id, version, content, status, created_by, locale) "
                    "VALUES ($1, 1, $2::jsonb, 'active', $3, $4)",
                    playbook_id,
                    pb_json,
                    prow["owner_id"],
                    locale,
                )
                await conn.execute(
                    "INSERT INTO persona_playbook "
                    "(persona_id, playbook_id, workspace_id, owner_id) "
                    "VALUES ($1, $2, $3, $4) "
                    "ON CONFLICT (persona_id, playbook_id) DO NOTHING",
                    prow["persona_id"],
                    playbook_id,
                    prow["workspace_id"],
                    prow["owner_id"],
                )
                # Konventions-Link auch fuer nachgeruestete Playbooks: der
                # Resource-Insert-missing-Zweig unten verlinkt ALLE Builder-
                # Playbooks nur, wenn die Resource selbst noch fehlt — in
                # Bestands-Workspaces (Resource seit Content-Stand 5 vorhanden)
                # bekaeme ein neues Playbook sonst nie seinen lazy-Pointer.
                await conn.execute(
                    "INSERT INTO playbook_resource_link "
                    "(playbook_id, resource_id, block_id, workspace_id, owner_id, "
                    " position, link_scope) "
                    "SELECT $1, r.id, NULL, $2, $3, 0, 'resource' "
                    "FROM resource r WHERE r.workspace_id = $2 AND r.name = $4 "
                    "ON CONFLICT DO NOTHING",
                    playbook_id,
                    prow["workspace_id"],
                    prow["owner_id"],
                    pack.resource.name,
                )
                updated += 1

            # (5) Playbook-Content-Update bei Stempel-Rueckstand.
            for row in await conn.fetch(
                "SELECT pb.id FROM playbook pb "
                "JOIN workspace w ON w.id = pb.workspace_id "
                "WHERE pb.name = $1 AND pb.is_managed = true "
                "AND pb.managed_content_version < $2 AND w.content_locale = $3",
                playbook.name,
                BUILDER_CONTENT_VERSION,
                locale,
            ):
                await conn.execute(
                    "UPDATE playbook_version SET content = $2::jsonb "
                    "WHERE playbook_id = $1 AND status = 'active'",
                    row["id"],
                    pb_json,
                )
                # Beim Stempeln auch die Row-Metadaten nachziehen — Trigger-/
                # Tag-/Type-Aenderungen leben ausserhalb des Versions-Contents
                # und wuerden ueber das Content-Replace allein nie verteilen.
                await conn.execute(
                    "UPDATE playbook SET type = $2, tags = $3, triggers = $4, "
                    "managed_content_version = $5, updated_at = now() "
                    "WHERE id = $1",
                    row["id"],
                    playbook.type,
                    list(playbook.tags),
                    playbook.triggers,
                    BUILDER_CONTENT_VERSION,
                )
                updated += 1

        resource_json = json.dumps(_builder_resource_content(pack))
        builder_playbook_names = [playbook.name for playbook in pack.playbooks]

        # (6) Insert-missing: die Managed-Resource erreicht Bestands-Workspaces
        # nur hier (der Seed laeuft dort nie wieder). Match wie im Seed ueber
        # workspace_id + Pack-Name (gescopet auf Workspaces der Pack-Sprache);
        # die Builder-Playbooks fuer die Links werden ebenso per Pack-Name
        # aufgeloest (der Playbook-Insert-missing-Block oben lief bereits, die
        # sechs Rows existieren also).
        for rrow in await conn.fetch(
            "SELECT p.id AS persona_id, p.workspace_id, p.owner_id FROM persona p "
            "JOIN workspace w ON w.id = p.workspace_id "
            "WHERE p.name = $1 AND p.is_managed = true AND w.content_locale = $3 "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM resource r "
            "  WHERE r.workspace_id = p.workspace_id AND r.name = $2"
            ")",
            pack.persona.name,
            pack.resource.name,
            locale,
        ):
            resource_id = await conn.fetchval(
                "INSERT INTO resource "
                "(workspace_id, owner_id, name, slug, is_managed, "
                " managed_content_version, locale) "
                "SELECT $1, $2, $3, $5, true, $4, $6 "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM resource WHERE workspace_id = $1 AND name = $3"
                ") "
                "RETURNING id",
                rrow["workspace_id"],
                rrow["owner_id"],
                pack.resource.name,
                BUILDER_CONTENT_VERSION,
                pack.resource.slug,
                locale,
            )
            if resource_id is None:
                # Race mit einem parallelen Sync/Seed — der andere Lauf hat
                # bereits angelegt und gestempelt, nichts mehr zu tun.
                continue
            await conn.execute(
                "INSERT INTO resource_version "
                "(resource_id, version, content, status, created_by, locale) "
                "VALUES ($1, 1, $2::jsonb, 'active', $3, $4)",
                resource_id,
                resource_json,
                rrow["owner_id"],
                locale,
            )
            await conn.execute(
                "INSERT INTO playbook_resource_link "
                "(playbook_id, resource_id, block_id, workspace_id, owner_id, "
                " position, link_scope) "
                "SELECT pb.id, $2, NULL, $1, $3, 0, 'resource' "
                "FROM playbook pb WHERE pb.workspace_id = $1 AND pb.name = ANY($4::text[]) "
                "ON CONFLICT DO NOTHING",
                rrow["workspace_id"],
                resource_id,
                rrow["owner_id"],
                builder_playbook_names,
            )
            updated += 1

        # (7) Resource-Content-Update bei Stempel-Rueckstand — analog Playbooks.
        # Die Tags leben im Versions-Content (`ResourceContent.tags`) und
        # verteilen ueber das Content-Replace mit; auf der resource-Row gibt es
        # nur Stempel + updated_at.
        for row in await conn.fetch(
            "SELECT r.id FROM resource r "
            "JOIN workspace w ON w.id = r.workspace_id "
            "WHERE r.name = $1 AND r.is_managed = true "
            "AND r.managed_content_version < $2 AND w.content_locale = $3",
            pack.resource.name,
            BUILDER_CONTENT_VERSION,
            locale,
        ):
            await conn.execute(
                "UPDATE resource_version SET content = $2::jsonb "
                "WHERE resource_id = $1 AND status = 'active'",
                row["id"],
                resource_json,
            )
            await conn.execute(
                "UPDATE resource SET managed_content_version = $2, updated_at = now() "
                "WHERE id = $1",
                row["id"],
                BUILDER_CONTENT_VERSION,
            )
            updated += 1

        # (8) Managed-Agent-Sync (Content-Stand 6, seit WP8 locale-bewusst):
        # tool_policy UND Beschreibung der beiden Builder-Agenten werden bei
        # Stempel-Rueckstand auf den kanonischen Stand ersetzt — die Policy ist
        # locale-unabhaengig, die Beschreibung kommt aus dem Pack der
        # Workspace-Sprache. Wholesale-Replace ist sicher, weil managed =
        # gesperrt (keine User-Edits zu erhalten); ohne diesen Zweig bekaemen
        # Bestands-Builder neue Capabilities (z. B. `feedback_resolve`) nie.
        for agent_def in (pack.agent, pack.agent_lite):
            for row in await conn.fetch(
                "SELECT a.id FROM agent a "
                "JOIN workspace w ON w.id = a.workspace_id "
                "WHERE a.name = $1 AND a.is_managed = true "
                "AND a.managed_content_version < $2 AND w.content_locale = $3",
                agent_def.name,
                BUILDER_CONTENT_VERSION,
                locale,
            ):
                await conn.execute(
                    "UPDATE agent SET tool_policy = $2::jsonb, description = $3, "
                    "managed_content_version = $4, updated_at = now() WHERE id = $1",
                    row["id"],
                    agent_policy_json,
                    agent_def.description,
                    BUILDER_CONTENT_VERSION,
                )
                updated += 1

    return updated
