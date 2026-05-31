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


# BASE-Klauseln (D1/E4): erklaeren dem Agenten die drei Achsen.
# Einheitlich in alle Default-Templates eingebettet; nach den inhaltlichen
# Abschnitten, vor dem abschliessenden Verhaltenssatz.
_BASE_CLAUSES = (
    "## Agenten-Hinweise\n"
    "**Modi:** Wenn die Persona Modi fuehrt (siehe Profil-Abschnitt oben), "
    "waehle anhand des Modus-Triggers den passenden Modus und wende dessen "
    "Identity-Ergaenzung sowie Output-Stil an. Ohne Trigger-Match gilt der "
    "Default-Modus.\n\n"
    "**Composite-Playbooks:** Wenn ein Playbook ein Composite ist (Feld "
    "`composed_playbooks` nicht leer), folge der nummerierten Sub-Playbook-"
    "Sequenz der Reihe nach.\n\n"
    "**Applied vs. Triggered:** Fest eingebettete Playbooks (Pill) sind "
    "bereits expandiert und gelten immer. Weitere Playbooks nur bei "
    "Trigger-Match laden — erst `list_triggers()`, dann `fetch_playbook(id)`."
)

# Welle 6: BlockNote-Starter-Body lebt als Sidecar-JSON-Datei neben dem
# Modul. Triple-Quoted-Stringliteral wurde von ruff (line-length=100)
# wegen der inneren JSON-Keys mit "textAlignment" usw. flach abgelehnt;
# die Sidecar-Datei sortiert ausserdem das Dual-Maintenance mit der
# SQL-Migration 0027 (gleicher Body-Inhalt jetzt nur noch an zwei Stellen).
_WORKFLOW_STARTER_BLOCKNOTE_BODY = (Path(__file__).parent / "workflow_starter_body.json").read_text(
    encoding="utf-8"
)


# Seed-Bodies fuer die Default-Templates eines neuen Workspaces — Quelle der
# Migrationen 0023b/0027 und gleichzeitig Quelle dieser Laufzeit-Variante. Wir
# halten beide bewusst synchron (Test prueft die Slug-Liste).
# Format: (slug, name, body, body_format).
#
# E4-Checkliste (jedes Template enthaelt):
#   1. {{ persona profile }} — Persoenlichkeit + Modi
#   2. Platz fuer applied-Playbook-Pills (vom Autor gesetzt; hier: {{ playbooks }})
#   3. {{ tools-overview }} — Lookup-Wegweiser
#   4. {{ date }} — aktuelles Datum
#   5. BASE-Klauseln (_BASE_CLAUSES) — Modi / Composite / Applied-vs-Triggered
_DEFAULT_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    (
        "customer-support-agent",
        "Customer-Support-Agent",
        "Du bist {{ persona.name }} — {{ persona.description }}.\n"
        "Datum: {{ date }}\n\n"
        "## Hintergrund zur Rolle\n{{ persona.profile }}\n\n"
        "## Themen-Tags\n{{ persona.tags }}\n\n"
        "## Spielbuecher\nFolge konsequent diesen Playbooks, wenn der Nutzer "
        "einen passenden Auslöser anspricht:\n{{ playbooks }}\n\n"
        "## Trigger-Stichworte\nReagiere besonders auf: {{ triggers }}\n\n"
        "## Wissensquellen\n{{ resources }}\n\n"
        "## Werkzeuge\n{{ tools-overview }}\n\n"
        f"{_BASE_CLAUSES}\n\n"
        "Antworte ruhig, präzise und in der gleichen Sprache wie der Nutzer.",
        "plain",
    ),
    (
        "knowledge-worker",
        "Knowledge-Worker",
        "Du bist {{ persona.name }}, ein Wissensarbeiter mit folgendem "
        "Profil:\n{{ persona.description }}\n"
        "Datum: {{ date }}\n\n"
        "## Persönliche Notizen\n{{ persona.profile }}\n\n"
        "## Verfügbares Wissen\n{{ resources }}\n\n"
        "## Arbeitsabläufe\n{{ playbooks }}\n\n"
        "## Werkzeuge\n{{ tools-overview }}\n\n"
        f"{_BASE_CLAUSES}\n\n"
        "Nutze die Wissensquellen, bevor du externe Annahmen triffst. "
        "Wenn die Quelle widersprüchlich ist, weise höflich darauf hin.",
        "plain",
    ),
    (
        "conversational-coach",
        "Conversational-Coach",
        "Du bist {{ persona.name }} — {{ persona.description }}.\n"
        "Datum: {{ date }}\n\n"
        "## Coach-Stimme\n{{ persona.profile }}\n\n"
        "## Schwerpunkte\nTags: {{ persona.tags }}\n\n"
        "## Methodenkasten\n{{ playbooks }}\n\n"
        "## Cues, die einen Methodenwechsel auslösen\n{{ triggers }}\n\n"
        "## Werkzeuge\n{{ tools-overview }}\n\n"
        f"{_BASE_CLAUSES}\n\n"
        "Bleibe stets gesprächig, stelle Fragen statt Antworten zu predigen, "
        "und beziehe die Methoden nur ein, wenn sie zum Gespräch passen.",
        "plain",
    ),
    (
        "workflow-starter",
        "Workflow-Starter",
        _WORKFLOW_STARTER_BLOCKNOTE_BODY,
        "blocknote",
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
    for slug, name, body, body_format in _DEFAULT_TEMPLATES:
        template_id = await conn.fetchval(
            "INSERT INTO system_prompt_template "
            "(workspace_id, owner_id, name, slug, body_format) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (workspace_id, slug) DO NOTHING "
            "RETURNING id",
            workspace_id,
            owner_id,
            name,
            slug,
            body_format,
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
