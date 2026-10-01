"""RLS fuer die Control-Plane-Tabellen (Migration 0092, ADR-0055 R3/R4).

`workspace`, `organization` und `status_history` hatten bis 0092 keine
Policy, `mcp_usage` nur eine permissive. Diese Tests laufen als Laufzeitrolle
`who2be_app` (NOBYPASSRLS) und lesen bewusst **ohne** `WHERE` — genau den
Fall, den RLS als zweite Linie abfangen soll. Als Owner waeren sie gruen,
ohne etwas zu beweisen.

Zusaetzlich: der Org-Purge (`PgAccountPurgeRepository.purge_organization`,
Owner-Verbindung wie der echte Purge-Job) laesst keine `status_history`-Zeilen
zurueck.

Laeuft in einem eigenen Schema wie `test_rls_isolation.py`.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import ORG_SETTING, TENANT_SETTING
from who2be_api.repositories.account_repository import PgAccountPurgeRepository

# Dieselbe Test-Konstante wie test_rls_isolation (die Rolle ist cluster-global).
_APP_PASSWORD = "rls_test_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


async def _seed_tenant(owner: asyncpg.Connection, key: str) -> dict[str, UUID]:
    """Org + Workspace + Persona + Statusverlauf + MCP-Zaehler eines Mandanten.

    Als Owner (RLS-Bypass). Der Statusverlauf wird ohne `workspace_id`
    eingefuegt — der Trigger aus 0092 muss sie aus der Persona ableiten.
    """
    user = uuid4()
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ($1, $1, 'company') RETURNING id",
        f"org-{key}-{secrets.token_hex(4)}",
    )
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, $2, $2) RETURNING id",
        org_id,
        f"ws-{key}",
    )
    persona_id: UUID = await owner.fetchval(
        "INSERT INTO persona (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
        ws_id,
        user,
        f"persona-{key}",
    )
    await owner.execute(
        "INSERT INTO status_history (entity_type, entity_id, from_status, to_status, changed_by) "
        "VALUES ('persona', $1, 'draft', 'review', $2)",
        persona_id,
        user,
    )
    await owner.execute(
        "INSERT INTO mcp_usage (org_id, period, count) VALUES ($1, '2026-10', 3)", org_id
    )
    return {"org": org_id, "ws": ws_id, "persona": persona_id, "user": user}


async def _in_schema(
    body: Callable[[asyncpg.Connection, asyncpg.Connection], Awaitable[None]], prefix: str
) -> None:
    """Migriert ein Wegwerf-Schema und reicht Owner- und App-Verbindung herein."""
    settings = get_settings()
    schema = f"{prefix}_{secrets.token_hex(6)}"
    owner = await asyncpg.connect(settings.database_url)
    app: asyncpg.Connection | None = None
    try:
        await owner.execute(f'CREATE SCHEMA "{schema}"')
        await owner.execute(f'SET search_path TO "{schema}"')
        await apply_migrations(owner, MIGRATIONS_DIR)
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        app = await asyncpg.connect(
            settings.database_url, user="who2be_app", password=_APP_PASSWORD
        )
        await app.execute(f'SET search_path TO "{schema}"')
        await body(owner, app)
    finally:
        if app is not None:
            await app.close()
        await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await owner.close()


async def _scope(app: asyncpg.Connection, tenant: UUID | None, org: UUID | None) -> None:
    """Setzt beide Mandanten-GUCs; `None` heisst leer wie nach dem Pool-Reset.

    Bewusst kein `RESET ALL`: das setzte auch den `search_path` zurueck, und
    die Abfragen liefen gegen `public` statt gegen das Test-Schema.
    """
    await app.execute(
        "SELECT set_config($1, $3, false), set_config($2, $4, false)",
        TENANT_SETTING,
        ORG_SETTING,
        str(tenant) if tenant is not None else "",
        str(org) if org is not None else "",
    )


@pytest.mark.integration
def test_control_plane_tables_hide_foreign_tenant_without_where() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def body(owner: asyncpg.Connection, app: asyncpg.Connection) -> None:
        a = await _seed_tenant(owner, "a")
        b = await _seed_tenant(owner, "b")

        # --- Mandant A gesetzt (wie unter get_current_workspace). ---
        await _scope(app, a["ws"], a["org"])
        assert {r["id"] for r in await app.fetch("SELECT id FROM workspace")} == {a["ws"]}
        assert {r["id"] for r in await app.fetch("SELECT id FROM organization")} == {a["org"]}
        history = await app.fetch("SELECT entity_id FROM status_history")
        assert {r["entity_id"] for r in history} == {a["persona"]}
        usage = await app.fetch("SELECT org_id FROM mcp_usage")
        assert {r["org_id"] for r in usage} == {a["org"]}

        # Schreiben in den fremden Mandanten trifft keine Zeile.
        assert await app.execute("UPDATE workspace SET name = 'x' WHERE id = $1", b["ws"]) == (
            "UPDATE 0"
        )
        assert await app.execute("UPDATE organization SET name = 'x' WHERE id = $1", b["org"]) == (
            "UPDATE 0"
        )
        assert await app.execute("UPDATE mcp_usage SET count = 0 WHERE org_id = $1", b["org"]) == (
            "UPDATE 0"
        )
        assert await owner.fetchval("SELECT name FROM workspace WHERE id = $1", b["ws"]) == "ws-b"

        # Den eigenen Workspace in die fremde Org umhaengen: WITH CHECK weist ab,
        # obwohl die Zeile ueber id = Mandant sichtbar ist.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute("UPDATE workspace SET org_id = $1 WHERE id = $2", b["org"], a["ws"])
        assert (
            await owner.fetchval("SELECT org_id FROM workspace WHERE id = $1", a["ws"]) == a["org"]
        )
        # Gewoehnliches Schreiben auf den eigenen Workspace bleibt erlaubt.
        assert await app.execute("UPDATE workspace SET name = 'ws-a' WHERE id = $1", a["ws"]) == (
            "UPDATE 1"
        )

        # Statusverlauf fuer eine fremde Entity: die Persona ist unsichtbar,
        # der Trigger findet keinen Workspace, WITH CHECK weist ab.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, 'review', 'active', $2)",
                b["persona"],
                a["user"],
            )
        # Ein mitgegebener fremder workspace_id wird vom Trigger ueberschrieben.
        await app.execute(
            "INSERT INTO status_history "
            "(entity_type, entity_id, from_status, to_status, changed_by, workspace_id) "
            "VALUES ('persona', $1, 'review', 'active', $2, $3)",
            a["persona"],
            a["user"],
            b["ws"],
        )
        derived = await owner.fetch(
            "SELECT workspace_id FROM status_history WHERE entity_id = $1", a["persona"]
        )
        assert {r["workspace_id"] for r in derived} == {a["ws"]}

        # Neue MCP-Zaehlung nur fuer die eigene Org.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.execute(
                "INSERT INTO mcp_usage (org_id, period, count) VALUES ($1, '2026-11', 1)",
                b["org"],
            )

        # --- Nur Workspace gesetzt (tenant_scope(ws, None)): bleibt strikt. ---
        await _scope(app, a["ws"], None)
        assert {r["id"] for r in await app.fetch("SELECT id FROM workspace")} == {a["ws"]}
        assert await app.fetch("SELECT id FROM organization") == []
        # Schreiben auf den eigenen Workspace bleibt ohne Org-GUC moeglich.
        assert await app.execute("UPDATE workspace SET name = 'ws-a' WHERE id = $1", a["ws"]) == (
            "UPDATE 1"
        )

        # --- Kein Mandant: Aufloesungspfade sehen Stammdaten (permissiv) ... ---
        await _scope(app, None, None)
        ws_all = {r["id"] for r in await app.fetch("SELECT id FROM workspace")}
        assert {a["ws"], b["ws"]} <= ws_all
        org_all = {r["id"] for r in await app.fetch("SELECT id FROM organization")}
        assert {a["org"], b["org"]} <= org_all
        # ... aber weder Statusverlauf noch MCP-Zaehler (strikt, fail-closed).
        assert await app.fetch("SELECT id FROM status_history") == []
        assert await app.fetch("SELECT org_id FROM mcp_usage") == []

    asyncio.run(_in_schema(body, "rlscp"))


@pytest.mark.integration
def test_workspace_policy_allows_org_siblings_for_last_workspace_guard() -> None:
    """Der Last-Workspace-Schutz (`PgWorkspaceRepository.delete`) zaehlt alle
    Workspaces der Org unter dem Mandanten eines davon. Die Policy muss die
    Geschwister derselben Org zeigen — und nur diese."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def body(owner: asyncpg.Connection, app: asyncpg.Connection) -> None:
        a = await _seed_tenant(owner, "a")
        b = await _seed_tenant(owner, "b")
        sibling: UUID = await owner.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'zwei', 'zwei') RETURNING id",
            a["org"],
        )
        await _scope(app, a["ws"], a["org"])
        count = await app.fetchval("SELECT count(*) FROM workspace WHERE org_id = $1", a["org"])
        assert count == 2
        visible = {r["id"] for r in await app.fetch("SELECT id FROM workspace")}
        assert visible == {a["ws"], sibling}
        assert b["ws"] not in visible

    asyncio.run(_in_schema(body, "rlscpsib"))


@pytest.mark.integration
def test_org_purge_leaves_no_status_history() -> None:
    """R4a: nach `purge_organization` bleibt kein Statusverlauf der Org stehen;
    der einer fremden Org bleibt unberuehrt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    async def body(owner: asyncpg.Connection, _app: asyncpg.Connection) -> None:
        a = await _seed_tenant(owner, "a")
        b = await _seed_tenant(owner, "b")
        # Altbestand: Entity vor dem Purge geloescht, Zeile haengt nur noch am
        # Workspace — genau der Fall, der vor 0092 verwaist zurueckblieb.
        await owner.execute("DELETE FROM persona WHERE id = $1", a["persona"])
        before = await owner.fetchval(
            "SELECT count(*) FROM status_history WHERE entity_id = $1", a["persona"]
        )
        assert before == 1, "Sanity: Statusverlauf von A muss vor dem Purge existieren"

        await PgAccountPurgeRepository(owner).purge_organization(a["org"])

        left_a = await owner.fetchval(
            "SELECT count(*) FROM status_history WHERE entity_id = $1", a["persona"]
        )
        assert left_a == 0, "Org-Purge hat status_history-Zeilen zurueckgelassen"
        left_b = await owner.fetchval(
            "SELECT count(*) FROM status_history WHERE entity_id = $1", b["persona"]
        )
        assert left_b == 1

    asyncio.run(_in_schema(body, "rlscppurge"))
