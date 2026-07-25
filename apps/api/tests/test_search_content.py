"""Integrationstests der Passage-Suche (ADR-0046).

Belegt den ganzen Weg: die Aktivierung einer Version materialisiert Passagen,
`GET /search/content` findet sie, der Read-Scope greift, und das Zuruecknehmen
der Aktivierung raeumt sie wieder weg.

Der fachliche Kern ist der Groessenvergleich in
`test_passage_is_smaller_than_the_full_aggregate`: das Passage-Retrieval soll
den Agenten-Kontext entlasten, nicht nur anders ranken.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _para(block_id: str, text: str) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _heading(block_id: str, text: str, level: int = 1) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": level},
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _resource_body(name: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "content": {"description": "Handbuch", "blocks": blocks, "tags": []}}


def _activate(client: TestClient, base: str, entity_id: str, auth: dict[str, str]) -> None:
    for to in ("review", "active"):
        r = client.post(f"{base}/{entity_id}/versions/1/transition", json={"to": to}, headers=auth)
        assert r.status_code in (200, 201), r.text


@pytest.mark.integration
def test_activation_materializes_passages_and_search_finds_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    rbase = f"{prefix}/resources"

    try:
        with TestClient(app) as client:
            blocks = [
                _heading("h-annahme", "Annahme der Reklamation"),
                _para("p1", "Beschwerde vollstaendig aufnehmen und protokollieren."),
                _heading("h-eskalation", "Eskalation an die Teamleitung"),
                _para("p2", "Ab Stufe drei uebernimmt die Teamleitung den Vorgang."),
            ]
            rid = client.post(rbase, json=_resource_body("Handbuch", blocks), headers=auth).json()[
                "id"
            ]

            # Vor der Aktivierung ist nichts auffindbar (nur `active` zaehlt).
            pre = client.get(f"{prefix}/search/content", params={"q": "Teamleitung"}, headers=auth)
            assert pre.status_code == 200, pre.text
            assert pre.json() == []

            _activate(client, rbase, rid, auth)

            res = client.get(f"{prefix}/search/content", params={"q": "Teamleitung"}, headers=auth)
            assert res.status_code == 200, res.text
            hits = res.json()
            assert len(hits) == 1
            hit = hits[0]
            assert hit["type"] == "resource"
            assert hit["entity_id"] == rid
            assert hit["name"] == "Handbuch"
            # Der Treffer traegt den bestehenden Block-Anker (ADR-0021).
            assert hit["block_id"] == "h-eskalation"
            assert "Teamleitung" in hit["text"]
            # Die Nachbar-Passage taucht NICHT auf — es ist Passage-, kein
            # Entity-Retrieval.
            assert "protokollieren" not in hit["text"]

            # Zuruecknehmen der Aktivierung raeumt die Passagen weg.
            back = client.post(
                f"{rbase}/{rid}/versions/1/transition", json={"to": "inactive"}, headers=auth
            )
            assert back.status_code in (200, 201), back.text
            after = client.get(
                f"{prefix}/search/content", params={"q": "Teamleitung"}, headers=auth
            )
            assert after.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_german_stemming_finds_an_inflected_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die locale-abhaengige FTS-Config (0070) stemmt — `'simple'` konnte das nicht.

    Der Text enthaelt „Reklamationen"; die Query fragt nach „Reklamation".
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    rbase = f"{prefix}/resources"

    try:
        with TestClient(app) as client:
            blocks = [
                _heading("h1", "Vorgehen"),
                _para("p1", "Wir bearbeiten eingehende Reklamationen taggleich."),
            ]
            rid = client.post(rbase, json=_resource_body("Leitfaden", blocks), headers=auth).json()[
                "id"
            ]
            _activate(client, rbase, rid, auth)

            res = client.get(f"{prefix}/search/content", params={"q": "Reklamation"}, headers=auth)
            assert res.status_code == 200, res.text
            assert [h["entity_id"] for h in res.json()] == [rid]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_passage_is_smaller_than_the_full_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der eigentliche Zweck: weniger Kontext als `fetch_resource`.

    Belegt mit Zahlen, dass eine Passage deutlich kleiner ist als das ganze
    Aggregat — sonst waere das Tool nur anderes Ranking.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    rbase = f"{prefix}/resources"

    try:
        with TestClient(app) as client:
            blocks: list[dict[str, Any]] = []
            for i in range(20):
                blocks.append(_heading(f"h{i}", f"Kapitel {i}"))
                blocks.append(_para(f"p{i}", f"Ausfuehrlicher Fliesstext zu Kapitel {i}. " * 20))
            blocks.append(_heading("h-ziel", "Sonderfall Grosskunde"))
            blocks.append(_para("p-ziel", "Grosskunden erhalten binnen zwei Stunden Antwort."))

            rid = client.post(rbase, json=_resource_body("Gross", blocks), headers=auth).json()[
                "id"
            ]
            _activate(client, rbase, rid, auth)

            passage = client.get(
                f"{prefix}/search/content", params={"q": "Grosskunden"}, headers=auth
            ).json()
            assert [h["block_id"] for h in passage] == ["h-ziel"]

            full = client.get(f"{rbase}/{rid}", headers=auth)
            assert full.status_code == 200, full.text

            passage_size = len(passage[0]["text"])
            full_size = len(full.text)
            # Grosszuegige Schranke — der Punkt ist die Groessenordnung, nicht
            # ein exakter Faktor.
            assert passage_size * 10 < full_size, (passage_size, full_size)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_assigned_scope_applies_to_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein `assigned`-Agent findet keine Passagen aus fremden Resources."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    rbase = f"{prefix}/resources"

    try:
        with TestClient(app) as client:
            blocks = [
                _heading("h1", "Geheimes Kapitel"),
                _para("p1", "Interne Eskalationsmatrix fuer Grosskunden."),
            ]
            rid = client.post(rbase, json=_resource_body("Intern", blocks), headers=auth).json()[
                "id"
            ]
            _activate(client, rbase, rid, auth)

            # Persona ohne Playbooks ⇒ der Agent hat keine zugewiesene Resource.
            persona_id = client.post(
                f"{prefix}/personas",
                json={
                    "name": "Leer",
                    "content": {
                        "description": "Ohne Zuweisung",
                        "system_prompt": "x",
                        "traits": [],
                        "content": {"description": "d", "blocks": [_para("b1", "d")]},
                    },
                },
                headers=auth,
            ).json()["id"]
            agent = client.post(
                f"{prefix}/agents",
                json={
                    "name": "Eng",
                    "persona_id": persona_id,
                    "tool_policy": {"resource_read": "assigned", "playbook_read": "assigned"},
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            token = client.post(
                f"{prefix}/tokens",
                json={"name": "eng", "agent_id": agent.json()["id"]},
                headers=auth,
            )
            agent_auth = {"Authorization": f"Bearer {token.json()['token']}"}

            # Owner findet die Passage, der eingeschraenkte Agent nicht.
            assert client.get(
                f"{prefix}/search/content", params={"q": "Eskalationsmatrix"}, headers=auth
            ).json()
            scoped = client.get(
                f"{prefix}/search/content", params={"q": "Eskalationsmatrix"}, headers=agent_auth
            )
            assert scoped.status_code == 200, scoped.text
            assert scoped.json() == []
    finally:
        cleanup_workspaces([owner])
