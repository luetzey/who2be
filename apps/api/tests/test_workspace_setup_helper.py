"""Integrationstests fuer den Test-Helper `testing/workspace_setup.py`.

Belegt fuer beide mehrstufigen Helfer, dass sie atomar sind:

* `_ensure_workspace` (Issue #480) — der Seed (Org, Member, Workspace,
  Default-Templates, Agenten, Chunks) bricht ohne Teilzustand ab: keine Org
  ohne Workspace, kein Workspace ohne Membership. Der Test ist damit zugleich
  der Nachweis, dass der Helper dieselbe Vorbedingung herstellt wie der
  einzige Produktiv-Aufrufer (`PgMeRepository.fetch`,
  `repositories/me_repository.py`), der den Aufruf mit derselben Begruendung
  klammert.
* `cleanup_workspaces` (Issue #492) — der Abbau ueber die vier abhaengigen
  Tabellen (`agent_access_log` → `organization` → `org_member` →
  `workspace_member`) laeuft in **einer** Transaktion. Ohne die Klammer bliebe
  nach einem Abbruch das Compliance-Log geloescht, seine Organisation aber
  stehen — ein Zustand, den kein Produktivpfad erzeugen kann.

Beide Haelften stehen je als Paar da: der erzwungene Abbruch und die
Gegenprobe, dass der ungestoerte Lauf wirklich committet. Ohne die Gegenprobe
waere der Rollback-Test auch dann gruen, wenn die Transaktion die Wirkung
komplett verschluckt.
"""

import asyncio
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.repositories import workspace_repository
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)


class _SeedAborted(RuntimeError):
    """Eigener Typ, damit der Test nicht versehentlich einen echten Fehler schluckt."""


def _db_fetchval(sql: str, *args: object) -> Any:
    """Liest ueber eine *eigene* Connection — also nach Commit/Rollback des Seeds."""

    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_abgebrochener_seed_hinterlaesst_keinen_teilzustand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abbruch nach den Basis-Inserts → nichts davon ist danach in der DB.

    Der Abbruch wird bewusst in `_seed_default_templates` ausgeloest: zu dem
    Zeitpunkt sind Org, `org_member`, Workspace und `workspace_member` bereits
    geschrieben. Der Fake protokolliert, dass er diesen Teilzustand *innerhalb*
    der Transaktion sieht — sonst wuerde der Test auch dann gruen, wenn der
    Seed schon vor dem ersten Insert scheitert.
    """
    user_id = fresh_user_id()
    slug = str(user_id)
    seen_inside_transaction: list[int] = []

    async def _fake_seed_default_templates(
        conn: asyncpg.Connection,
        workspace_id: UUID,
        seed_user_id: UUID,
        content_locale: str,
    ) -> None:
        seen_inside_transaction.append(
            await conn.fetchval(
                "SELECT count(*) FROM workspace w "
                "JOIN organization o ON o.id = w.org_id "
                "WHERE o.kind = 'personal' AND o.slug = $1",
                slug,
            )
        )
        raise _SeedAborted("Seed-Abbruch mitten im Setup (Testfall)")

    monkeypatch.setattr(
        workspace_repository, "_seed_default_templates", _fake_seed_default_templates
    )

    try:
        with pytest.raises(_SeedAborted):
            setup_workspace(user_id)

        # Kontrolle: der Teilzustand existierte wirklich, bevor er zurueckrollte.
        assert seen_inside_transaction == [1]

        # Und ist danach vollstaendig weg — Org, Membership, Workspace.
        assert (
            _db_fetchval(
                "SELECT count(*) FROM organization WHERE kind = 'personal' AND slug = $1",
                slug,
            )
            == 0
        )
        assert _db_fetchval("SELECT count(*) FROM org_member WHERE user_id = $1", user_id) == 0
        assert (
            _db_fetchval("SELECT count(*) FROM workspace_member WHERE user_id = $1", user_id) == 0
        )
    finally:
        cleanup_workspaces([user_id])


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_seed_committet_und_bleibt_idempotent() -> None:
    """Gegenprobe: ohne Abbruch committet die Klammer, ein Re-Lauf dupliziert nichts.

    Ohne diese Gegenprobe koennte die Transaktion den Seed auch komplett
    verschlucken, und der Rollback-Test oben waere trotzdem gruen.
    """
    user_id = fresh_user_id()
    slug = str(user_id)
    try:
        workspace_id = setup_workspace(user_id)
        assert (
            _db_fetchval(
                "SELECT count(*) FROM workspace_member WHERE workspace_id = $1 AND user_id = $2",
                workspace_id,
                user_id,
            )
            == 1
        )

        assert setup_workspace(user_id) == workspace_id
        assert (
            _db_fetchval(
                "SELECT count(*) FROM organization WHERE kind = 'personal' AND slug = $1",
                slug,
            )
            == 1
        )
    finally:
        cleanup_workspaces([user_id])


# --- cleanup_workspaces: der Abbau ist eine Transaktion (Issue #492) ---------

_ACCESS_DATE = date(2026, 1, 1)


class _CleanupAborted(RuntimeError):
    """Eigener Typ, damit der Test nicht versehentlich einen echten Fehler schluckt."""


def _seed_access_log_row(workspace_id: UUID) -> UUID:
    """Legt eine `agent_access_log`-Zeile im Workspace an und gibt ihre id zurueck.

    Das Log ist die **erste** der vier Tabellen, die `cleanup_workspaces`
    abraeumt — ohne eine Zeile darin waere am Rollback nichts zu sehen. Der
    Agent kommt aus dem Seed (`_seed_default_agents`); faellt der weg, soll der
    Test laut scheitern statt still leer zu laufen.
    """
    agent_id = _db_fetchval(
        "SELECT id FROM agent WHERE workspace_id = $1 ORDER BY name LIMIT 1", workspace_id
    )
    assert agent_id is not None, "Workspace-Seed liefert keinen Agenten mehr."
    log_id = _db_fetchval(
        "INSERT INTO agent_access_log "
        "(workspace_id, agent_id, ref_kind, ref_id, operation, "
        " sensitivity_at_access, access_date) "
        "VALUES ($1, $2, 'artifact', $3, 'read', 'general', $4) "
        "RETURNING id",
        workspace_id,
        agent_id,
        str(uuid4()),
        _ACCESS_DATE,
    )
    assert log_id is not None
    return UUID(str(log_id))


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_abgebrochenes_cleanup_laesst_das_zugriffslog_stehen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Abbruch beim zweiten `DELETE` → auch das erste ist zurueckgerollt.

    Ohne die Klammer liefe jedes `DELETE` in einer eigenen Autocommit-
    Transaktion: das `agent_access_log` waere weg, seine Organisation stuende
    noch. Der Fake protokolliert, dass er das geloeschte Log *innerhalb* der
    Transaktion sieht — sonst wuerde der Test auch dann gruen, wenn der Abbau
    schon vor dem ersten `DELETE` scheitert.
    """
    user_id = fresh_user_id()
    slug = str(user_id)
    workspace_id = setup_workspace(user_id)
    _seed_access_log_row(workspace_id)

    seen_inside_transaction: list[int] = []
    original_execute = asyncpg.Connection.execute

    async def _execute_but_abort_on_org_delete(
        self: asyncpg.Connection, query: str, *args: object, **kwargs: object
    ) -> Any:
        if query.startswith("DELETE FROM organization"):
            seen_inside_transaction.append(
                await self.fetchval(
                    "SELECT count(*) FROM agent_access_log WHERE workspace_id = $1",
                    workspace_id,
                )
            )
            raise _CleanupAborted("Cleanup-Abbruch zwischen den DELETEs (Testfall)")
        return await original_execute(self, query, *args, **kwargs)

    monkeypatch.setattr(asyncpg.Connection, "execute", _execute_but_abort_on_org_delete)

    try:
        with pytest.raises(_CleanupAborted):
            cleanup_workspaces([user_id])

        monkeypatch.undo()

        # Kontrolle: das Log war innerhalb der Transaktion wirklich schon leer.
        assert seen_inside_transaction == [0]

        # Und ist danach wieder da — zusammen mit seiner Organisation.
        assert (
            _db_fetchval(
                "SELECT count(*) FROM agent_access_log WHERE workspace_id = $1", workspace_id
            )
            == 1
        )
        assert (
            _db_fetchval(
                "SELECT count(*) FROM organization WHERE kind = 'personal' AND slug = $1",
                slug,
            )
            == 1
        )
    finally:
        monkeypatch.undo()
        cleanup_workspaces([user_id])


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_cleanup_loescht_alle_vier_tabellen() -> None:
    """Gegenprobe: der ungestoerte Lauf raeumt wirklich alle vier ab.

    Ohne diese Gegenprobe koennte die Transaktion das Loeschen auch komplett
    verschlucken, und der Rollback-Test oben waere trotzdem gruen.
    """
    user_id = fresh_user_id()
    slug = str(user_id)
    workspace_id = setup_workspace(user_id)
    _seed_access_log_row(workspace_id)

    counts = {
        "agent_access_log": (
            "SELECT count(*) FROM agent_access_log WHERE workspace_id = $1",
            workspace_id,
        ),
        "organization": (
            "SELECT count(*) FROM organization WHERE kind = 'personal' AND slug = $1",
            slug,
        ),
        "org_member": ("SELECT count(*) FROM org_member WHERE user_id = $1", user_id),
        "workspace_member": (
            "SELECT count(*) FROM workspace_member WHERE user_id = $1",
            user_id,
        ),
    }

    # Vorher stehen in allen vier Tabellen Zeilen — sonst belegt das Cleanup nichts.
    for table, (sql, arg) in counts.items():
        assert _db_fetchval(sql, arg) >= 1, f"{table} war schon vor dem Cleanup leer."

    cleanup_workspaces([user_id])

    for table, (sql, arg) in counts.items():
        assert _db_fetchval(sql, arg) == 0, f"{table} wurde vom Cleanup nicht abgeraeumt."
