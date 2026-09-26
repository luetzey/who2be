"""Kontoweite Routen verlangen einen menschlichen Aufrufer (Karte t_c119c5e6).

Die Routen ausserhalb des Workspace-Prefix hingen bisher an `get_current_user`,
das den Aufrufer auf die nackte `user_id` reduziert: ein `w2b_`-Token war dort
von einer eingeloggten Person nicht zu unterscheiden. Das Gate sitzt jetzt in
der Dependency selbst, damit eine neue Route auf diesem Pfad per Vorgabe
abgesichert ist und nicht per Nachtrag.

Der Test ist tabellengetrieben und fordert **403 plus `reason`** — nicht bloss
"nicht 2xx". Mehrere dieser Routen antworten auch aus anderen Gruenden mit
404/409/402, und ein Test, der nur auf "kein Erfolg" prueft, bleibt gruen,
waehrend das Autorisierungs-Gate fehlt.

Gegenprobe in beide Richtungen: derselbe Aufruf als eingeloggter Mensch (JWT)
laeuft weiter durch, inklusive der loeschenden und exportierenden Pfade.

`GET /v1/me` ist bewusst **nicht** in der Sperrliste: die Route bleibt fuer
Maschinen erreichbar (der MCP-Server loest darueber Token und Workspace auf),
ihre Antwort wird fuer den Token-Pfad aber auf den gepinnten Workspace
geschnitten. Das prueft `test_me_for_token_is_scoped_to_pinned_workspace`.

**Zur Menge "ungebundene Tokens":** seit Migration 0048 haelt ein DB-CHECK
(`agent_id IS NOT NULL OR revoked_at IS NOT NULL`) fest, dass jeder *aktive*
Token agent-gebunden ist — ein ungebundener aktiver Token laesst sich weder
ueber die API noch per direktem SQL erzeugen. Die Gegenprobe zum gebundenen
Token ist deshalb der Mensch (JWT), nicht ein ungebundener Token.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

# Der MCP-Server wird hier bewusst ECHT importiert (nicht nachgebaut): der Test
# soll belegen, dass der laufende MCP-Code das Gate ueberlebt.
from who2be_mcp import server as mcp_server
from who2be_mcp.auth import Who2BeTokenVerifier as McpTokenVerifier
from who2be_mcp.config import Settings as McpSettings

AuthFactory = Callable[[UUID], dict[str, str]]

# Permissive Policy: die Assertions sollen am kontoweiten Gate haengen, nicht
# an einer fehlenden Capability weiter innen.
_POLICY: dict[str, object] = {
    "persona_write": True,
    "playbook_write": True,
    "resource_write": True,
    "feedback_write": True,
    "promote_retire": True,
}


def _org_body(name: str) -> dict[str, str]:
    return {"name": name, "slug": f"gate-{uuid4().hex[:12]}"}


@pytest.mark.integration
def test_machine_token_is_blocked_on_every_account_wide_route(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: AuthFactory,
) -> None:
    """Jede kontoweite Route antwortet einem `w2b_`-Token mit 403 + `reason`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    human = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            _agent_id, token_auth = agent_token(
                client, prefix, "[Gate] Konto-Agent", _POLICY, human
            )

            # Ein Ziel-Objekt, das es wirklich gibt: sonst koennte ein 404 den
            # fehlenden 403 verdecken.
            org = client.post("/v1/organizations", json=_org_body("Gate-Ziel"), headers=human)
            assert org.status_code == 201, org.text
            org_id = org.json()["id"]

            cases: list[tuple[str, str, dict[str, str] | None]] = [
                ("DELETE", "/v1/me", None),
                ("GET", "/v1/organizations", None),
                ("POST", "/v1/organizations", _org_body("Gate-Agent-Org")),
                ("DELETE", f"/v1/organizations/{org_id}", None),
                ("GET", f"/v1/organizations/{org_id}/workspaces", None),
                (
                    "POST",
                    f"/v1/organizations/{org_id}/workspaces",
                    {"name": "Gate-WS", "slug": f"gate-{uuid4().hex[:12]}"},
                ),
                ("GET", "/v1/gdpr/export", None),
                ("POST", f"/v1/invitations/{uuid4().hex}/accept", None),
            ]

            for method, path, body in cases:
                res = client.request(method, path, json=body, headers=token_auth)
                assert res.status_code == 403, f"{method} {path}: {res.status_code} {res.text}"
                assert res.json()["reason"] == "account_route_requires_human", (
                    f"{method} {path}: {res.text}"
                )

            # Der Account des Besitzers steht noch: `DELETE /v1/me` hat das Gate
            # nicht passiert. Ohne diese Zeile belegt der 403 oben nur den
            # Statuscode, nicht die ausgebliebene Wirkung.
            still_there = client.get("/v1/me", headers=human)
            assert still_there.status_code == 200, still_there.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_human_session_still_reaches_every_account_wide_route(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: AuthFactory,
) -> None:
    """Gegenprobe: ein eingeloggter Mensch kann weiterhin alles, was er heute kann."""
    owner = fresh_user_id()
    setup_workspace(owner)
    human = make_auth_headers(owner)

    try:
        with TestClient(app) as client:
            assert client.get("/v1/organizations", headers=human).status_code == 200

            org = client.post("/v1/organizations", json=_org_body("Mensch-Org"), headers=human)
            assert org.status_code == 201, org.text
            org_id = org.json()["id"]

            workspaces = client.get(f"/v1/organizations/{org_id}/workspaces", headers=human)
            assert workspaces.status_code == 200, workspaces.text

            created_ws = client.post(
                f"/v1/organizations/{org_id}/workspaces",
                json={"name": "Mensch-WS", "slug": f"mensch-{uuid4().hex[:12]}"},
                headers=human,
            )
            assert created_ws.status_code == 201, created_ws.text

            export = client.get("/v1/gdpr/export", headers=human)
            assert export.status_code == 200, export.text

            deleted_org = client.delete(f"/v1/organizations/{org_id}", headers=human)
            assert deleted_org.status_code == 200, deleted_org.text

            # Zuletzt der Konto-Pfad: danach ist dieser User gesperrt.
            deleted_me = client.delete("/v1/me", headers=human)
            assert deleted_me.status_code == 200, deleted_me.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_me_for_token_is_scoped_to_pinned_workspace(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: AuthFactory,
) -> None:
    """Rot-Probe: die Antwort eines gepinnten Tokens nennt nur seinen Workspace.

    Der Workspace-Pin ist die tragende Isolationslinie des Token-Pfades. Ohne
    den Schnitt listet diese Route jede Organisation und jeden Workspace des
    Besitzers — auch die, an die der Token nicht gebunden ist.
    """
    owner = fresh_user_id()
    pinned_ws = setup_workspace(owner)
    human = make_auth_headers(owner)

    try:
        with TestClient(app) as client:
            # Zweite Organisation mit eigenem Workspace: das ist der Bereich,
            # den der gepinnte Token NICHT sehen darf.
            other_org = client.post("/v1/organizations", json=_org_body("Fremd-Org"), headers=human)
            assert other_org.status_code == 201, other_org.text
            other_org_id = other_org.json()["id"]
            other_ws = client.post(
                f"/v1/organizations/{other_org_id}/workspaces",
                json={"name": "Fremd-WS", "slug": f"fremd-{uuid4().hex[:12]}"},
                headers=human,
            )
            assert other_ws.status_code == 201, other_ws.text
            other_ws_id = other_ws.json()["id"]

            _agent_id, token_auth = agent_token(
                client, f"/v1/workspaces/{pinned_ws}", "[Gate] Pin-Agent", _POLICY, human
            )

            # Der Mensch sieht unveraendert beides.
            human_view = client.get("/v1/me", headers=human)
            assert human_view.status_code == 200, human_view.text
            human_ws_ids = {
                w["id"] for org in human_view.json()["organizations"] for w in org["workspaces"]
            }
            assert {str(pinned_ws), other_ws_id} <= human_ws_ids

            # Der Token sieht ausschliesslich seinen gepinnten Workspace.
            token_view = client.get("/v1/me", headers=token_auth)
            assert token_view.status_code == 200, token_view.text
            payload = token_view.json()
            token_ws_ids = {w["id"] for org in payload["organizations"] for w in org["workspaces"]}
            assert token_ws_ids == {str(pinned_ws)}
            assert other_ws_id not in token_ws_ids
            assert other_org_id not in {org["id"] for org in payload["organizations"]}

            # Die beiden Felder, von denen der MCP-Server lebt, bleiben brauchbar
            # und widersprechen der geschnittenen Liste nicht.
            assert payload["token_workspace_id"] == str(pinned_ws)
            assert payload["default_workspace_id"] == str(pinned_ws)
    finally:
        cleanup_workspaces([owner])


def _mcp_settings() -> McpSettings:
    return McpSettings(
        api_base_url="http://testserver",
        transport="http",
        oauth_issuer_url="http://testserver",
        mcp_public_url="http://mcp.test",
    )


@pytest.mark.integration
def test_mcp_token_and_workspace_resolution_survives_the_account_gate(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: AuthFactory,
) -> None:
    """Der MCP-Pfad laeuft nach dem Gate weiter — ausgefuehrt, nicht behauptet.

    `GET /v1/me` ist die einzige kontoweite Route, die Maschinen offen bleibt,
    und der MCP-Server haengt doppelt daran: `Who2BeTokenVerifier.verify_token`
    introspectiert damit jeden eingehenden Bearer, und `_resolve_workspace_id`
    loest darueber den Workspace vor jedem Tool-Call auf. Ein 403 an dieser
    Stelle legte den MCP-Betrieb still — deshalb wird hier der **echte**
    MCP-Code gegen die echte API gefahren und nicht nur der Endpunkt gelesen.

    Zweiter, genauso wichtiger Punkt: der Schnitt auf den gepinnten Workspace
    darf die Resolution nicht bloss „irgendwie" ueberleben, sondern muss genau
    den gebundenen Workspace liefern. Vor dem Schnitt konnte
    `default_workspace_id` (die erste Membership des *Menschen*) einen fremden
    Workspace nennen — der Fehler aus Issue #413.
    """
    owner = fresh_user_id()
    pinned_ws = setup_workspace(owner)
    human = make_auth_headers(owner)

    try:
        with TestClient(app) as client:
            # Eine zweite Organisation zuerst: waere `default_workspace_id` noch
            # die Menschen-Sicht, koennte die Resolution hierauf zeigen.
            other_org = client.post("/v1/organizations", json=_org_body("MCP-Fremd"), headers=human)
            assert other_org.status_code == 201, other_org.text
            other_ws = client.post(
                f"/v1/organizations/{other_org.json()['id']}/workspaces",
                json={"name": "MCP-Fremd-WS", "slug": f"mcpf-{uuid4().hex[:12]}"},
                headers=human,
            )
            assert other_ws.status_code == 201, other_ws.text

            _agent_id, token_auth = agent_token(
                client, f"/v1/workspaces/{pinned_ws}", "[Gate] MCP-Agent", _POLICY, human
            )
        token = token_auth["Authorization"].removeprefix("Bearer ")

        async def _exercise() -> None:
            async with app.router.lifespan_context(app):
                transport = httpx.ASGITransport(app=app)
                real_client = httpx.AsyncClient

                def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
                    kwargs.pop("transport", None)
                    return real_client(*args, transport=transport, **kwargs)  # type: ignore[arg-type]

                settings = _mcp_settings()
                with pytest.MonkeyPatch.context() as mp:
                    mp.setattr(httpx, "AsyncClient", factory)

                    # 1. Introspektion: der Token gilt weiter als gueltig.
                    verified = await McpTokenVerifier(settings).verify_token(token)
                    assert verified is not None
                    assert verified.token == token

                    # 2. Workspace-Resolution: genau der gebundene Workspace.
                    #    Cache geleert, damit die Resolution wirklich laeuft und
                    #    nicht ein Eintrag aus einem fruehen Lauf beantwortet.
                    mcp_server._workspace_cache.clear()
                    resolved = await mcp_server._resolve_workspace_id(settings, token)
                    assert resolved == pinned_ws

        asyncio.run(_exercise())
    finally:
        cleanup_workspaces([owner])
