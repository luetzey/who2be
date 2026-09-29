"""Lernschleife B5a: Aktivierungsvertrag nach ADR-0053 6.3 (Modell, Fehler, Service).

Drei Ebenen:

1. **Modell** — `VersionTransitionRequest` nimmt `acknowledge_test_report` und
   `override_reason` (getrimmt, hoechstens 1 000 Zeichen, keine Mindestlaenge),
   `extra="forbid"` bleibt.
2. **Vertrag als reine Funktion** — `check_activation_contract` und die
   `note`-Zusammensetzung, ohne Datenbank.
3. **Service gegen eine echte Pruefall-Menge** — `VersionStatusService` fuer
   persona und playbook: Menge leer, alles `pass`, rot ohne Bestaetigung,
   bestaetigt ohne Grund bzw. nur Leerzeichen, bestaetigt mit Grund. Die
   Menge entsteht ueber die echte API (Agent, Verknuepfung, Pruefaelle,
   Ergebnisse) und wird vom Service mit derselben Aufloesung wie der
   Pruefbericht (B2) bestimmt. Laeuft nur mit erreichbarer Datenbank.

4. **Endpunkte** (B5b) — die fuenf Transition-Router reichen beide Felder an
   den Service durch: je Elementart 409 mit Bericht in `params` bzw.
   Aktivierung mit Bestaetigung plus Grund, ueber HTTP.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.errors import ApiError
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.security import WorkspaceContext
from who2be_api.main import app
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.test_case_service import TestReport, TestReportCounts
from who2be_api.services.version_status import (
    TEST_OVERRIDE_NOTE_PREFIX,
    VersionStatusService,
    check_activation_contract,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import VersionStatus, VersionTransitionRequest, WorkspaceRole
from who2be_models.status import OVERRIDE_REASON_MAX_LENGTH, TRANSITION_NOTE_MAX_LENGTH

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"

# --- 1. Modell ---------------------------------------------------------------


def test_request_defaults_keep_old_payloads_valid() -> None:
    req = VersionTransitionRequest.model_validate({"to": "active"})
    assert req.acknowledge_test_report is False
    assert req.override_reason is None


def test_request_trims_reason_and_has_no_minimum_length() -> None:
    req = VersionTransitionRequest.model_validate(
        {"to": "active", "acknowledge_test_report": True, "override_reason": "  x  "}
    )
    # Ein Zeichen reicht — die 10-Zeichen-Regel der Design-Spec gilt nicht.
    assert req.override_reason == "x"
    # Nur Leerzeichen ist KEIN Formatfehler: der Service antwortet dafuer mit
    # 409 `test_override_reason_required` (Vertrag unterscheidet die Faelle).
    blank = VersionTransitionRequest.model_validate({"to": "active", "override_reason": "   "})
    assert blank.override_reason == ""


def test_request_reason_max_length_counts_after_trim() -> None:
    padded = " " * 50 + "r" * OVERRIDE_REASON_MAX_LENGTH + " " * 50
    req = VersionTransitionRequest.model_validate({"to": "active", "override_reason": padded})
    assert req.override_reason == "r" * OVERRIDE_REASON_MAX_LENGTH
    with pytest.raises(ValidationError):
        VersionTransitionRequest.model_validate(
            {"to": "active", "override_reason": "r" * (OVERRIDE_REASON_MAX_LENGTH + 1)}
        )


def test_request_still_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        VersionTransitionRequest.model_validate({"to": "active", "acknowledge": True})


# --- 2. Vertrag als reine Funktion ------------------------------------------


def _report(*, passed: int = 0, failed: int = 0, error: int = 0, missing: int = 0) -> TestReport:
    total = passed + failed + error + missing
    return TestReport(
        entity_type="persona",
        entity_id=uuid4(),
        version_id=uuid4(),
        affected_agent_count=1,
        scope_note=None,
        counts=TestReportCounts(
            total=total, passed=passed, failed=failed, error=error, missing=missing
        ),
        agents=[],
    )


@pytest.mark.parametrize("report", [_report(), _report(passed=3)], ids=["leer", "alles-pass"])
def test_contract_green_ignores_both_fields(report: TestReport) -> None:
    for ack, reason in ((False, None), (True, "egal"), (False, "   ")):
        assert (
            check_activation_contract(
                report, acknowledge_test_report=ack, override_reason=reason, note="n"
            )
            == "n"
        )


@pytest.mark.parametrize(
    "report",
    [_report(passed=1, failed=1), _report(error=1), _report(passed=2, missing=1)],
    ids=["fail", "error", "missing"],
)
def test_contract_red_or_missing_without_ack_is_409(report: TestReport) -> None:
    with pytest.raises(ApiError) as exc:
        check_activation_contract(
            report, acknowledge_test_report=False, override_reason="Grund", note=None
        )
    assert exc.value.status_code == 409
    assert exc.value.reason == "test_results_incomplete"
    params = exc.value.params
    assert params is not None
    assert params["total"] == report.counts.total
    assert params["missing"] == report.counts.missing
    assert params["report"] == report.model_dump(mode="json")


@pytest.mark.parametrize("reason", [None, "", "   \n\t "], ids=["none", "leer", "leerzeichen"])
def test_contract_ack_without_reason_is_409(reason: str | None) -> None:
    report = _report(failed=1)
    with pytest.raises(ApiError) as exc:
        check_activation_contract(
            report, acknowledge_test_report=True, override_reason=reason, note=None
        )
    assert exc.value.status_code == 409
    assert exc.value.reason == "test_override_reason_required"
    assert exc.value.params is not None
    assert exc.value.params["report"] == report.model_dump(mode="json")


def test_contract_note_has_prefix_counts_reason_and_appended_user_note() -> None:
    note = check_activation_contract(
        _report(passed=1, failed=2, error=1, missing=3),
        acknowledge_test_report=True,
        override_reason="Pruefall veraltet",
        note="Freigabe im Review",
    )
    assert note is not None
    assert note.startswith(TEST_OVERRIDE_NOTE_PREFIX)
    assert "(3 rot, 3 fehlend von 7): Pruefall veraltet" in note
    assert note.endswith("Freigabe im Review")


def test_contract_note_stays_within_limit_with_maximal_inputs() -> None:
    reason = "g" * OVERRIDE_REASON_MAX_LENGTH
    user_note = "n" * TRANSITION_NOTE_MAX_LENGTH
    note = check_activation_contract(
        _report(failed=1), acknowledge_test_report=True, override_reason=reason, note=user_note
    )
    assert note is not None
    assert len(note) <= TRANSITION_NOTE_MAX_LENGTH
    # Grund bleibt vollstaendig, gekuerzt wird nur die angehaengte Nutzer-note.
    assert reason in note
    assert "Notiz: nnn" in note
    assert note.endswith("…")


# --- 3. Service gegen echte Pruefall-Menge ----------------------------------


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


def _auth(user_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _fetch(sql: str, *args: Any) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


_VERSION_TABLES = {
    "persona": ("persona_version", "persona_id"),
    "playbook": ("playbook_version", "playbook_id"),
}


def _put_in_review(entity_type: str, entity_id: str) -> str:
    """v1 auf `review` setzen und ihre Versions-ID liefern.

    Direkt per SQL: der Weg nach `review` ist nicht Gegenstand dieses Tests
    (dort greifen die Pflichtfeld-Validatoren), geprueft wird `review -> active`.
    """
    table, fk = _VERSION_TABLES[entity_type]
    rows = _fetch(
        f"UPDATE {table} SET status = 'review' WHERE {fk} = $1 AND version = 1 RETURNING id",
        UUID(entity_id),
    )
    assert len(rows) == 1
    return str(rows[0]["id"])


def _status(entity_type: str, entity_id: str) -> str:
    table, fk = _VERSION_TABLES[entity_type]
    rows = _fetch(f"SELECT status FROM {table} WHERE {fk} = $1 AND version = 1", UUID(entity_id))
    return str(rows[0]["status"])


def _history_notes(entity_type: str, entity_id: str) -> list[str | None]:
    rows = _fetch(
        "SELECT note FROM status_history WHERE entity_type = $1 AND entity_id = $2 "
        "AND version = 1 AND to_status = 'active' ORDER BY changed_at",
        entity_type,
        UUID(entity_id),
    )
    return [r["note"] for r in rows]


class _World:
    """Workspace mit Persona P, Playbook B (an P verlinkt) und Agent A auf P."""

    def __init__(self, client: TestClient, ws: UUID, owner: UUID) -> None:
        self.client = client
        self.ws = ws
        self.owner = owner
        self.auth = _auth(owner)
        self.base = f"/v1/workspaces/{ws}"

    def post(self, path: str, body: dict[str, Any], expected: int = 201) -> Any:
        res = self.client.post(f"{self.base}{path}", json=body, headers=self.auth)
        assert res.status_code == expected, res.text
        return res.json()

    def element(self, entity_type: str) -> str:
        """Frisches Element samt Agent, der es erreicht (Menge nach 3.2.1)."""
        persona = self.post(
            "/personas",
            {"name": f"P-{uuid4().hex[:6]}", "content": {"description": "d", "system_prompt": "s"}},
        )["id"]
        if entity_type == "persona":
            element = persona
        else:
            element = self.post(
                "/playbooks",
                {
                    "name": f"B-{uuid4().hex[:6]}",
                    "content": {
                        "description": "d",
                        "body": "1. Schritt.",
                        "type": "workflow",
                        "tags": [],
                        "triggers": "t",
                    },
                },
            )["id"]
            res = self.client.put(
                f"{self.base}/personas/{persona}/playbooks",
                json={"playbook_ids": [element]},
                headers=self.auth,
            )
            assert res.status_code == 200, res.text
        self.agent = self.post("/agents", {"name": f"A-{uuid4().hex[:6]}", "persona_id": persona})[
            "id"
        ]
        return str(element)

    def case(self, title: str) -> str:
        return str(
            self.post(
                "/test-cases",
                {
                    "agent_id": self.agent,
                    "title": title,
                    "input": "Eingabe",
                    "expected_behavior": "Erwartet",
                },
            )["id"]
        )

    def results(self, entity_type: str, version_id: str, verdicts: dict[str, str]) -> None:
        self.post(
            "/test-runs",
            {
                "subject_entity_type": entity_type,
                "subject_version_id": version_id,
                "results": [
                    {
                        "test_case_id": case_id,
                        "runs_total": 1,
                        "runs_passed": 1 if verdict == "pass" else 0,
                        "verdict": verdict,
                    }
                    for case_id, verdict in verdicts.items()
                ],
            },
        )


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            yield _World(client, ws, owner)
    finally:
        cleanup_workspaces([owner])


Transition = Callable[..., Awaitable[Any]]


def _activate(w: _World, entity_type: str, entity_id: str, **kwargs: Any) -> Any:
    """Ruft den Service `review -> active` fuer v1 (Admin, eigener Pool)."""

    async def _run() -> Any:
        pool = await asyncpg.create_pool(
            get_settings().database_url, init=init_connection, min_size=1, max_size=2
        )
        assert pool is not None
        try:
            svc = VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))
            ctx = WorkspaceContext(workspace_id=w.ws, user_id=w.owner, role=WorkspaceRole.admin)
            method: Transition = {
                "persona": svc.transition_persona_version,
                "playbook": svc.transition_playbook_version,
            }[entity_type]
            return await method(
                ctx, UUID(entity_id), 1, VersionStatus.active, kwargs.pop("note", None), **kwargs
            )
        finally:
            await pool.close()

    return asyncio.run(_run())


_TYPES = ["persona", "playbook"]


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
def test_empty_set_activates_and_ignores_fields(world: _World, entity_type: str) -> None:
    element = world.element(entity_type)
    _put_in_review(entity_type, element)
    # Betroffener Agent ohne Pruefall -> Menge leer. Felder werden ignoriert:
    # auch ein Grund aus Leerzeichen fuehrt zu keinem 409 und keinem Praefix.
    result = _activate(
        world,
        entity_type,
        element,
        note="nur Notiz",
        acknowledge_test_report=False,
        override_reason="",
    )
    assert result.status == VersionStatus.active
    assert _history_notes(entity_type, element) == ["nur Notiz"]


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
def test_all_pass_activates_without_ack(world: _World, entity_type: str) -> None:
    element = world.element(entity_type)
    version_id = _put_in_review(entity_type, element)
    world.results(entity_type, version_id, {world.case("a"): "pass", world.case("b"): "pass"})
    result = _activate(world, entity_type, element)
    assert result.status == VersionStatus.active
    assert _history_notes(entity_type, element) == [None]


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
def test_red_without_ack_is_409_with_report_and_changes_nothing(
    world: _World, entity_type: str
) -> None:
    element = world.element(entity_type)
    version_id = _put_in_review(entity_type, element)
    red, _missing = world.case("rot"), world.case("fehlt")
    world.results(entity_type, version_id, {red: "fail"})

    with pytest.raises(ApiError) as exc:
        _activate(world, entity_type, element, override_reason="Grund ohne Bestaetigung")
    assert exc.value.status_code == 409
    assert exc.value.reason == "test_results_incomplete"
    params = exc.value.params
    assert params is not None
    assert (params["total"], params["failed"], params["missing"]) == (2, 1, 1)
    report = TestReport.model_validate(params["report"])
    assert str(report.version_id) == version_id
    states = {str(e.test_case.id): e.state for g in report.agents for e in g.entries}
    assert states == {red: "fail", _missing: "missing"}
    # Abgewiesen heisst: nichts geschrieben.
    assert _status(entity_type, element) == "review"
    assert _history_notes(entity_type, element) == []


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
@pytest.mark.parametrize("reason", [None, "   "], ids=["ohne-grund", "nur-leerzeichen"])
def test_ack_without_reason_is_409(world: _World, entity_type: str, reason: str | None) -> None:
    element = world.element(entity_type)
    _put_in_review(entity_type, element)
    world.case("fehlt")
    # Der Router gibt den getrimmten Wert aus dem Modell weiter; der Service
    # trimmt selbst noch einmal, damit der Vertrag nicht am Modell haengt.
    with pytest.raises(ApiError) as exc:
        _activate(world, entity_type, element, acknowledge_test_report=True, override_reason=reason)
    assert exc.value.status_code == 409
    assert exc.value.reason == "test_override_reason_required"
    assert exc.value.params is not None
    assert exc.value.params["missing"] == 1
    assert _status(entity_type, element) == "review"


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
def test_ack_with_reason_activates_and_records_reason_plus_note(
    world: _World, entity_type: str
) -> None:
    element = world.element(entity_type)
    version_id = _put_in_review(entity_type, element)
    world.results(
        entity_type,
        version_id,
        {world.case("rot"): "fail", world.case("fehler"): "error", world.case("ok"): "pass"},
    )
    world.case("fehlt")
    result = _activate(
        world,
        entity_type,
        element,
        acknowledge_test_report=True,
        override_reason="  Pruefall veraltet  ",
        note="Review ok",
    )
    assert result.status == VersionStatus.active
    notes = _history_notes(entity_type, element)
    assert notes == [
        f"{TEST_OVERRIDE_NOTE_PREFIX} (2 rot, 1 fehlend von 4): Pruefall veraltet"
        "\n\nNotiz: Review ok"
    ]


@pytest.mark.integration
def test_reason_and_note_both_land_in_history_below_limit(world: _World) -> None:
    """Maximaler Grund plus maximale note: beide in `status_history.note`, <= 2 000.

    Liest ueber `_provenance` zurueck — `StatusHistoryEntry` validiert die
    2 000er-Grenze, eine laengere note wuerde die Versionsherkunft brechen.
    """
    element = world.element("persona")
    _put_in_review("persona", element)
    world.case("fehlt")
    reason = "g" * OVERRIDE_REASON_MAX_LENGTH
    user_note = "n" * TRANSITION_NOTE_MAX_LENGTH
    _activate(
        world,
        "persona",
        element,
        acknowledge_test_report=True,
        override_reason=reason,
        note=user_note,
    )
    [note] = _history_notes("persona", element)
    assert note is not None
    assert len(note) <= TRANSITION_NOTE_MAX_LENGTH
    assert reason in note
    assert "Notiz: nnnn" in note

    async def _provenance() -> list[Any]:
        pool = await asyncpg.create_pool(
            get_settings().database_url, init=init_connection, min_size=1, max_size=1
        )
        assert pool is not None
        try:
            svc = VersionStatusService(pool, StatusHistoryService(PgStatusHistoryRepository()))
            ctx = WorkspaceContext(
                workspace_id=world.ws, user_id=world.owner, role=WorkspaceRole.admin
            )
            return await svc.provenance_persona(ctx, UUID(element), 1)
        finally:
            await pool.close()

    entries = asyncio.run(_provenance())
    assert [e.note for e in entries if e.to_status == VersionStatus.active] == [note]


# --- 4. Endpunkte: die fuenf Transition-Router (B5b) ------------------------
#
# `POST .../versions/1/transition` mit `to=active` je Elementart. Die rote
# Menge (1 fail, 1 missing) haengt DIREKT am Element (Teil (1) der Vereinigung
# nach 3.2.1) — das geht fuer alle fuenf Arten gleich, auch fuer
# `external_tool` ohne Verweisindex. Reicht ein Router die Felder nicht durch,
# faellt der Bestaetigungs-Fall auf 409 `test_results_incomplete` zurueck.

# entity_type -> (URL-Segment, Versionstabelle, FK-Spalte, Create-Body)
_ENDPOINT_KINDS: dict[str, tuple[str, str, str, dict[str, Any]]] = {
    "persona": (
        "personas",
        "persona_version",
        "persona_id",
        {"content": {"description": "d", "system_prompt": "s"}},
    ),
    "playbook": (
        "playbooks",
        "playbook_version",
        "playbook_id",
        {
            "content": {
                "description": "d",
                "body": "1. Schritt.",
                "type": "workflow",
                "tags": [],
                "triggers": "t",
            }
        },
    ),
    "resource": (
        "resources",
        "resource_version",
        "resource_id",
        {
            "content": {
                "description": "d",
                "blocks": [{"id": "b1", "type": "heading", "props": {"level": 1}}],
                "tags": [],
            }
        },
    ),
    "system_prompt_template": (
        "system-prompts",
        "system_prompt_template_version",
        "template_id",
        {"content": {"description": "d", "body": "Du bist ein Test-Agent."}},
    ),
    "external_tool": (
        "external_tools",
        "external_tool_version",
        "external_tool_id",
        {},
    ),
}
_ALL_TYPES = list(_ENDPOINT_KINDS)


class _Element:
    """Element in `review` mit roter Pruefall-Menge (1 fail, 1 missing)."""

    def __init__(self, w: _World, entity_type: str) -> None:
        segment, table, fk, body = _ENDPOINT_KINDS[entity_type]
        self.w = w
        self.entity_type = entity_type
        self.table = table
        self.fk = fk
        self.id = str(w.post(f"/{segment}", {"name": f"E-{uuid4().hex[:6]}", **body})["id"])
        self.url = f"{w.base}/{segment}/{self.id}/versions/1/transition"
        # Direkt per SQL nach `review`: geprueft wird `review -> active`.
        rows = _fetch(
            f"UPDATE {table} SET status = 'review' WHERE {fk} = $1 AND version = 1 RETURNING id",
            UUID(self.id),
        )
        assert len(rows) == 1
        self.version_id = str(rows[0]["id"])
        agent = w.post("/agents", {"name": f"A-{uuid4().hex[:6]}"})["id"]
        self.red = self._case(agent, "rot")
        self.missing = self._case(agent, "fehlt")
        w.post(
            "/test-runs",
            {
                "subject_entity_type": entity_type,
                "subject_version_id": self.version_id,
                "results": [
                    {"test_case_id": self.red, "runs_total": 1, "runs_passed": 0, "verdict": "fail"}
                ],
            },
        )

    def _case(self, agent: str, title: str) -> str:
        return str(
            self.w.post(
                "/test-cases",
                {
                    "agent_id": agent,
                    "entity_type": self.entity_type,
                    "entity_id": self.id,
                    "title": title,
                    "input": "Eingabe",
                    "expected_behavior": "Erwartet",
                },
            )["id"]
        )

    def transition(self, body: dict[str, Any]) -> Any:
        return self.w.client.post(self.url, json={"to": "active", **body}, headers=self.w.auth)

    def status(self) -> str:
        rows = _fetch(
            f"SELECT status FROM {self.table} WHERE {self.fk} = $1 AND version = 1",
            UUID(self.id),
        )
        return str(rows[0]["status"])

    def active_notes(self) -> list[str | None]:
        rows = _fetch(
            "SELECT note FROM status_history WHERE entity_type = $1 AND entity_id = $2 "
            "AND version = 1 AND to_status = 'active' ORDER BY changed_at",
            self.entity_type,
            UUID(self.id),
        )
        return [r["note"] for r in rows]


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _ALL_TYPES)
def test_endpoint_red_without_ack_is_409_with_report_in_params(
    world: _World, entity_type: str
) -> None:
    el = _Element(world, entity_type)
    res = el.transition({"override_reason": "Grund ohne Bestaetigung"})
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["reason"] == "test_results_incomplete"
    params = body["params"]
    assert (params["total"], params["failed"], params["missing"]) == (2, 1, 1)
    report = params["report"]
    assert report["entity_type"] == entity_type
    assert report["version_id"] == el.version_id
    states = {e["test_case"]["id"]: e["state"] for g in report["agents"] for e in g["entries"]}
    assert states == {el.red: "fail", el.missing: "missing"}
    assert el.status() == "review"
    assert el.active_notes() == []


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _ALL_TYPES)
def test_endpoint_ack_with_blank_reason_is_409_reason_required(
    world: _World, entity_type: str
) -> None:
    el = _Element(world, entity_type)
    res = el.transition({"acknowledge_test_report": True, "override_reason": "   "})
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["reason"] == "test_override_reason_required"
    assert body["params"]["report"]["version_id"] == el.version_id
    assert el.status() == "review"


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _ALL_TYPES)
def test_endpoint_ack_with_reason_activates(world: _World, entity_type: str) -> None:
    el = _Element(world, entity_type)
    res = el.transition(
        {"acknowledge_test_report": True, "override_reason": "  Pruefall veraltet  "}
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"
    assert el.status() == "active"
    assert el.active_notes() == [
        f"{TEST_OVERRIDE_NOTE_PREFIX} (1 rot, 1 fehlend von 2): Pruefall veraltet"
    ]
