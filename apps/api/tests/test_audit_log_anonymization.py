"""`audit_log` wird beim Loeschen von Workspace/Org anonymisiert (Migration 0106).

Owner-Entscheidung E1a: „Beim Loeschen bleiben Aktion, Zeitpunkt und Scope;
Akteur, Ziel und personenbezogene Details werden geleert." Den Grundfall
(Workspace-Delete, Org-Purge) belegt `test_kb_chunk_workspace_erasure.py`.
Hier stehen die Faelle, an denen die Umsetzung brechen kann:

* der API-Workspace-Delete laeuft in der Cloud als `who2be_app`, die auf
  `audit_log` nur SELECT/INSERT hat — der Trigger muss trotzdem greifen, und
  die Rolle darf dadurch kein UPDATE-Recht bekommen;
* die `detail`-Allowlist behaelt je Aktion nur ihre Schluessel, eine Aktion
  ohne Eintrag verliert `detail` ganz (fail-closed);
* Zeilen aus einem schon frueher geloeschten Workspace werden mit der
  Migration nachgezogen;
* jede Audit-Aktion im Code hat einen Allowlist-Eintrag (Guard).

Alle Faelle laufen gegen die echte DB in einem frisch migrierten
Wegwerf-Schema. Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1`
schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository

pytestmark = pytest.mark.integration

_MIGRATION = "0106_audit_log_anonymize_on_purge.sql"
# Test-only Passwort der App-Rolle — dieselbe Konstante wie test_rls_isolation.
_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CODE_ROOTS = (
    _REPO_ROOT / "apps" / "api" / "src",
    _REPO_ROOT / "packages" / "models" / "src",
)

Body = Callable[[asyncpg.Connection, str], Awaitable[None]]


def _in_isolated_schema(body: Body, *, stop_before: str | None = None) -> None:
    """Owner-Verbindung auf einem frisch migrierten Wegwerf-Schema."""
    schema = f"audit_anon_{secrets.token_hex(6)}"
    url = get_settings().database_url

    async def _run() -> None:
        owner = await asyncpg.connect(url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}", public')
            if stop_before is None:
                await apply_migrations(owner, MIGRATIONS_DIR)
            else:
                await _apply_until(owner, stop_before)
            await body(owner, schema)
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _apply_until(conn: asyncpg.Connection, stop_before: str) -> None:
    """Alle Migrationen alphabetisch vor `stop_before`, mit Runner-Eintrag."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    for path in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        if path.name >= stop_before:
            break
        async with conn.transaction():
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.name)


async def _org(owner: asyncpg.Connection) -> UUID:
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"o-{secrets.token_hex(4)}",
    )
    return org_id


async def _workspace(owner: asyncpg.Connection, org_id: UUID) -> UUID:
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', $2) RETURNING id",
        org_id,
        f"w-{secrets.token_hex(4)}",
    )
    return ws_id


async def _audit(
    owner: asyncpg.Connection,
    *,
    action: str,
    org_id: UUID | None,
    ws: UUID | None,
    actor: UUID | None,
    detail: dict[str, object],
) -> UUID:
    row_id: UUID = await owner.fetchval(
        "INSERT INTO audit_log (org_id, workspace_id, actor_id, action, target, detail) "
        "VALUES ($1, $2, $3, $4, 'ziel', $5::text::jsonb) RETURNING id",
        org_id,
        ws,
        actor,
        action,
        json.dumps(detail),
    )
    return row_id


async def _row(owner: asyncpg.Connection, row_id: UUID) -> asyncpg.Record:
    row: asyncpg.Record | None = await owner.fetchrow(
        "SELECT org_id, workspace_id, actor_id, action, target, detail::text AS detail, "
        "anonymized_at FROM audit_log WHERE id = $1",
        row_id,
    )
    assert row is not None, "audit_log-Zeile ist verschwunden"
    return row


def test_app_role_workspace_delete_anonymizes_without_update_grant() -> None:
    """Cloud-Pfad: `who2be_app` loescht, der Trigger anonymisiert als Owner.

    Als Owner/Superuser waere der Test gruen, ohne etwas zu beweisen — deshalb
    laeuft der Delete ueber einen Pool der App-Rolle. Danach darf dieselbe
    Rolle `audit_log` weiterhin nicht aendern und die Trigger-Funktion nicht
    aufrufen (append-only bleibt).
    """

    async def body(owner: asyncpg.Connection, schema: str) -> None:
        org_id = await _org(owner)
        doomed, sibling = await _workspace(owner, org_id), await _workspace(owner, org_id)
        actor = uuid4()
        gone = await _audit(
            owner,
            action="token.issued",
            org_id=None,
            ws=doomed,
            actor=actor,
            detail={"name": "Laptop von Anna", "role": "editor", "agent_id": str(uuid4())},
        )
        kept = await _audit(
            owner,
            action="token.issued",
            org_id=None,
            ws=sibling,
            actor=actor,
            detail={"name": "x", "role": "viewer"},
        )
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        pool = await asyncpg.create_pool(
            get_settings().database_url,
            user="who2be_app",
            password=_APP_PASSWORD,
            min_size=1,
            max_size=1,
            server_settings={
                "search_path": f'"{schema}"',
                "app.current_tenant": str(doomed),
                "app.current_org": str(org_id),
            },
        )
        assert pool is not None
        try:
            assert await PgWorkspaceRepository(pool).delete(doomed) is True

            row = await _row(owner, gone)
            assert row["actor_id"] == ANONYMIZED_USER_ID
            assert row["target"] is None
            assert row["detail"] == '{"role": "editor"}', "Token-Name/Agent-ID ueberlebt"
            assert row["action"] == "token.issued"
            assert row["workspace_id"] == doomed
            assert row["anonymized_at"] is not None
            untouched = await _row(owner, kept)
            assert untouched["actor_id"] == actor
            assert untouched["anonymized_at"] is None

            async with pool.acquire() as app:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute("UPDATE audit_log SET target = 'x' WHERE id = $1", kept)
                with pytest.raises(asyncpg.PostgresError):
                    await app.execute("SELECT w2b_audit_anonymize_scope()")
        finally:
            await pool.close()

    _in_isolated_schema(body)


def test_allowlist_filters_detail_per_action_and_fails_closed() -> None:
    """Je Aktion nur die Allowlist-Schluessel; ohne Eintrag `{}`; NULL-Akteur bleibt."""

    async def body(owner: asyncpg.Connection, _schema: str) -> None:
        org_id = await _org(owner)
        ws = await _workspace(owner, org_id)
        await _workspace(owner, org_id)  # der letzte Workspace ist geschuetzt
        rule = await _audit(
            owner,
            action="workarea.rules_reapplied",
            org_id=None,
            ws=ws,
            actor=uuid4(),
            detail={"pattern": "Anna Schmidt", "category": "privat", "tables": {"t": 3}},
        )
        unknown = await _audit(
            owner,
            action="probe.unbekannt",
            org_id=None,
            ws=ws,
            actor=uuid4(),
            detail={"role": "admin", "email": "a@example.com"},
        )
        system = await _audit(
            owner,
            action="token.role_capped",
            org_id=None,
            ws=ws,
            actor=None,
            detail={"from_role": "admin", "to_role": "editor", "agent_id": str(uuid4())},
        )
        org_level = await _audit(
            owner,
            action="org.soft_deleted",
            org_id=org_id,
            ws=None,
            actor=uuid4(),
            detail={"purge_after": "2026-11-09T00:00:00+00:00"},
        )

        await PgAccountPurgeRepository(owner).purge_organization(org_id)

        assert (await _row(owner, rule))["detail"] == "{}"
        assert (await _row(owner, unknown))["detail"] == "{}", "Aktion ohne Eintrag behielt detail"
        capped = await _row(owner, system)
        assert capped["actor_id"] is None, "System-Ereignis bekam einen Akteur"
        assert json.loads(capped["detail"]) == {"from_role": "admin", "to_role": "editor"}
        org_row = await _row(owner, org_level)
        assert org_row["org_id"] == org_id
        assert org_row["workspace_id"] is None
        assert org_row["actor_id"] == ANONYMIZED_USER_ID
        assert org_row["target"] is None
        assert json.loads(org_row["detail"]) == {"purge_after": "2026-11-09T00:00:00+00:00"}

    _in_isolated_schema(body)


def test_migration_anonymizes_rows_of_already_deleted_scopes() -> None:
    """Bestand: Zeilen eines vor 0106 geloeschten Workspace/Org werden nachgezogen."""

    async def body(owner: asyncpg.Connection, _schema: str) -> None:
        org_id = await _org(owner)
        live = await _workspace(owner, org_id)
        actor = uuid4()
        orphan_ws = await _audit(
            owner,
            action="member.removed",
            org_id=None,
            ws=uuid4(),
            actor=actor,
            detail={"role": "editor", "note": "frei"},
        )
        orphan_org = await _audit(
            owner,
            action="org.soft_deleted",
            org_id=uuid4(),
            ws=None,
            actor=actor,
            detail={"purge_after": "2026-01-01"},
        )
        alive = await _audit(
            owner,
            action="member.removed",
            org_id=org_id,
            ws=live,
            actor=actor,
            detail={"role": "editor", "note": "frei"},
        )

        await apply_migrations(owner, MIGRATIONS_DIR)

        row = await _row(owner, orphan_ws)
        assert row["actor_id"] == ANONYMIZED_USER_ID
        assert row["target"] is None
        assert row["detail"] == '{"role": "editor"}'
        assert (await _row(owner, orphan_org))["anonymized_at"] is not None
        untouched = await _row(owner, alive)
        assert untouched["actor_id"] == actor
        assert untouched["target"] == "ziel"
        assert untouched["anonymized_at"] is None

    _in_isolated_schema(body, stop_before=_MIGRATION)


# Aktionen im Code: `action="x.y"` (AuditService.record), Konstanten
# `*_AUDIT_ACTION = "x.y"` (Repositories, Modelle) und Literale in
# Migrationen, die selbst in `audit_log` schreiben (0088).
_ACTION_NAME = r"\"([a-z_]+(?:\.[a-z_]+)+)\""
_ACTION_KWARG = re.compile(r"\baction\s*=\s*" + _ACTION_NAME)
_ACTION_CONST = re.compile(r"\b[A-Z_]*AUDIT_ACTION\s*(?::\s*\w+\s*)?=\s*" + _ACTION_NAME)
_SQL_LITERAL = re.compile(r"'([a-z_]+(?:\.[a-z_]+)+)'")


def _code_actions() -> set[str]:
    found: set[str] = set()
    for root in _CODE_ROOTS:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            found.update(_ACTION_KWARG.findall(text))
            found.update(_ACTION_CONST.findall(text))
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name == _MIGRATION:
            continue
        text = path.read_text(encoding="utf-8")
        if "INSERT INTO audit_log" in text:
            found.update(a for a in _SQL_LITERAL.findall(text) if not a.startswith("app."))
    return found


def test_every_audit_action_has_an_allowlist_entry() -> None:
    """Guard: eine neue Aktion ohne Allowlist-Eintrag macht diesen Test rot.

    Die Allowlist lebt nur in der DB (`w2b_audit_detail_allowlist()`, 0106);
    eine neue Aktion ergaenzt sie per neuer Migration. Ohne Eintrag waere ihr
    `detail` nach dem Loeschen zwar leer (fail-closed), aber die Entscheidung,
    was davon personenbezogen ist, waere nie getroffen worden.
    """
    actions = _code_actions()
    assert "member.removed" in actions, "Sanity: der Sammler findet keine Aktionen"

    async def body(owner: asyncpg.Connection, _schema: str) -> None:
        allowlist = json.loads(await owner.fetchval("SELECT w2b_audit_detail_allowlist()::text"))
        missing = sorted(actions - allowlist.keys())
        assert not missing, f"Audit-Aktionen ohne Allowlist-Eintrag (Migration noetig): {missing}"
        stale = sorted(allowlist.keys() - actions)
        assert not stale, f"Allowlist-Eintraege ohne Aktion im Code: {stale}"

    _in_isolated_schema(body)
