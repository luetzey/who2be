"""Persistenz fuer das Workspace-Aggregat (TASK-301).

Liest und schreibt `workspace`. Die Membership-Pruefung ist Aufgabe der
`WorkspaceMemberRepository`; dieses Repo arbeitet auf der Workspace-Ebene
und bekommt die User-Identitaet vom Service-Layer durchgereicht.
"""

from pathlib import Path
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import WorkspaceRead


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
        template_id = await conn.fetchval(
            "INSERT INTO system_prompt_template "
            "(workspace_id, owner_id, name, slug) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (workspace_id, slug) DO NOTHING "
            "RETURNING id",
            workspace_id,
            owner_id,
            name,
            slug,
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
            f'{{"description": "", "body": {_json_escape(body)}}}',
            owner_id,
        )


def _json_escape(text: str) -> str:
    """Minimaler JSON-String-Escape (Quotes + Backslashes + Newlines).

    Wir bauen das jsonb-Literal bewusst ohne externe ``json``-Import-Aufrufe,
    damit der Helper nah am SQL bleibt. Reicht fuer Fixed-Strings aus unserer
    eigenen Konstanten-Tabelle.
    """
    import json

    return json.dumps(text, ensure_ascii=False)
