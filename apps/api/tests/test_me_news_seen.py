"""„Was ist neu“ gesehen und Kontoanlage am Konto (ADR-0060 §4, Migration 0110).

Belegt die Akzeptanzkriterien der Karte t_f18f38ee (Onboarding P5-API):

* `GET /v1/me` liefert `news_seen_at` und `created_at` des eigenen Kontos.
* `PATCH /v1/me/news-seen` setzt den Wert auf jetzt, wiederholbar, eine Zeile.
* Ein fremdes Konto liest und setzt den Wert nicht (Rot-Probe: ohne
  `WHERE user_id` im Lesepfad sieht das zweite Konto den Wert des ersten).
* Agent-Token: PATCH 403, und `GET /v1/me` gibt die Kontofelder nicht heraus.
* DSGVO-Export enthaelt den Wert, Konto-Purge loescht ihn.

Ohne erreichbare DB greift der zentrale Skip aus `conftest.py`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.repositories.account_repository import PgAccountPurgeRepository
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_PATH = "/v1/me/news-seen"
_CREATED = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)


def _db(query: str, *args: object) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(query, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _rows(user: UUID) -> int:
    return int(_db("SELECT count(*) AS n FROM account_state WHERE user_id = $1", user)[0]["n"])


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_me_reports_created_at_and_news_seen_only_for_own_account(
    make_auth_headers: AuthFactory,
) -> None:
    me, other = fresh_user_id(), fresh_user_id()
    setup_workspace(me)
    setup_workspace(other)
    seed_auth_user(me, "news-me@example.com", None)
    _db("UPDATE auth.users SET created_at = $2 WHERE id = $1", me, _CREATED)
    me_auth, other_auth = make_auth_headers(me), make_auth_headers(other)
    try:
        with TestClient(app) as client:
            fresh = client.get("/v1/me", headers=me_auth)
            assert fresh.status_code == 200, fresh.text
            assert fresh.json()["news_seen_at"] is None
            assert _parse(fresh.json()["created_at"]) == _CREATED

            first = client.patch(_PATH, headers=me_auth)
            assert first.status_code == 200, first.text
            seen = _parse(first.json()["news_seen_at"])

            after = client.get("/v1/me", headers=me_auth).json()
            assert _parse(after["news_seen_at"]) == seen

            # Wiederholt: kein Fehler, weiterhin genau eine Zeile, Zeit rueckt vor.
            second = client.patch(_PATH, headers=me_auth)
            assert second.status_code == 200, second.text
            assert _parse(second.json()["news_seen_at"]) >= seen
            assert _rows(me) == 1

            # Das andere Konto sieht davon nichts ...
            theirs = client.get("/v1/me", headers=other_auth).json()
            assert theirs["news_seen_at"] is None
            # ... und sein PATCH schreibt nur die eigene Zeile.
            mine_before = _db("SELECT news_seen_at FROM account_state WHERE user_id = $1", me)
            assert client.patch(_PATH, headers=other_auth).status_code == 200
            mine_after = _db("SELECT news_seen_at FROM account_state WHERE user_id = $1", me)
            assert mine_after == mine_before
            assert _rows(other) == 1
            assert _parse(client.get("/v1/me", headers=me_auth).json()["news_seen_at"]) == _parse(
                second.json()["news_seen_at"]
            )
    finally:
        _db("DELETE FROM account_state WHERE user_id = ANY($1::uuid[])", [me, other])
        cleanup_workspaces([me, other])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_agent_token_cannot_set_or_read_account_fields(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    seed_auth_user(owner, "news-agent@example.com", None)
    _db("UPDATE auth.users SET created_at = $2 WHERE id = $1", owner, _CREATED)
    human = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            _agent, token = agent_token(client, f"/v1/workspaces/{ws}", "[News] Agent", {}, human)
            denied = client.patch(_PATH, headers=token)
            assert denied.status_code == 403, denied.text
            assert denied.json()["reason"] == "account_route_requires_human"
            assert _rows(owner) == 0, "Der abgewiesene Aufruf darf nichts schreiben."

            assert client.patch(_PATH, headers=human).status_code == 200
            # `GET /v1/me` bleibt fuer Tokens offen (MCP), traegt aber keine
            # personenbezogenen Kontofelder.
            token_view = client.get("/v1/me", headers=token)
            assert token_view.status_code == 200, token_view.text
            assert token_view.json()["news_seen_at"] is None
            assert token_view.json()["created_at"] is None
    finally:
        _db("DELETE FROM account_state WHERE user_id = $1", owner)
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_export_contains_and_purge_removes_news_seen(make_auth_headers: AuthFactory) -> None:
    user = fresh_user_id()
    setup_workspace(user)
    auth = make_auth_headers(user)
    try:
        with TestClient(app) as client:
            empty = client.get("/v1/gdpr/export", headers=auth)
            assert empty.status_code == 200, empty.text
            assert empty.json()["account_state"]["news_seen_at"] is None

            seen = client.patch(_PATH, headers=auth).json()["news_seen_at"]
            export = client.get("/v1/gdpr/export", headers=auth)
            assert export.status_code == 200, export.text
            assert _parse(export.json()["account_state"]["news_seen_at"]) == _parse(seen)
        assert _rows(user) == 1

        async def _purge() -> None:
            conn = await asyncpg.connect(get_settings().database_url)
            try:
                await PgAccountPurgeRepository(conn).purge_account_data(user)
            finally:
                await conn.close()

        asyncio.run(_purge())
        assert _rows(user) == 0
    finally:
        _db("DELETE FROM account_state WHERE user_id = $1", user)
        cleanup_workspaces([user])
