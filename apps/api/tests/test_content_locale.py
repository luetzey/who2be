"""Integrationstests fuer „Ein Element, eine Sprache" (ADR-0045, WP3).

Deckt die Querschnitts-Semantik ab, die nicht schon in den Entity-Tests
liegt: den defensiven Legacy-Tie-Break (Alt-Daten aus dem ADR-0027-
Multi-Track koennen dieselbe Versionsnummer in zwei Sprachen tragen) und
das Nachziehen der System-Prompt-Templates (Create-Default, expliziter
`locale`, Listen-Filter, Sprachwechsel via Update, Versions-Rows mit
Entity-Sprache). Laeuft nur mit erreichbarer Datenbank.
"""

import asyncio
from datetime import UTC, datetime, timedelta
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


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "Locale-Test",
        "content": {
            "description": description,
            "content": {
                "description": description,
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description, "styles": {}}],
                    }
                ],
            },
        },
    }


def _template_body(name: str, body: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": "", "body": body},
    }


def _inject_legacy_en_v1(persona_id: str, owner: UUID) -> None:
    """Simuliert einen ADR-0027-Multi-Track-Bestand: EN-v1 NEBEN der DE-v1.

    `UNIQUE (persona_id, locale, version)` erlaubt das weiterhin (Migration
    0069 behaelt die Constraint bewusst); Status `inactive` entspricht der
    0069-Konsolidierung.
    """

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by, locale) "
                "SELECT persona_id, 1, content, 'inactive', $2, 'en' "
                "FROM persona_version WHERE persona_id = $1 AND version = 1 AND locale = 'de'",
                UUID(persona_id),
                owner,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _template_version_locales(template_id: str) -> list[tuple[int, str]]:
    async def _run() -> list[tuple[int, str]]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            rows = await conn.fetch(
                "SELECT version, locale FROM system_prompt_template_version "
                "WHERE template_id = $1 ORDER BY version ASC",
                UUID(template_id),
            )
            return [(row["version"], row["locale"]) for row in rows]
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.integration
def test_legacy_multi_track_reads_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy-Tie-Break: DE-v1 UND EN-v1 unter derselben Entity.

    Detail-/Versions-Reads liefern deterministisch die Row in der
    Entity-Sprache; die Versions-Liste zeigt beide Rows als Historie.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            created = client.post(base, json=_persona_body("deutsch v1"), headers=auth)
            assert created.status_code == 201, created.text
            persona_id = created.json()["id"]
            assert created.json()["locale"] == "de"

            _inject_legacy_en_v1(persona_id, owner)

            # Detail-Read: trotz zweier v1-Rows genau EIN Ergebnis — die Row
            # der Entity-Sprache ('de'). Ohne Tie-Break waere das Ergebnis
            # zufaellig (oder eine doppelte Zeile).
            detail = client.get(f"{base}/{persona_id}", headers=auth)
            assert detail.status_code == 200, detail.text
            assert detail.json()["locale"] == "de"
            assert detail.json()["current_version"] == 1

            # Einzel-Version-Read waehlt bei Duplikaten die Entity-Sprache.
            v1 = client.get(f"{base}/{persona_id}/versions/1", headers=auth)
            assert v1.status_code == 200, v1.text
            assert v1.json()["locale"] == "de"

            # Die Versions-Liste zeigt die vollstaendige Historie (beide Rows).
            versions = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            assert [(v["version"], v["locale"]) for v in versions] == [(1, "de"), (1, "en")]

            # Die Liste liefert die Entity genau einmal (kein Duplikat durch
            # den Legacy-Doppel-Track).
            listed = client.get(base, headers=auth).json()
            assert sum(1 for p in listed if p["id"] == persona_id) == 1

            # Transition ohne locale-Param trifft deterministisch die Row der
            # Entity-Sprache (nicht die inaktive EN-Legacy-Row).
            for to in ("review", "active"):
                promoted = client.post(
                    f"{base}/{persona_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert promoted.status_code == 200, promoted.text
                assert promoted.json()["locale"] == "de"

            # next_version zaehlt GLOBAL ueber alle locales: der Edit erzeugt
            # v2 — keine UniqueViolation gegen die EN-v1 und keinen zweiten
            # per-Sprache-Zaehler.
            updated = client.put(f"{base}/{persona_id}", json=_persona_body("v2"), headers=auth)
            assert updated.status_code == 200, updated.text
            assert updated.json()["current_version"] == 2
            versions_after = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            assert [(v["version"], v["locale"]) for v in versions_after] == [
                (2, "de"),
                (1, "de"),
                (1, "en"),
            ]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_system_prompt_template_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System-Prompt-Templates ziehen nach (ADR-0045, WP3 Punkt 7).

    Create ohne `locale` → Workspace-Default `'de'`; Create mit `locale='en'`
    → Entity + v1-Row tragen `'en'`; Listen-Filter `?locale=`; Sprachwechsel
    via Update (neue Versions-Row folgt der Entity-Sprache).
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/system-prompts"

    try:
        with TestClient(app) as client:
            # Create OHNE locale → Workspace-Default 'de'.
            created_de = client.post(
                base, json=_template_body("Tpl DE", "Hallo {{ persona.name }}"), headers=auth
            )
            assert created_de.status_code == 201, created_de.text
            de_id = created_de.json()["id"]
            assert created_de.json()["locale"] == "de"
            assert _template_version_locales(de_id) == [(1, "de")]

            # Create MIT locale='en' → Entity + Version tragen 'en'.
            body_en = _template_body("Tpl EN", "Hello {{ persona.name }}")
            body_en["locale"] = "en"
            created_en = client.post(base, json=body_en, headers=auth)
            assert created_en.status_code == 201, created_en.text
            en_id = created_en.json()["id"]
            assert created_en.json()["locale"] == "en"
            assert _template_version_locales(en_id) == [(1, "en")]

            # Unbekannte Sprache → 422 an der Modell-Grenze.
            body_bad = _template_body("Tpl XX", "x")
            body_bad["locale"] = "xx"
            assert client.post(base, json=body_bad, headers=auth).status_code == 422

            # Listen-Filter auf die Entity-Sprache (Seed-Templates sind 'de').
            listed_en = client.get(f"{base}?locale=en", headers=auth).json()
            assert {t["id"] for t in listed_en} == {en_id}
            listed_de_ids = {t["id"] for t in client.get(f"{base}?locale=de", headers=auth).json()}
            assert de_id in listed_de_ids
            assert en_id not in listed_de_ids

            # Detail-Read traegt die Entity-Sprache Top-Level.
            assert client.get(f"{base}/{en_id}", headers=auth).json()["locale"] == "en"

            # v1 ist Draft — vor dem PUT (Draft-on-Edit) erst publizieren.
            for to in ("review", "active"):
                promoted = client.post(
                    f"{base}/{en_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert promoted.status_code == 200, promoted.text

            # Sprachwechsel via Update: Entity wechselt auf 'de', die neue
            # Versions-Row uebernimmt die Sprache, die Historie behaelt 'en'.
            switch = _template_body("Tpl EN", "Jetzt deutsch {{ persona.name }}")
            switch.pop("name")
            switch["locale"] = "de"
            switched = client.put(f"{base}/{en_id}", json=switch, headers=auth)
            assert switched.status_code == 200, switched.text
            assert switched.json()["locale"] == "de"
            assert switched.json()["current_version"] == 2
            assert _template_version_locales(en_id) == [(1, "en"), (2, "de")]
    finally:
        cleanup_workspaces([owner])
