"""Tutorial-Fortschritt am Konto (ADR-0060, Onboarding P1).

Zwei Schichten in einer Datei:

* **Ohne DB:** Katalog-Validierung (`load_tutorial_catalog`) und die reine
  Zustandsregel `build_tutorial_read` — welche Schritte gelten als erledigt,
  was schlaegt was.
* **Integration:** die vier Routen unter `/v1/me/tutorials` gegen die echte
  App. Belegt werden die Akzeptanzkriterien der Karte t_cdf85bb8: ID-Form
  und unbekannte IDs, kein Schreiben fremder Konten, abgeleitete Schritte
  (erster MCP-Abruf, Agent angelegt, eigener Agent), Neustart nur fuer dieses Tutorial,
  Purge bei Konto-Loeschung, Export im DSGVO-Buendel, Token-Sperre.

Integrationsteil nutzt die zentralen Fixtures aus `conftest.py`. Ohne
erreichbare DB greift der zentrale Skip.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.main import app
from who2be_api.repositories.tutorial_repository import (
    DerivedSignals,
    PgTutorialRepository,
    StepProgressRow,
    TutorialStateRow,
)
from who2be_api.routers.me import get_tutorial_service
from who2be_api.services.tutorial_service import TutorialService, build_tutorial_read
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models.tutorial import (
    TutorialDefinition,
    TutorialPatch,
    load_tutorial_catalog,
    tutorial_catalog,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_TUTORIAL = "getting-started"
_BASE = f"/v1/me/tutorials/{_TUTORIAL}"
_NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
_NO_SIGNALS = DerivedSignals(None, None, None)


# --------------------------------------------------------------------------
# Katalog und Zustandsregel (ohne DB)
# --------------------------------------------------------------------------


def test_shipped_catalog_is_valid_and_has_getting_started() -> None:
    catalog = tutorial_catalog()
    assert _TUTORIAL in catalog
    steps = [(s.id, s.type) for s in catalog[_TUTORIAL].steps]
    assert steps == [
        ("builder-ready", "head_start"),
        ("connect-claude", "first_mcp_call"),
        ("build-own-agent", "own_agent_mcp_call"),
        ("learn-feedback", "page_visited"),
    ]


def test_catalog_rejects_mismatched_filename_and_bad_definitions(tmp_path: Path) -> None:
    good = {"id": "x", "audience": "everyone", "steps": [{"id": "a", "type": "manual"}]}
    (tmp_path / "y.json").write_text(json.dumps(good))
    with pytest.raises(ValueError, match="Dateinamen"):
        load_tutorial_catalog(tmp_path)

    bad_cases: list[dict[str, object]] = [
        {**good, "id": "Gross"},  # keine Slug-Form
        {**good, "steps": [{"id": "a", "type": "telepathy"}]},  # Typ nicht im Katalog
        {**good, "steps": [{"id": "a", "type": "manual"}, {"id": "a", "type": "manual"}]},
        {**good, "steps": [{"id": "a", "type": "page_visited"}]},  # `page` fehlt
        {**good, "steps": [{"id": "a", "type": "manual", "page": "/x"}]},  # `page` zu viel
        {**good, "steps": []},
    ]
    for case in bad_cases:
        with pytest.raises(ValidationError):
            TutorialDefinition.model_validate(case)


def test_patch_body_requires_step_and_state_together() -> None:
    TutorialPatch(step_id="a", state="done")
    TutorialPatch(welcome_seen=True)
    for bad in ({"step_id": "a"}, {"state": "done"}, {}, {"step_id": "A", "state": "done"}):
        with pytest.raises(ValidationError):
            TutorialPatch.model_validate(bad)


def _states(read: object) -> dict[str, str]:
    return {s.id: s.state for s in read.steps}  # type: ignore[attr-defined]


def test_state_rule_head_start_signals_and_manual_rows() -> None:
    definition = tutorial_catalog()[_TUTORIAL]

    fresh = build_tutorial_read(definition, None, {}, _NO_SIGNALS)
    assert _states(fresh) == {
        "builder-ready": "done",
        "connect-claude": "open",
        "build-own-agent": "open",
        "learn-feedback": "open",
    }
    assert not fresh.completed

    # Ein erkanntes Ereignis schlaegt ein frueheres Ueberspringen; ein
    # gespeichertes `done` auf einem automatischen Schritt zaehlt nicht.
    progress = {
        (_TUTORIAL, "connect-claude"): StepProgressRow("skipped", _NOW),
        (_TUTORIAL, "build-own-agent"): StepProgressRow("done", _NOW),
        (_TUTORIAL, "learn-feedback"): StepProgressRow("done", _NOW),
    }
    signals = DerivedSignals(first_mcp_call=_NOW, agent_created=None, own_agent_mcp_call=None)
    read = build_tutorial_read(definition, TutorialStateRow(_NOW, None), progress, signals)
    assert _states(read) == {
        "builder-ready": "done",
        "connect-claude": "done",
        "build-own-agent": "open",
        "learn-feedback": "done",
    }
    assert read.welcome_seen_at == _NOW
    connect = next(s for s in read.steps if s.id == "connect-claude")
    assert connect.automatic and connect.completed_at == _NOW

    all_done = build_tutorial_read(
        definition,
        None,
        {(_TUTORIAL, "learn-feedback"): StepProgressRow("skipped", _NOW)},
        DerivedSignals(_NOW, _NOW, _NOW),
    )
    assert all_done.completed


# --------------------------------------------------------------------------
# Integration
# --------------------------------------------------------------------------


def _db(query: str, *args: object) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(query, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _usage(ws: UUID, user: UUID, agent_id: str, at: datetime) -> None:
    """Eine serverseitig gezaehlte Auslieferung (Muster `record_server_usage`)."""
    _db(
        "INSERT INTO usage_event "
        "(workspace_id, agent_id, actor_id, entity_type, entity_id, version, source, created_at) "
        "VALUES ($1, $2, $3, 'persona', $4, 1, 'server', $5)",
        ws,
        UUID(agent_id),
        user,
        uuid4(),
        at,
    )


def _rows(user: UUID) -> int:
    rows = _db(
        "SELECT (SELECT count(*) FROM tutorial_progress WHERE user_id = $1) "
        "     + (SELECT count(*) FROM tutorial_state WHERE user_id = $1) AS n",
        user,
    )
    return int(rows[0]["n"])


def _step(body: dict[str, object], step_id: str) -> str:
    steps = body["steps"]
    assert isinstance(steps, list)
    return str(next(s["state"] for s in steps if s["id"] == step_id))


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_ids_are_checked_against_form_and_catalog(make_auth_headers: AuthFactory) -> None:
    user = fresh_user_id()
    auth = make_auth_headers(user)
    try:
        with TestClient(app) as client:
            listed = client.get("/v1/me/tutorials", headers=auth)
            assert listed.status_code == 200, listed.text
            assert [t["id"] for t in listed.json()] == [_TUTORIAL]

            # Falsche Form: Pfad-Validierung, nichts erreicht den Service.
            for bad in ("Gross", "a" * 65, "a_b"):
                res = client.get(f"/v1/me/tutorials/{bad}", headers=auth)
                assert res.status_code == 422, (bad, res.text)
            # Richtige Form, unbekannt: 422 mit `loc` auf das Feld.
            unknown = client.get("/v1/me/tutorials/no-such-tutorial", headers=auth)
            assert unknown.status_code == 422
            assert unknown.json()["detail"][0]["loc"] == ["path", "tutorial_id"]
            unknown_step = client.patch(
                _BASE, json={"step_id": "no-such-step", "state": "done"}, headers=auth
            )
            assert unknown_step.status_code == 422
            assert unknown_step.json()["detail"][0]["loc"] == ["body", "step_id"]
            # Automatische Schritte lassen sich nicht von Hand abhaken.
            forged = client.patch(
                _BASE, json={"step_id": "connect-claude", "state": "done"}, headers=auth
            )
            assert forged.status_code == 422, forged.text
            # Unbekannte Felder (etwa ein fremder `user_id`) lehnt das Modell ab.
            smuggled = client.patch(
                _BASE,
                json={"welcome_seen": True, "user_id": str(uuid4())},
                headers=auth,
            )
            assert smuggled.status_code == 422
        assert _rows(user) == 0, "Abgewiesene Aufrufe duerfen nichts schreiben."
    finally:
        cleanup_workspaces([user])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_patch_writes_only_own_account_and_restart_resets_only_this_tutorial(
    make_auth_headers: AuthFactory,
) -> None:
    me, other = fresh_user_id(), fresh_user_id()
    me_auth, other_auth = make_auth_headers(me), make_auth_headers(other)
    try:
        with TestClient(app) as client:
            done = client.patch(
                _BASE, json={"step_id": "learn-feedback", "state": "done"}, headers=me_auth
            )
            assert done.status_code == 200, done.text
            assert _step(done.json(), "learn-feedback") == "done"
            skipped = client.patch(
                _BASE, json={"step_id": "connect-claude", "state": "skipped"}, headers=me_auth
            )
            assert _step(skipped.json(), "connect-claude") == "skipped"
            welcome = client.patch(_BASE, json={"welcome_seen": True}, headers=me_auth)
            seen_at = welcome.json()["welcome_seen_at"]
            assert seen_at is not None
            # Zweites „gesehen“ (Begruessung erneut abgespielt) behaelt den ersten Zeitpunkt.
            again = client.patch(_BASE, json={"welcome_seen": True}, headers=me_auth)
            assert again.json()["welcome_seen_at"] == seen_at

            # Das andere Konto sieht davon nichts.
            theirs = client.get(_BASE, headers=other_auth).json()
            assert theirs["welcome_seen_at"] is None
            assert _step(theirs, "learn-feedback") == "open"

            # Wieder oeffnen nimmt nur diesen Schritt zurueck.
            reopened = client.patch(
                _BASE, json={"step_id": "connect-claude", "state": "open"}, headers=me_auth
            )
            assert _step(reopened.json(), "connect-claude") == "open"
            assert _step(reopened.json(), "learn-feedback") == "done"

            # Fremde Zeile eines anderen Tutorials: der Neustart laesst sie stehen.
            _db(
                "INSERT INTO tutorial_progress (user_id, tutorial_id, step_id, state) "
                "VALUES ($1, 'other-tutorial', 'x', 'done')",
                me,
            )
            other_done = client.patch(
                _BASE, json={"step_id": "learn-feedback", "state": "done"}, headers=other_auth
            )
            assert other_done.status_code == 200

            restarted = client.post(f"{_BASE}/restart", headers=me_auth)
            assert restarted.status_code == 200, restarted.text
            body = restarted.json()
            assert body["restarted_at"] is not None
            assert body["welcome_seen_at"] == seen_at, (
                "Neustart setzt die Begruessung nicht zurueck."
            )
            assert _step(body, "learn-feedback") == "open"
            assert _step(body, "builder-ready") == "done"

        left = _db("SELECT tutorial_id FROM tutorial_progress WHERE user_id = $1", me)
        assert [r["tutorial_id"] for r in left] == ["other-tutorial"]
        assert _db(
            "SELECT 1 FROM tutorial_progress WHERE user_id = $1 AND step_id = 'learn-feedback'",
            other,
        ), "Der Neustart eines Kontos darf ein anderes nicht beruehren."
    finally:
        _db("DELETE FROM tutorial_progress WHERE user_id = ANY($1::uuid[])", [me, other])
        _db("DELETE FROM tutorial_state WHERE user_id = ANY($1::uuid[])", [me, other])
        cleanup_workspaces([me, other])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_automatic_steps_are_derived_from_workspace_data(make_auth_headers: AuthFactory) -> None:
    """Erster MCP-Abruf und eigener Agent — abgeleitet, nicht gespeichert."""
    me, stranger = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(me)
    foreign_ws = setup_workspace(stranger)
    auth = make_auth_headers(me)
    query = {"workspace_id": str(ws)}
    try:
        with TestClient(app) as client:
            prefix = f"/v1/workspaces/{ws}"
            managed = client.post(f"{prefix}/agents", json={"name": "Verwaltet"}, headers=auth)
            own = client.post(f"{prefix}/agents", json={"name": "Eigener"}, headers=auth)
            assert managed.status_code == 201 and own.status_code == 201, own.text
            managed_id, own_id = managed.json()["id"], own.json()["id"]
            # Der Builder ist ein verwalteter Agent; hier per SQL nachgestellt.
            _db("UPDATE agent SET is_managed = true WHERE id = $1", UUID(managed_id))

            # Ohne Workspace: nichts ableitbar, nur der Startvorsprung.
            plain = client.get(_BASE, headers=auth).json()
            assert _step(plain, "connect-claude") == "open"

            # Abruf eines fremden Nutzers im selben Workspace zaehlt nicht.
            _usage(ws, stranger, own_id, datetime.now(UTC))
            assert (
                _step(client.get(_BASE, params=query, headers=auth).json(), "connect-claude")
                == "open"
            )

            # Erster eigener Abruf ueber den verwalteten Agenten: Schritt 2, nicht 3.
            _usage(ws, me, managed_id, datetime.now(UTC) - timedelta(minutes=1))
            body = client.get(_BASE, params=query, headers=auth).json()
            assert _step(body, "connect-claude") == "done"
            assert _step(body, "build-own-agent") == "open"

            # Abruf ueber den eigenen, nicht verwalteten Agenten: Schritt 3.
            _usage(ws, me, own_id, datetime.now(UTC))
            body = client.get(_BASE, params=query, headers=auth).json()
            assert _step(body, "build-own-agent") == "done"
            listed = client.get("/v1/me/tutorials", params=query, headers=auth).json()
            assert _step(listed[0], "build-own-agent") == "done"

            # Neustart: Ereignisse davor zaehlen nicht mehr ...
            restarted = client.post(f"{_BASE}/restart", params=query, headers=auth).json()
            assert _step(restarted, "connect-claude") == "open"
            assert _step(restarted, "build-own-agent") == "open"
            # ... ein neues danach schon.
            _usage(ws, me, managed_id, datetime.now(UTC) + timedelta(seconds=1))
            body = client.get(_BASE, params=query, headers=auth).json()
            assert _step(body, "connect-claude") == "done"

            # Fremder und unbekannter Workspace: derselbe 404, ohne Schreibwirkung.
            before = _rows(me)
            for target in (foreign_ws, uuid4()):
                for method, path, payload in (
                    ("GET", _BASE, None),
                    ("PATCH", _BASE, {"welcome_seen": True}),
                    ("POST", f"{_BASE}/restart", None),
                ):
                    res = client.request(
                        method,
                        path,
                        params={"workspace_id": str(target)},
                        json=payload,
                        headers=auth,
                    )
                    assert res.status_code == 404, (method, res.text)
                    assert res.json()["reason"] == "workspace_not_found"
            assert _rows(me) == before
    finally:
        _db("DELETE FROM usage_event WHERE workspace_id = ANY($1::uuid[])", [ws, foreign_ws])
        _db("DELETE FROM tutorial_progress WHERE user_id = $1", me)
        _db("DELETE FROM tutorial_state WHERE user_id = $1", me)
        cleanup_workspaces([me, stranger])


_AGENT_TUTORIAL = TutorialDefinition.model_validate(
    {
        "id": "agent-test",
        "audience": "everyone",
        "steps": [{"id": "create-agent", "type": "agent_created"}],
    }
)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_agent_created_counts_only_own_unmanaged_agents_since_restart(
    make_auth_headers: AuthFactory,
) -> None:
    """AK „Agent angelegt“: `agent_created` gegen die echte `agent`-Tabelle.

    Der ausgelieferte Katalog nutzt den Typ (noch) nicht, deshalb laeuft die
    Route hier mit einem Test-Katalog — Ableitung, Mandanten-Scope und
    `since`-Filter sind dieselben wie im Betrieb.
    """

    def _service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> TutorialService:
        return TutorialService(
            PgTutorialRepository(pool), catalog={_AGENT_TUTORIAL.id: _AGENT_TUTORIAL}
        )

    me, stranger = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(me)
    auth = make_auth_headers(me)
    query = {"workspace_id": str(ws)}
    base = f"/v1/me/tutorials/{_AGENT_TUTORIAL.id}"
    app.dependency_overrides[get_tutorial_service] = _service
    try:
        with TestClient(app) as client:
            prefix = f"/v1/workspaces/{ws}"

            def _create(name: str) -> UUID:
                res = client.post(f"{prefix}/agents", json={"name": name}, headers=auth)
                assert res.status_code == 201, res.text
                return UUID(res.json()["id"])

            def _state() -> str:
                res = client.get(base, params=query, headers=auth)
                assert res.status_code == 200, res.text
                return _step(res.json(), "create-agent")

            assert _state() == "open"

            # Verwalteter Agent (wie der Builder) zaehlt nicht.
            managed = _create("[Tut] Verwaltet")
            _db("UPDATE agent SET is_managed = true WHERE id = $1", managed)
            assert _state() == "open"

            # Agent eines anderen Owners im selben Workspace zaehlt nicht.
            foreign = _create("[Tut] Fremd")
            _db("UPDATE agent SET owner_id = $1 WHERE id = $2", stranger, foreign)
            assert _state() == "open"

            # Eigener, nicht verwalteter Agent zaehlt.
            _create("[Tut] Eigener")
            assert _state() == "done"

            # Nach dem Neustart zaehlt der vorher angelegte Agent nicht mehr ...
            restarted = client.post(f"{base}/restart", params=query, headers=auth)
            assert restarted.status_code == 200, restarted.text
            assert _step(restarted.json(), "create-agent") == "open"
            assert _state() == "open"
            # ... ein danach angelegter schon.
            _create("[Tut] Nach Neustart")
            assert _state() == "done"
    finally:
        app.dependency_overrides.pop(get_tutorial_service, None)
        _db("DELETE FROM tutorial_progress WHERE user_id = $1", me)
        _db("DELETE FROM tutorial_state WHERE user_id = $1", me)
        cleanup_workspaces([me, stranger])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_machine_token_cannot_use_tutorial_routes(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    human = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            _agent, token = agent_token(client, f"/v1/workspaces/{ws}", "[Tut] Agent", {}, human)
            for method, path, body in (
                ("GET", "/v1/me/tutorials", None),
                ("GET", _BASE, None),
                ("PATCH", _BASE, {"welcome_seen": True}),
                ("POST", f"{_BASE}/restart", None),
            ):
                res = client.request(method, path, json=body, headers=token)
                assert res.status_code == 403, (method, path, res.text)
                assert res.json()["reason"] == "account_route_requires_human"
        assert _rows(owner) == 0
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_export_contains_and_purge_removes_progress(make_auth_headers: AuthFactory) -> None:
    user = fresh_user_id()
    setup_workspace(user)
    auth = make_auth_headers(user)
    try:
        with TestClient(app) as client:
            client.patch(_BASE, json={"welcome_seen": True}, headers=auth)
            client.patch(_BASE, json={"step_id": "learn-feedback", "state": "done"}, headers=auth)
            export = client.get("/v1/gdpr/export", headers=auth)
            assert export.status_code == 200, export.text
            tutorials = export.json()["tutorials"]
            assert [s["tutorial_id"] for s in tutorials["states"]] == [_TUTORIAL]
            assert [(p["step_id"], p["state"]) for p in tutorials["progress"]] == [
                ("learn-feedback", "done")
            ]
        assert _rows(user) == 2

        async def _purge() -> None:
            from who2be_api.repositories.account_repository import PgAccountPurgeRepository

            conn = await asyncpg.connect(get_settings().database_url)
            try:
                await PgAccountPurgeRepository(conn).purge_account_data(user)
            finally:
                await conn.close()

        asyncio.run(_purge())
        assert _rows(user) == 0
    finally:
        cleanup_workspaces([user])
