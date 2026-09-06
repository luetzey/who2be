"""Fehlercodes in API-Antworten — der Vertrag aus ADR-0051 (#436, W0 von #402).

Drei Ebenen, weil der Vertrag drei Zusagen macht:

1. **Migrierte Stellen** tragen `reason` zusaetzlich zu `detail` — gegen eine
   echte DB, weil ein 404 auf einen unbekannten Agenten sonst gar nicht
   entsteht (`WHO2BE_REQUIRE_DB=1` macht ein fehlendes Postgres zum Fehler
   statt zum Skip, ADR-0041).
2. **Nicht migrierte Stellen** sind unveraendert — das ist die eigentliche
   Risiko-Zusage der Welle: `detail` bleibt Wort fuer Wort, es kommt kein
   Feld dazu, der Content-Type wechselt nicht. Ohne diesen Test faellt eine
   versehentliche Verbreiterung erst beim Client auf.
3. **Der Handler selbst** — `params`, Header und die Abgrenzung zur
   RFC-7807-Serialisierung der Gates. Ohne DB.

Zur Serialisierungs-Frage: `ApiProblem` (Gates, ``application/problem+json``)
und `ApiErrorBody` (alles uebrige, ``application/json``) bleiben zwei Huellen
um EIN Vokabular. `test_gate_error_keeps_rfc7807_shape` haelt fest, dass diese
Welle die Gate-Antworten nicht angefasst hat.
"""

from collections.abc import Callable
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.main import _on_api_error, _on_api_gate_error, app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]


# --- 1. Migrierte Stellen: `reason` liegt im Body ---------------------------


@pytest.mark.integration
def test_unknown_agent_404_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Der Pilot-Fall aus dem Issue: unbekannter Agent => 404 + `agent_not_found`."""
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/agents/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    # Additiv: derselbe Content-Type und dasselbe `detail` wie vor der Welle.
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Agent nicht gefunden.", "reason": "agent_not_found"}


@pytest.mark.integration
def test_last_workspace_delete_409_carries_reason(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Der letzte Workspace einer Organization ist geschuetzt (409).

    `setup_workspace` legt eine Personal-Org mit genau einem Workspace an —
    dessen Loeschung ist damit garantiert der Grenzfall.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.delete(
                f"/v1/workspaces/{workspace_id}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 409
    body = resp.json()
    assert body["reason"] == "last_workspace_undeletable"
    assert body["detail"] == (
        "Der letzte Workspace einer Organization kann nicht geloescht werden."
    )


def test_missing_db_pool_503_carries_reason(
    patched_jwt_secret: str, make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein Pool => 503 + `db_unavailable`.

    Bewusst ohne DB: der Fall IST die fehlende DB. `get_pool` wirft
    `RuntimeError`, wenn der Lifespan keinen Pool aufbauen konnte — genau das
    wird hier erzwungen, statt auf einen kaputten Testlauf zu warten.
    """
    import who2be_api.core.security as security_module

    def _no_pool() -> asyncpg.Pool:
        raise RuntimeError("Datenbank-Pool ist nicht initialisiert.")

    monkeypatch.setattr(security_module, "get_pool", _no_pool)

    with TestClient(app) as client:
        resp = client.get(
            f"/v1/workspaces/{uuid4()}/agents",
            headers=make_auth_headers(fresh_user_id()),
        )

    assert resp.status_code == 503
    assert resp.json() == {"detail": "Datenbank nicht verfuegbar.", "reason": "db_unavailable"}


# --- 2. Nicht migrierte Stellen: byte-identisch zu vorher -------------------


@pytest.mark.integration
def test_unmigrated_error_body_is_unchanged(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> None:
    """Eine Stelle, die diese Welle NICHT angefasst hat, traegt kein `reason`.

    Die Zusage der Welle ist Additivitaet an drei Pilot-Stellen — nicht ein
    neues Feld ueberall. Faellt dieser Test, hat jemand entweder den Handler zu
    breit registriert oder `HTTPException` global ersetzt.
    """
    user_id = fresh_user_id()
    workspace_id = setup_workspace(user_id)
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/v1/workspaces/{workspace_id}/personas/{uuid4()}",
                headers=make_auth_headers(user_id),
            )
    finally:
        cleanup_workspaces([user_id])

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Persona nicht gefunden."}


# --- 3. Handler-Ebene: params, Header, Abgrenzung zu RFC 7807 --------------


def _mini_app(error: ApiError) -> TestClient:
    mini = FastAPI()
    mini.add_exception_handler(ApiError, _on_api_error)

    @mini.get("/boom")
    def boom() -> None:
        raise error

    return TestClient(mini, raise_server_exceptions=False)


def test_handler_omits_params_when_absent() -> None:
    """Ohne Platzhalter kein leeres Feld — sonst traegt jede Antwort Ballast."""
    with _mini_app(
        ApiError(status_code=404, detail="Agent nicht gefunden.", reason="agent_not_found")
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Agent nicht gefunden.", "reason": "agent_not_found"}


def test_handler_passes_params_through() -> None:
    """`params` transportiert die Werte, die der Client in den Text interpoliert."""
    with _mini_app(
        ApiError(
            status_code=413,
            detail="Datei zu gross (max. 10 MB).",
            reason="ingest_too_large",
            params={"limit": "10 MB", "size": 42},
        )
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 413
    assert resp.json()["params"] == {"limit": "10 MB", "size": 42}


def test_handler_keeps_http_exception_headers() -> None:
    """`ApiError` ist eine `HTTPException` — ihre Header duerfen nicht verloren gehen.

    Sonst braeche die erste migrierte 401-Stelle den Auth-Flow: ohne
    `WWW-Authenticate` weiss der Client nicht, wie er sich anmelden soll.
    """
    with _mini_app(
        ApiError(
            status_code=401,
            detail="Nicht authentifiziert.",
            reason="mfa_required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ) as client:
        resp = client.get("/boom")

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_gate_error_keeps_rfc7807_shape() -> None:
    """Die Gate-Serialisierung ist von dieser Welle unberuehrt.

    Zwei Huellen, ein Vokabular: hier `application/problem+json` mit `title`
    und `actionable_by`, beim schlanken Body nicht. Wuerde der neue Handler
    auch `ApiGateError` greifen, faende man es hier.
    """
    mini = FastAPI()
    mini.add_exception_handler(ApiGateError, _on_api_gate_error)
    mini.add_exception_handler(ApiError, _on_api_error)

    @mini.get("/gate")
    def gate() -> None:
        raise ApiGateError(
            status=403,
            reason="insufficient_role",
            actionable_by="human",
            detail="Diese Aktion erfordert mindestens die Rolle 'admin'.",
        )

    with TestClient(mini, raise_server_exceptions=False) as client:
        resp = client.get("/gate")

    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["reason"] == "insufficient_role"
    assert body["actionable_by"] == "human"
    assert "title" in body


def test_pilot_reasons_are_part_of_the_one_vocabulary() -> None:
    """Die drei Pilot-Gruende stehen in `ProblemReason`, nicht in einem zweiten Enum.

    Das ist die Owner-Entscheidung vom 2026-09-06 (Weg B) als Test: taucht
    irgendwann ein paralleler `ErrorCode`-Enum auf, laufen die beiden Listen
    auseinander — dieser Test haelt fest, wo die Gruende hingehoeren.
    """
    from typing import get_args

    from who2be_models.errors import ProblemReason

    reasons = set(get_args(ProblemReason))
    assert {"agent_not_found", "db_unavailable", "last_workspace_undeletable"} <= reasons
