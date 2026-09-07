"""Integrationstest fuer den Test-Helper `testing/workspace_setup.py` (Issue #480).

Belegt die Eigenschaft, die die `conn.transaction()`-Klammer in
`_ensure_workspace` herstellt: der mehrstufige Seed (Org, Member, Workspace,
Default-Templates, Agenten, Chunks) ist atomar. Bricht er in der Mitte ab,
bleibt **kein** Teilzustand zurueck — keine Org ohne Workspace, kein Workspace
ohne Membership.

Der Test ist damit zugleich der Nachweis, dass der Helper dieselbe
Vorbedingung herstellt wie der einzige Produktiv-Aufrufer
(`PgMeRepository.fetch`, `repositories/me_repository.py`), der den Aufruf mit
derselben Begruendung klammert.
"""

import asyncio
from typing import Any
from uuid import UUID

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
