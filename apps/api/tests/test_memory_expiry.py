"""Secret-Scan, Ratenbegrenzung und Verfall des Gedaechtnisses (ADR-0053 3.1.3, 7.1, C2b).

Kritische Invarianten:
- **Verfall nur fuer Unbestaetigtes:** `pending` und automatisch aktivierte
  `active` ohne `confirmed_at` verfallen nach `expires_at`; bestaetigte
  Eintraege nie, auch nicht mit einem stehengebliebenen `expires_at`;
  Lernvorschlaege nie (DB-CHECK 0091).
- **Abrufe verlaengern nichts:** ein ueber den Abrufpfad ausgelieferter
  Eintrag verfaellt trotzdem.
- **Spur und Dublettenbasis:** je Eintrag ein Ereignis `expired`
  (`actor_kind='system'`); geloescht wird nichts, ein erneut eingereichter
  gleicher Fakt bleibt `memory_duplicate`.
- **Bestaetigung beendet den Verfall:** Freigabe in der Triage setzt
  `confirmed_at` und `expires_at = NULL`.
- **Secret-Scan:** ein synthetisches Geheimnis wird mit
  `memory_guard_rejected` abgewiesen — auch bei ausgeschaltetem
  Injection-Waechter und im Feld `context`; Alltagsfakten mit dem Wort
  „Passwort“ bleiben speicherbar.
- **Ratenbegrenzung:** `save_memory` verbraucht das agentenbezogene
  Schreib-Ratenlimit (`write_rate_limited`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.memory_expiry import expire_unconfirmed_memories
from who2be_api.core.rate_limit import token_rate_limiter
from who2be_api.main import app
from who2be_api.services.memory_service import _secret_rejection
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

_CELL = {"row": "user_fact", "origin": "user_stated"}

# Synthetisch und bewusst in keinem Token-Format eines Anbieters.
_SECRET_FACT = "Das Passwort des Nutzers lautet: Zx9-beispiel-wert-123"


# ------------------------------------------------------------------ Helfer


def _sql(query: str, *args: Any) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(query, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _expire() -> int:
    """Der Verfallsjob, wie ihn die CLI faehrt (Owner-Connection, echte Zeit)."""

    async def _run() -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await expire_unconfirmed_memories(conn)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _save(client: TestClient, prefix: str, headers: dict[str, str], fact: str, **body: Any) -> Any:
    payload: dict[str, Any] = {
        "fact": fact,
        "category": "preference",
        "importance": 7,
        "origin": "user_stated",
    }
    payload.update(body)
    return client.post(f"{prefix}/agent-memories", json=payload, headers=headers)


def _make_due(memory_id: str) -> None:
    """Rueckt `expires_at` in die Vergangenheit, ohne sonst etwas anzufassen."""
    _sql(
        "UPDATE agent_memory SET expires_at = now() - interval '1 minute' WHERE id = $1",
        UUID(memory_id),
    )


def _status(memory_id: str) -> str:
    return str(_sql("SELECT status FROM agent_memory WHERE id = $1", UUID(memory_id))[0]["status"])


# ------------------------------------------------------------ Secret-Scan (Einheit)


@pytest.mark.parametrize(
    "text",
    [
        _SECRET_FACT,
        "api_key=beispiel0123456789",
        "Zugang zur Datenbank: postgres://nutzer:beispielwert@db.example.invalid/app",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "Header: Bearer abcdefghijklmnopqrstuvwxyz012345",
    ],
)
def test_secret_scan_flags_credentials(text: str) -> None:
    assert _secret_rejection(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "Nutzer nutzt einen Passwortmanager",
        "Nutzer moechte API-Keys immer ueber die Einstellungen rotieren",
        "Nutzer arbeitet mit Tokens als Abrechnungseinheit",
        "Nutzer bevorzugt https://example.invalid/docs als Quelle",
        "Das Passwort des Nutzers ist sicher verwahrt",
        "Der Token-Verbrauch des Nutzers ist 2026 gestiegen",
    ],
)
def test_secret_scan_leaves_everyday_facts(text: str) -> None:
    assert _secret_rejection(text) is None


# --------------------------------------------------------------- Integration


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_expiry_hits_only_unconfirmed(make_auth_headers: AuthFactory) -> None:
    """Fixture bestaetigt/unbestaetigt/abgerufen: nur Unbestaetigtes verfaellt,
    der abgerufene Eintrag trotzdem; Ereignis geschrieben; Dublettenbasis bleibt."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, sug = agent_token(client, prefix, "x-sug", {"memory_mode": "suggest"}, auth)
            _, auto = agent_token(client, prefix, "x-auto", {"memory_mode": "auto"}, auth)
            put = client.put(
                f"{prefix}/memory-auto-policy", json={"enabled_cells": [_CELL]}, headers=auth
            )
            assert put.status_code == 200, put.text

            # Unbestaetigt, pending: der Speicherpfad setzt den Verfall.
            pending = _save(client, prefix, sug, "Nutzer faehrt im Winter Ski").json()
            assert pending["status"] == "pending"
            assert pending["expires_at"] is not None
            # Bestaetigt: Freigabe in der Triage beendet den Verfall.
            confirmed = _save(client, prefix, sug, "Nutzer spielt Cello im Orchester").json()
            approved = client.post(
                f"{prefix}/agents/{agent_id}/memories/{confirmed['id']}/triage",
                json={"action": "approve"},
                headers=auth,
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "active"
            assert approved.json()["confirmed_at"] is not None
            assert approved.json()["confirmed_by"] == str(owner)
            assert approved.json()["expires_at"] is None
            # Unbestaetigt aktiv und ueber den Abrufpfad ausgeliefert.
            retrieved = _save(client, prefix, auto, "Nutzer trinkt Kaffee schwarz").json()
            assert (retrieved["status"], retrieved["auto_activated"]) == ("active", True)
            hits = client.get(f"{prefix}/agent-memories", headers=auto)
            assert hits.status_code == 200, hits.text
            assert retrieved["id"] in [hit["id"] for hit in hits.json()]
            # Lernvorschlag: verfaellt nie.
            lesson = _save(
                client, prefix, sug, "Vor dem Push die Tests lokal starten", kind="lesson"
            ).json()
            assert lesson["expires_at"] is None
            # Noch nicht faellig.
            later = _save(client, prefix, sug, "Nutzer liest gern Krimis").json()

            for memory in (pending, retrieved):
                _make_due(memory["id"])
            # Bestaetigt, aber mit stehengebliebenem `expires_at` (Altbestand
            # oder kuenftiger Schreibpfad): bleibt trotzdem aktiv.
            _make_due(confirmed["id"])
            # Lernvorschlag mit (kuenstlich) faelligem Termin: bleibt pending.
            _make_due(lesson["id"])
            bumped = _sql(
                "SELECT retrieval_count, last_retrieved_at FROM agent_memory WHERE id = $1",
                UUID(retrieved["id"]),
            )[0]
            assert bumped["retrieval_count"] >= 1
            assert bumped["last_retrieved_at"] is not None

            assert _expire() >= 2
            assert _status(pending["id"]) == "expired"
            assert _status(retrieved["id"]) == "expired"
            assert _status(confirmed["id"]) == "active"
            assert _status(lesson["id"]) == "pending"
            assert _status(later["id"]) == "pending"

            events = _sql(
                "SELECT memory_id, actor_kind, actor_id, before->>'status' AS before, "
                "       after->>'status' AS after FROM agent_memory_event "
                "WHERE workspace_id = $1 AND event = 'expired' ORDER BY memory_id",
                ws,
            )
            assert sorted(
                (str(e["memory_id"]), e["actor_kind"], e["actor_id"], e["before"], e["after"])
                for e in events
            ) == sorted(
                [
                    (pending["id"], "system", None, "pending", "expired"),
                    (retrieved["id"], "system", None, "active", "expired"),
                ]
            )

            # Abgelaufen ist nicht abrufbar ...
            hits_after = client.get(f"{prefix}/agent-memories", headers=auto).json()
            assert retrieved["id"] not in [hit["id"] for hit in hits_after]
            # ... bleibt aber Dublettenbasis.
            dup = _save(client, prefix, sug, "Nutzer faehrt im Winter Ski")
            assert dup.status_code == 409, dup.text
            assert dup.json()["reason"] == "memory_duplicate"

            # Idempotent: ein zweiter Lauf trifft in diesem Workspace nichts mehr.
            _expire()
            again = _sql(
                "SELECT count(*) AS n FROM agent_memory_event "
                "WHERE workspace_id = $1 AND event = 'expired'",
                ws,
            )[0]["n"]
            assert again == 2
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_secret_scan_rejects_even_with_guard_off(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, sug = agent_token(client, prefix, "x-secret", {"memory_mode": "suggest"}, auth)
            off = client.put(f"{prefix}/memory-guard", json={"mode": "off"}, headers=auth)
            assert off.status_code == 200, off.text

            in_fact = _save(client, prefix, sug, _SECRET_FACT)
            assert in_fact.status_code == 422, in_fact.text
            assert in_fact.json()["reason"] == "memory_guard_rejected"
            # Der Treffer wird nicht ins Fehlerdetail gespiegelt.
            assert "Zx9-beispiel-wert-123" not in in_fact.text

            in_context = _save(
                client, prefix, sug, "Nutzer nutzt einen Passwortmanager", context=_SECRET_FACT
            )
            assert in_context.status_code == 422, in_context.text
            assert in_context.json()["reason"] == "memory_guard_rejected"

            harmless = _save(client, prefix, sug, "Nutzer nutzt einen Passwortmanager")
            assert harmless.status_code == 201, harmless.text

            stored = _sql(
                "SELECT count(*) AS n FROM agent_memory WHERE workspace_id = $1 "
                "AND (fact LIKE '%Zx9-beispiel%' OR context LIKE '%Zx9-beispiel%')",
                ws,
            )[0]["n"]
            assert stored == 0
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_save_memory_consumes_agent_write_rate(make_auth_headers: AuthFactory) -> None:
    """`write_rate_limit=1`: der zweite Speichervorgang im Fenster ist 429."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    token_rate_limiter.reset()
    try:
        with TestClient(app) as client:
            _, sug = agent_token(
                client,
                prefix,
                "x-rate",
                {"memory_mode": "suggest", "write_rate_limit": 1},
                auth,
            )
            first = _save(client, prefix, sug, "Nutzer wandert gern in den Alpen")
            assert first.status_code == 201, first.text
            second = _save(client, prefix, sug, "Nutzer kocht gern indisch")
            assert second.status_code == 429, second.text
            assert second.json()["reason"] == "write_rate_limited"
            assert second.json()["params"] == {"limit": 1}
    finally:
        token_rate_limiter.reset()
        cleanup_workspaces([owner])
