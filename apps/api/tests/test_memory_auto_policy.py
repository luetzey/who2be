"""Freigabematrix Art x Herkunft und Speicherpfad 2.0 (ADR-0053 4, Paket C2a).

Kritische Invarianten:
- Tabellentest ueber JEDE Zelle der Matrix 4.2 (auto an/aus x Art x Herkunft
  x Kanal): nur `user_fact` (ohne Verhaltenswirkung) x `user_stated` wird bei
  eingeschalteter Zelle im Kanal `agent` aktiv; eine eingeschaltete
  Nie-Zelle bleibt `pending`.
- Default „alles aus" (M3): ein `auto`-Agent wirkt wie `suggest`.
- `origin` ist Pflicht, kind x scope wird geprueft, lesson-Merge laesst den
  Status des Treffers unveraendert, beide Obergrenzen greifen nahe der Grenze.
- `PUT /memory-auto-policy` nur `admin` UND eingeloggter Mensch; jede
  geaenderte Zelle steht im `audit_log`.
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.services.memory_service import decide_memory_status, matrix_row
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import (
    MEMORY_MAX_PER_AGENT,
    MEMORY_MAX_PER_USER,
    MemoryCategory,
    MemoryKind,
    MemoryMode,
    MemoryOrigin,
    MemorySource,
    MemoryStatus,
)
from who2be_models.memory import (
    MEMORY_AUTO_SWITCHABLE_CELLS,
    MEMORY_MAX_NOTES_PER_AGENT,
    MemoryAutoCell,
    MemoryAutoPolicy,
    MemoryAutoRow,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_CELL = {"row": "user_fact", "origin": "user_stated"}
_ALL_CELLS = [
    MemoryAutoCell(row=row, origin=origin)
    for row, origin in itertools.product(MemoryAutoRow, MemoryOrigin)
]


# --------------------------------------------------------------- Tabellentest


def _expected(
    mode: MemoryMode, source: MemorySource, row: MemoryAutoRow, origin: MemoryOrigin, on: bool
) -> tuple[MemoryStatus, bool]:
    """Die Matrix 4.2 als Tabelle, unabhaengig von der Implementierung notiert."""
    if source in (MemorySource.human, MemorySource.import_):
        if row in (MemoryAutoRow.lesson, MemoryAutoRow.proposal):
            return MemoryStatus.pending, False
        return MemoryStatus.active, False
    if (
        mode == MemoryMode.auto
        and on
        and row == MemoryAutoRow.user_fact
        and origin == MemoryOrigin.user_stated
    ):
        return MemoryStatus.active, True
    return MemoryStatus.pending, False


@pytest.mark.parametrize("mode", [MemoryMode.suggest, MemoryMode.auto])
@pytest.mark.parametrize("source", list(MemorySource))
@pytest.mark.parametrize("row", list(MemoryAutoRow))
@pytest.mark.parametrize("origin", list(MemoryOrigin))
@pytest.mark.parametrize("on", [False, True])
def test_matrix_every_cell(
    mode: MemoryMode, source: MemorySource, row: MemoryAutoRow, origin: MemoryOrigin, on: bool
) -> None:
    """Jede Zelle: `on` schaltet die Zelle selbst ein — auch Nie-Zellen."""
    policy = MemoryAutoPolicy(enabled_cells=[MemoryAutoCell(row=row, origin=origin)] if on else [])
    decision = decide_memory_status(mode=mode, source=source, row=row, origin=origin, policy=policy)
    status, auto_activated = _expected(mode, source, row, origin, on)
    assert (decision.status, decision.auto_activated) == (status, auto_activated)
    assert decision.confirmed == (source != MemorySource.agent and status == MemoryStatus.active)


def test_all_cells_switched_on_still_only_one_activates() -> None:
    """Alle Zellen eingeschaltet: genau eine wirkt, der Rest bleibt pending."""
    policy = MemoryAutoPolicy(enabled_cells=_ALL_CELLS)
    assert policy.effective() == MEMORY_AUTO_SWITCHABLE_CELLS
    active = [
        cell
        for cell in _ALL_CELLS
        if decide_memory_status(
            mode=MemoryMode.auto,
            source=MemorySource.agent,
            row=cell.row,
            origin=cell.origin,
            policy=policy,
        ).status
        == MemoryStatus.active
    ]
    assert active == [MemoryAutoCell(row=MemoryAutoRow.user_fact, origin=MemoryOrigin.user_stated)]


@pytest.mark.parametrize(
    ("kind", "category", "row"),
    [
        (MemoryKind.user_fact, MemoryCategory.preference, MemoryAutoRow.user_fact),
        (MemoryKind.user_fact, MemoryCategory.general, MemoryAutoRow.user_fact),
        (MemoryKind.user_fact, MemoryCategory.instruction, MemoryAutoRow.user_fact_instruction),
        (MemoryKind.agent_note, MemoryCategory.preference, MemoryAutoRow.agent_note),
        (MemoryKind.lesson, MemoryCategory.instruction, MemoryAutoRow.lesson),
    ],
)
def test_matrix_row(kind: MemoryKind, category: MemoryCategory, row: MemoryAutoRow) -> None:
    assert matrix_row(kind, category) == row


# ------------------------------------------------------------- Integrations-Helfer


def _sql(query: str, *args: Any) -> Any:
    """Fuehrt eine Abfrage als Owner aus (Fixtures, Statuswechsel, Pruefung)."""

    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetch(query, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _add_editor(workspace_id: UUID, user_id: UUID) -> None:
    _sql(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'editor') "
        "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
        workspace_id,
        user_id,
    )


def _fill(
    workspace_id: UUID,
    count: int,
    *,
    agent_id: str | None,
    kind: str = "user_fact",
    scope: str = "agent",
    subject_user_id: UUID | None = None,
) -> None:
    """Legt `count` Fuelleintraege an — md5-Fakten, damit kein Dedup anschlaegt."""
    _sql(
        "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, fact, "
        " category, importance, kind, scope, origin, source, subject_user_id) "
        "SELECT $1, $2::uuid, $2::uuid, 'pending', md5($3 || i::text), 'general', 5, $4, $5, "
        "       'user_stated', 'agent', $6 "
        "FROM generate_series(1, $7) AS i",
        workspace_id,
        agent_id,
        f"{kind}-{scope}-",
        kind,
        scope,
        subject_user_id,
        count,
    )


def _save(client: TestClient, prefix: str, headers: dict[str, str], fact: str, **body: Any) -> Any:
    payload: dict[str, Any] = {
        "fact": fact,
        "category": "preference",
        "importance": 7,
        "origin": "user_stated",
    }
    payload.update(body)
    return client.post(f"{prefix}/agent-memories", json=payload, headers=headers)


# ----------------------------------------------------------------- Integration


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_auto_policy_endpoint_gates_and_audit(make_auth_headers: AuthFactory) -> None:
    """GET/PUT nur admin + Mensch; Nie-Zellen ignoriert; jede Aenderung im audit_log."""
    owner = fresh_user_id()
    editor = fresh_user_id()
    ws = setup_workspace(owner)
    _add_editor(ws, editor)
    auth = make_auth_headers(owner)
    editor_auth = make_auth_headers(editor)
    prefix = f"/v1/workspaces/{ws}"
    url = f"{prefix}/memory-auto-policy"
    try:
        with TestClient(app) as client:
            _, agent_tok = agent_token(client, prefix, "p-gate", {"memory_mode": "auto"}, auth)

            initial = client.get(url, headers=auth)
            assert initial.status_code == 200, initial.text
            assert initial.json() == {"enabled_cells": [], "switchable_cells": [_CELL]}

            body = {"enabled_cells": [_CELL]}
            assert client.get(url, headers=editor_auth).status_code == 403
            assert client.put(url, json=body, headers=editor_auth).status_code == 403
            assert client.get(url, headers=agent_tok).status_code == 403
            assert client.put(url, json=body, headers=agent_tok).status_code == 403
            assert (
                _sql(
                    "SELECT 1 FROM audit_log WHERE workspace_id = $1 "
                    "AND action LIKE 'memory.auto_policy.%'",
                    ws,
                )
                == []
            )

            # Einschalten + eine Nie-Zelle: die Nie-Zelle faellt heraus.
            never = {"row": "user_fact", "origin": "inferred"}
            on = client.put(url, json={"enabled_cells": [_CELL, never]}, headers=auth)
            assert on.status_code == 200, on.text
            assert on.json()["enabled_cells"] == [_CELL]
            assert client.get(url, headers=auth).json()["enabled_cells"] == [_CELL]

            # Gleiche Einstellung erneut: keine weitere Audit-Zeile.
            assert client.put(url, json=body, headers=auth).status_code == 200
            assert client.put(url, json={"enabled_cells": []}, headers=auth).status_code == 200

            rows = _sql(
                "SELECT actor_id, action, target, detail FROM audit_log WHERE workspace_id = $1 "
                "AND action LIKE 'memory.auto_policy.%' ORDER BY created_at",
                ws,
            )
            assert [(r["actor_id"], r["action"], r["target"]) for r in rows] == [
                (owner, "memory.auto_policy.enabled", "user_fact:user_stated"),
                (owner, "memory.auto_policy.disabled", "user_fact:user_stated"),
            ]
    finally:
        cleanup_workspaces([owner, editor])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_save_path_matrix_end_to_end(make_auth_headers: AuthFactory) -> None:
    """Default aus → pending; eingeschaltet → nur user_fact x user_stated aktiv,
    unbestaetigt, mit Verfall und Ereignis `auto_activated`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, auto = agent_token(client, prefix, "p-auto", {"memory_mode": "auto"}, auth)
            _, sug = agent_token(client, prefix, "p-sug", {"memory_mode": "suggest"}, auth)

            off = _save(client, prefix, auto, "Nutzer faehrt im Sommer gern Fahrrad")
            assert off.status_code == 201, off.text
            assert (off.json()["status"], off.json()["auto_activated"]) == ("pending", False)
            assert off.json()["source"] == "agent"
            assert off.json()["origin"] == "user_stated"
            assert off.json()["expires_at"] is None

            put = client.put(
                f"{prefix}/memory-auto-policy",
                json={"enabled_cells": [_CELL, {"row": "agent_note", "origin": "user_stated"}]},
                headers=auth,
            )
            assert put.status_code == 200, put.text

            on = _save(client, prefix, auto, "Nutzer trinkt morgens gruenen Tee")
            assert on.status_code == 201, on.text
            assert (on.json()["status"], on.json()["auto_activated"]) == ("active", True)
            assert on.json()["confirmed_at"] is None
            row = _sql(
                "SELECT expires_at - created_at AS ttl FROM agent_memory WHERE id = $1",
                UUID(on.json()["id"]),
            )[0]
            assert row["ttl"].days == 30
            events = _sql(
                "SELECT event, actor_kind FROM agent_memory_event WHERE memory_id = $1 "
                "ORDER BY created_at, event",
                UUID(on.json()["id"]),
            )
            assert {(e["event"], e["actor_kind"]) for e in events} == {
                ("created", "agent"),
                ("auto_activated", "system"),
            }

            # Nie-Zellen bleiben pending, auch wenn eingeschaltet.
            for fact, extra in (
                ("Nutzer will Antworten immer als Liste", {"category": "instruction"}),
                ("Nutzer wohnt vermutlich in Hamburg", {"origin": "inferred"}),
                ("Laut Webseite ist der Nutzer Architekt", {"origin": "external_content"}),
                ("Repo nutzt uv statt pip", {"kind": "agent_note"}),
                ("Bei Rueckfragen erst das Board lesen", {"kind": "lesson"}),
            ):
                res = _save(client, prefix, auto, fact, **extra)
                assert res.status_code == 201, (fact, res.text)
                assert (res.json()["status"], res.json()["auto_activated"]) == (
                    "pending",
                    False,
                ), fact

            # suggest bleibt Schleuse, auch mit eingeschalteter Zelle.
            sug_res = _save(client, prefix, sug, "Nutzer liest gern Science-Fiction")
            assert sug_res.json()["status"] == "pending"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_origin_required_and_kind_scope(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, sug = agent_token(client, prefix, "p-orig", {"memory_mode": "suggest"}, auth)
            missing = client.post(
                f"{prefix}/agent-memories",
                json={"fact": "Nutzer mag Jazz", "importance": 7},
                headers=sug,
            )
            assert missing.status_code == 422
            assert missing.json()["reason"] == "memory_origin_required"
            legacy = _save(client, prefix, sug, "Nutzer mag Jazz", origin="legacy_unknown")
            assert legacy.status_code == 422
            assert legacy.json()["reason"] == "memory_origin_required"

            for kind in ("agent_note", "lesson"):
                bad = _save(client, prefix, sug, "Nutzer mag Jazz", kind=kind, scope="user")
                assert bad.status_code == 422
                assert bad.json()["reason"] == "memory_kind_scope_invalid"
                assert bad.json()["params"] == {"kind": kind, "scope": "user"}

            # `source` ist kein Eingabefeld (der Server setzt den Kanal).
            forged = _save(client, prefix, sug, "Nutzer mag Jazz", source="human")
            assert forged.status_code == 422

            user_fact = _save(client, prefix, sug, "Nutzer mag Jazz", scope="user")
            assert user_fact.status_code == 201, user_fact.text
            assert user_fact.json()["agent_id"] is None
            assert user_fact.json()["subject_user_id"] == str(owner)
            assert user_fact.json()["scope"] == "user"
            # Dublette im Nutzergedaechtnis.
            dup = _save(client, prefix, sug, "Nutzer mag Jazz", scope="user")
            assert dup.status_code == 409
            assert dup.json()["reason"] == "memory_duplicate"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_lesson_merge_keeps_status_and_user_fact_duplicate(make_auth_headers: AuthFactory) -> None:
    """lesson-Wiederholung → 200 `merged_into`, Status bleibt (pending/rejected/
    converted); eine user_fact-Dublette bleibt 409."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, sug = agent_token(client, prefix, "p-lesson", {"memory_mode": "suggest"}, auth)
            lessons = {
                "pending": "Vor dem Push immer die Migrationsnummer pruefen",
                "rejected": "Deploy-Schritte nie ohne Rueckfrage starten",
                "converted": "Bei leeren Ergebnissen die Suchbegriffe variieren",
            }
            ids: dict[str, str] = {}
            for status_name, fact in lessons.items():
                res = _save(client, prefix, sug, fact, kind="lesson", category="instruction")
                assert res.status_code == 201, res.text
                ids[status_name] = res.json()["id"]
            _sql("UPDATE agent_memory SET status = 'rejected' WHERE id = $1", UUID(ids["rejected"]))
            _sql(
                "UPDATE agent_memory SET status = 'converted', "
                "converted_case_id = gen_random_uuid() WHERE id = $1",
                UUID(ids["converted"]),
            )

            for status_name, fact in lessons.items():
                again = _save(client, prefix, sug, fact, kind="lesson", category="instruction")
                assert again.status_code == 200, again.text
                assert again.json()["merged_into"] == ids[status_name]
                assert again.json()["id"] == ids[status_name]
                assert again.json()["status"] == status_name
                assert again.json()["occurrence_count"] == 2

            assert (
                _sql(
                    "SELECT count(*) AS n FROM agent_memory "
                    "WHERE workspace_id = $1 AND kind = 'lesson'",
                    ws,
                )[0]["n"]
                == 3
            )
            merged = _sql(
                "SELECT count(*) AS n FROM agent_memory_event WHERE workspace_id = $1 "
                "AND event = 'merged'",
                ws,
            )[0]["n"]
            assert merged == 3

            # Kanaele getrennt: der gleiche Text als user_fact ist kein Merge.
            as_fact = _save(client, prefix, sug, lessons["pending"])
            assert as_fact.status_code == 201, as_fact.text
            dup = _save(client, prefix, sug, lessons["pending"])
            assert dup.status_code == 409
            assert dup.json()["reason"] == "memory_duplicate"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_caps_near_the_limit(make_auth_headers: AuthFactory) -> None:
    """agent_note 200 je Agent, Agentengrenze 500 ohne Notizen, Nutzer 500."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, sug = agent_token(client, prefix, "p-cap", {"memory_mode": "suggest"}, auth)

            # Notizen: eine unter der Grenze passt noch, dann 409.
            _fill(ws, MEMORY_MAX_NOTES_PER_AGENT - 1, agent_id=agent_id, kind="agent_note")
            last = _save(client, prefix, sug, "Build laeuft mit uv sync", kind="agent_note")
            assert last.status_code == 201, last.text
            full = _save(client, prefix, sug, "Tests laufen mit pytest -q", kind="agent_note")
            assert full.status_code == 409
            assert full.json()["reason"] == "memory_note_cap_reached"
            assert full.json()["params"] == {"maximum": MEMORY_MAX_NOTES_PER_AGENT}

            # Notizen zaehlen nicht gegen die Agentengrenze.
            _fill(ws, MEMORY_MAX_PER_AGENT - 1, agent_id=agent_id)
            fits = _save(client, prefix, sug, "Nutzer spielt Schach im Verein")
            assert fits.status_code == 201, fits.text
            capped = _save(client, prefix, sug, "Nutzer sammelt alte Landkarten")
            assert capped.status_code == 409
            assert capped.json()["reason"] == "memory_cap_reached"
            assert capped.json()["params"] == {"maximum": MEMORY_MAX_PER_AGENT}

            # Nutzergedaechtnis: eigene Grenze, scope='user' in params.
            _fill(ws, MEMORY_MAX_PER_USER - 1, agent_id=None, scope="user", subject_user_id=owner)
            user_ok = _save(client, prefix, sug, "Nutzer hat zwei Katzen", scope="user")
            assert user_ok.status_code == 201, user_ok.text
            user_full = _save(client, prefix, sug, "Nutzer segelt am Wochenende", scope="user")
            assert user_full.status_code == 409
            assert user_full.json()["reason"] == "memory_cap_reached"
            assert user_full.json()["params"] == {"maximum": MEMORY_MAX_PER_USER, "scope": "user"}
    finally:
        cleanup_workspaces([owner])
