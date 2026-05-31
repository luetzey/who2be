"""Tests fuer den Promote-Validator (Welle 4).

Drei Ebenen:
1. Unit-Tests fuer `promote_validation.py` (kein DB-Zugriff) — prueft die
   Logik der Pflichtfeld-Tabelle isoliert.
2. Integrationstests (brauchen erreichbare DB) — prueft den vollstaendigen
   Flow:
   - Create mit minimalem Body (nur `name`) → 201, status='draft'
   - Transition `draft → review` mit unvollstaendigem Draft → 409,
     `application/problem+json`, `missing`-Liste korrekt
   - Transition nach Befuellen → 200

DoD aus dem Spec: alle drei Cases pro Entity (Persona, Playbook, Resource).
Agent wird separat besprochen — kein Versions-Workflow, daher kein
Transition-Gate.
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
from who2be_api.services.promote_validation import (
    PromoteValidationError,
    _blocks_empty,
    _field_empty,
    validate_promote_persona,
    validate_promote_playbook,
    validate_promote_resource,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import VersionStatus

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


# ---------------------------------------------------------------------------
# Unit-Tests — kein DB-Zugriff
# ---------------------------------------------------------------------------


class TestFieldEmpty:
    def test_none_is_empty(self) -> None:
        assert _field_empty(None) is True

    def test_empty_string_is_empty(self) -> None:
        assert _field_empty("") is True

    def test_whitespace_is_empty(self) -> None:
        assert _field_empty("   ") is True

    def test_non_empty_string_is_not_empty(self) -> None:
        assert _field_empty("hello") is False

    def test_zero_is_not_empty(self) -> None:
        # Nur str/None werden als leer behandelt; andere Typen sind nicht leer.
        assert _field_empty(0) is False


class TestBlocksEmpty:
    def test_empty_list_is_empty(self) -> None:
        assert _blocks_empty([]) is True

    def test_block_with_text_is_not_empty(self) -> None:
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "content": [{"type": "text", "text": "Hello world", "styles": {}}],
            }
        ]
        assert _blocks_empty(blocks) is False

    def test_block_with_empty_text_is_empty(self) -> None:
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "content": [{"type": "text", "text": "   ", "styles": {}}],
            }
        ]
        assert _blocks_empty(blocks) is True

    def test_block_with_no_content_key_is_not_empty(self) -> None:
        # Unbekanntes Format — konservativ als befuellt werten.
        blocks = [{"id": "b1", "type": "image"}]
        assert _blocks_empty(blocks) is False


class TestValidatePromotePersona:
    def _full_content(self) -> dict[str, object]:
        return {
            "description": "A persona description.",
            "system_prompt": "",
            "traits": [],
            "tags": [],
            "content": {
                "description": "",
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Body text", "styles": {}}],
                    }
                ],
            },
        }

    def test_full_content_passes_for_review(self) -> None:
        validate_promote_persona("MyPersona", self._full_content(), VersionStatus.review)

    def test_full_content_passes_for_active(self) -> None:
        validate_promote_persona("MyPersona", self._full_content(), VersionStatus.active)

    def test_non_promote_transition_skipped(self) -> None:
        # inactive -> draft ist kein Promote — kein Gate.
        validate_promote_persona("MyPersona", {}, VersionStatus.draft)

    def test_missing_description_raises(self) -> None:
        content = self._full_content()
        content["description"] = ""
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_persona("MyPersona", content, VersionStatus.review)
        assert "description" in exc_info.value.missing

    def test_missing_body_raises(self) -> None:
        content: dict[str, object] = {
            "description": "Desc",
            "content": {"description": "", "blocks": []},
        }
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_persona("MyPersona", content, VersionStatus.review)
        assert "body" in exc_info.value.missing

    def test_empty_name_raises(self) -> None:
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_persona("", self._full_content(), VersionStatus.review)
        assert "name" in exc_info.value.missing

    def test_all_missing_returns_all_fields(self) -> None:
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_persona("", {"description": "", "content": None}, VersionStatus.review)
        missing = exc_info.value.missing
        assert "name" in missing
        assert "description" in missing
        assert "body" in missing


class TestValidatePromotePlaybook:
    def _full_content(self) -> dict[str, object]:
        return {
            "description": "A playbook description.",
            "body": "Step 1. Step 2.",
            "type": "workflow",
            "tags": [],
        }

    def test_full_content_passes(self) -> None:
        validate_promote_playbook("MyPlaybook", self._full_content(), VersionStatus.review)

    def test_missing_type_raises(self) -> None:
        content = dict(self._full_content())
        content["type"] = ""
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_playbook("MyPlaybook", content, VersionStatus.review)
        assert "type" in exc_info.value.missing

    def test_missing_body_raises(self) -> None:
        content = dict(self._full_content())
        content["body"] = ""
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_playbook("MyPlaybook", content, VersionStatus.review)
        assert "body" in exc_info.value.missing

    def test_all_fields_missing(self) -> None:
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_playbook(
                "", {"description": "", "body": "", "type": ""}, VersionStatus.active
            )
        missing = exc_info.value.missing
        assert set(missing) == {"name", "description", "body", "type"}


class TestValidatePromoteResource:
    def _full_content(self) -> dict[str, object]:
        return {
            "description": "A resource description.",
            "blocks": [
                {
                    "id": "b1",
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Body text", "styles": {}}],
                }
            ],
        }

    def test_full_content_passes(self) -> None:
        validate_promote_resource("MyResource", self._full_content(), VersionStatus.review)

    def test_missing_description_raises(self) -> None:
        content = dict(self._full_content())
        content["description"] = ""
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_resource("MyResource", content, VersionStatus.review)
        assert "description" in exc_info.value.missing

    def test_empty_blocks_raises(self) -> None:
        content: dict[str, object] = {"description": "Desc", "blocks": []}
        with pytest.raises(PromoteValidationError) as exc_info:
            validate_promote_resource("MyResource", content, VersionStatus.review)
        assert "body" in exc_info.value.missing


# ---------------------------------------------------------------------------
# Integration-Tests — brauchen erreichbare DB
# ---------------------------------------------------------------------------


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


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


# --- Persona ---


@pytest.mark.integration
def test_persona_create_with_name_only_yields_201_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anlegen mit nur `name` ergibt HTTP 201 und status='draft'."""
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
            resp = client.post(base, json={"name": "MinimalPersona"}, headers=auth)
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["name"] == "MinimalPersona"
            assert data["current_status"] == "draft"
            assert data["content"]["description"] == ""
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_promote_incomplete_draft_returns_409_with_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote einer Persona ohne description + body ergibt 409 mit missing-Liste."""
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
            persona_id = client.post(base, json={"name": "IncompletePersona"}, headers=auth).json()[
                "id"
            ]

            resp = client.post(
                f"{base}/{persona_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 409, resp.text
            assert resp.headers["content-type"].startswith("application/problem+json")
            body = resp.json()
            assert body["type"] == "https://who2be.dev/errors/promote-validation-failed"
            assert body["status"] == 409
            assert "description" in body["missing"]
            assert "body" in body["missing"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_promote_complete_draft_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote einer vollstaendigen Persona-Draft gelingt."""
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
            persona_id = client.post(
                base,
                json={
                    "name": "CompletePersona",
                    "content": {
                        "description": "A persona description.",
                        "content": {
                            "description": "",
                            "blocks": [_block("b1", "My persona body text.")],
                        },
                    },
                },
                headers=auth,
            ).json()["id"]

            resp = client.post(
                f"{base}/{persona_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "review"
    finally:
        cleanup_workspaces([owner])


# --- Playbook ---


@pytest.mark.integration
def test_playbook_create_with_name_only_yields_201_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anlegen mit nur `name` ergibt HTTP 201 und status='draft'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            resp = client.post(base, json={"name": "MinimalPlaybook"}, headers=auth)
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["name"] == "MinimalPlaybook"
            assert data["current_status"] == "draft"
            assert data["content"]["description"] == ""
            assert data["content"]["body"] == ""
            assert data["content"]["type"] == ""
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_promote_incomplete_draft_returns_409_with_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote eines Playbooks ohne description/body/type ergibt 409 mit missing-Liste."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            playbook_id = client.post(
                base, json={"name": "IncompletePlaybook"}, headers=auth
            ).json()["id"]

            resp = client.post(
                f"{base}/{playbook_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 409, resp.text
            assert resp.headers["content-type"].startswith("application/problem+json")
            body = resp.json()
            assert body["type"] == "https://who2be.dev/errors/promote-validation-failed"
            missing = body["missing"]
            assert "description" in missing
            assert "body" in missing
            assert "type" in missing
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_promote_complete_draft_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote eines vollstaendigen Playbook-Drafts gelingt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            playbook_id = client.post(
                base,
                json={
                    "name": "CompletePlaybook",
                    "content": {
                        "description": "A playbook description.",
                        "body": "Step 1. Step 2.",
                        "type": "workflow",
                    },
                },
                headers=auth,
            ).json()["id"]

            resp = client.post(
                f"{base}/{playbook_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "review"
    finally:
        cleanup_workspaces([owner])


# --- Resource ---


@pytest.mark.integration
def test_resource_create_with_name_only_yields_201_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anlegen mit nur `name` ergibt HTTP 201 und status='draft'."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            resp = client.post(base, json={"name": "MinimalResource"}, headers=auth)
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["name"] == "MinimalResource"
            assert data["current_status"] == "draft"
            assert data["content"]["description"] == ""
            assert data["content"]["blocks"] == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_promote_incomplete_draft_returns_409_with_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote einer Resource ohne description + body ergibt 409 mit missing-Liste."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            resource_id = client.post(
                base, json={"name": "IncompleteResource"}, headers=auth
            ).json()["id"]

            resp = client.post(
                f"{base}/{resource_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 409, resp.text
            assert resp.headers["content-type"].startswith("application/problem+json")
            body = resp.json()
            assert body["type"] == "https://who2be.dev/errors/promote-validation-failed"
            assert "description" in body["missing"]
            assert "body" in body["missing"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_promote_complete_draft_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote einer vollstaendigen Resource-Draft gelingt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            resource_id = client.post(
                base,
                json={
                    "name": "CompleteResource",
                    "content": {
                        "description": "A resource description.",
                        "blocks": [_block("b1", "Resource body text.")],
                    },
                },
                headers=auth,
            ).json()["id"]

            resp = client.post(
                f"{base}/{resource_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "review"
    finally:
        cleanup_workspaces([owner])
