"""Persistenz fuer das Workspace-Aggregat (TASK-301).

Liest und schreibt `workspace`. Die Membership-Pruefung ist Aufgabe der
`WorkspaceMemberRepository`; dieses Repo arbeitet auf der Workspace-Ebene
und bekommt die User-Identitaet vom Service-Layer durchgereicht.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import WorkspaceRead


class WorkspaceRepository(Protocol):
    """Service-seitige Abstraktion fuer den Workspace-Zugriff."""

    async def list_by_org_for_user(self, org_id: UUID, user_id: UUID) -> list[WorkspaceRead]: ...

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None: ...

    async def create(self, org_id: UUID, user_id: UUID, name: str, slug: str) -> WorkspaceRead: ...

    async def update_name(self, workspace_id: UUID, name: str) -> WorkspaceRead | None: ...


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


# Seed-Bodies fuer die Default-Templates eines neuen Workspaces — Quelle der
# Migration 0023b und gleichzeitig Quelle dieser Laufzeit-Variante. Wir halten
# beide bewusst synchron (Test prueft die Slug-Liste).
_DEFAULT_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    (
        "customer-support-agent",
        "Customer-Support-Agent",
        "Du bist {{ persona.name }} — {{ persona.description }}.\n\n"
        "## Hintergrund zur Rolle\n{{ persona.profile }}\n\n"
        "## Themen-Tags\n{{ persona.tags }}\n\n"
        "## Spielbuecher\nFolge konsequent diesen Playbooks, wenn der Nutzer "
        "einen passenden Auslöser anspricht:\n{{ playbooks }}\n\n"
        "## Trigger-Stichworte\nReagiere besonders auf: {{ triggers }}\n\n"
        "## Wissensquellen\n{{ resources }}\n\n"
        "Antworte ruhig, präzise und in der gleichen Sprache wie der Nutzer.",
    ),
    (
        "knowledge-worker",
        "Knowledge-Worker",
        "Du bist {{ persona.name }}, ein Wissensarbeiter mit folgendem "
        "Profil:\n{{ persona.description }}\n\n"
        "## Persönliche Notizen\n{{ persona.profile }}\n\n"
        "## Verfügbares Wissen\n{{ resources }}\n\n"
        "## Arbeitsabläufe\n{{ playbooks }}\n\n"
        "Nutze die Wissensquellen, bevor du externe Annahmen triffst. "
        "Wenn die Quelle widersprüchlich ist, weise höflich darauf hin.",
    ),
    (
        "conversational-coach",
        "Conversational-Coach",
        "Du bist {{ persona.name }} — {{ persona.description }}.\n\n"
        "## Coach-Stimme\n{{ persona.profile }}\n\n"
        "## Schwerpunkte\nTags: {{ persona.tags }}\n\n"
        "## Methodenkasten\n{{ playbooks }}\n\n"
        "## Cues, die einen Methodenwechsel auslösen\n{{ triggers }}\n\n"
        "Bleibe stets gesprächig, stelle Fragen statt Antworten zu predigen, "
        "und beziehe die Methoden nur ein, wenn sie zum Gespräch passen.",
    ),
)


async def _seed_default_templates(
    conn: asyncpg.Connection, workspace_id: UUID, owner_id: UUID
) -> None:
    """Legt die drei Default-Templates eines neuen Workspaces an.

    Idempotent ueber ``ON CONFLICT (workspace_id, slug) DO NOTHING`` auf
    `system_prompt_template`. Versions-Insert per ``NOT EXISTS`` — wenn ein
    Template existiert (z. B. nach Re-Lauf), wird kein v1 mehr angelegt.
    Initial-Status ist `active`, sodass der Render-Endpoint sofort ohne
    Promote-Schritt feuert.
    """
    for slug, name, body in _DEFAULT_TEMPLATES:
        template_id = await conn.fetchval(
            "INSERT INTO system_prompt_template (workspace_id, owner_id, name, slug) "
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
