"""Integrationstests fuer den Workspace-Deckel je Organisation (Issue #576).

Eigene Datei statt Anbau an `test_workspace_management.py` — die Karte deckt ein
eigenes Thema ab und Sammeldateien sind im Repo bewusst ein Anti-Pattern
(`.claude/plan/2026-09-22-1500_p5-sammeldateien-entschaerfen.md`).

Vier Zusagen, je ein Test:

1. Ueber der Grenze antwortet `POST /organizations/{id}/workspaces` mit `402`,
   stabilem `reason` und der Grenze in `params`.
2. **Kein Datenverlust:** ein Workspace-Bestand ueber der Grenze bleibt
   vollstaendig nutzbar — nur die Anlage wird abgewiesen.
3. Eine Loeschung gibt den Platz sofort wieder frei (kein Statusfilter noetig,
   `workspace` hat kein Soft-Delete).
4. On-Prem/OSS ist unbegrenzt — und zaehlt nicht einmal.

Dazu der Pfad, der NICHT gegatet sein darf: die Org-Anlage legt atomar einen
Default-Workspace an und muss auch bei Free-Limit 1 durchlaufen.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from typing import Literal
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient
from httpx import Response

from who2be_api.core.config import Settings, get_settings
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.main import app
from who2be_api.services import workspace_quota_service
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]


def _patch_workspace_quota(
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit: int | None,
    edition: Literal["cloud", "onprem"],
) -> list[UUID]:
    """Haengt ein Entitlement mit `limit` an das Gate (ohne Billing-DB).

    Gibt die Liste der Org-IDs zurueck, fuer die das Gate das Entitlement
    aufgeloest hat — so laesst sich belegen, dass On-Prem gar nicht erst zaehlt.
    """
    resolved: list[UUID] = []

    class _FakePort:
        async def resolve(self, org_id: UUID) -> Entitlement:
            resolved.append(org_id)
            return Entitlement(
                status="active",
                features=frozenset({"core"}),
                workspace_quota=limit,
            )

    monkeypatch.setattr(workspace_quota_service, "get_settings", lambda: Settings(edition=edition))
    monkeypatch.setattr(
        workspace_quota_service, "build_entitlement_port", lambda _pool, _settings: _FakePort()
    )
    return resolved


def _drop_company_org(slug: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "DELETE FROM organization WHERE kind = 'company' AND slug = $1",
                slug,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _create_org(client: TestClient, auth: dict[str, str], slug: str) -> str:
    resp = client.post("/v1/organizations", json={"name": "Quota", "slug": slug}, headers=auth)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _create_workspace(client: TestClient, auth: dict[str, str], org_id: str, slug: str) -> Response:
    resp: Response = client.post(
        f"/v1/organizations/{org_id}/workspaces",
        json={"name": slug.title(), "slug": slug},
        headers=auth,
    )
    return resp


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_workspace_quota_blockt_neue_anlage_und_laesst_bestand_nutzbar(
    monkeypatch: pytest.MonkeyPatch, make_auth_headers: AuthFactory
) -> None:
    """AK 1-3: `402` mit `reason` + `params`, Bestand bleibt vollstaendig nutzbar.

    Der Deckel steht hier auf 2, die Org startet mit ihrem Default-Workspace —
    genau ein weiterer passt also, der uebernaechste nicht mehr. Danach wird der
    Deckel auf 1 gesenkt (das Downgrade-Szenario): der Bestand liegt jetzt
    *ueber* der Grenze und muss trotzdem les- und schreibbar bleiben.
    """
    resolved = _patch_workspace_quota(monkeypatch, limit=2, edition="cloud")

    owner = fresh_user_id()
    setup_workspace(owner)
    auth = make_auth_headers(owner)
    slug = f"wsq-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            org_id = _create_org(client, auth, slug)
            # Die Org-Anlage selbst ist ungegatet — sonst haette sie bei einem
            # Free-Limit von 1 gar nicht erst durchlaufen koennen.
            assert org_id not in [str(o) for o in resolved]

            # Default-Workspace ist da: count == 1 < 2 ⇒ der zweite passt.
            second = _create_workspace(client, auth, org_id, "zweiter")
            assert second.status_code == 201, second.text
            ws_id = second.json()["id"]

            # count == 2 >= 2 ⇒ 402.
            blocked = _create_workspace(client, auth, org_id, "dritter")
            assert blocked.status_code == 402, blocked.text
            body = blocked.json()
            assert body["reason"] == "workspace_quota_exceeded"
            assert body["params"] == {"limit": 2}

            # AK 3 — kein Datenverlust, auch nach einem Downgrade: die Grenze
            # faellt auf 1, der Bestand (2) liegt darueber.
            _patch_workspace_quota(monkeypatch, limit=1, edition="cloud")
            read = client.get(f"/v1/workspaces/{ws_id}", headers=auth)
            assert read.status_code == 200, read.text
            renamed = client.patch(
                f"/v1/workspaces/{ws_id}", json={"name": "Weiter nutzbar"}, headers=auth
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["name"] == "Weiter nutzbar"
            listed = client.get(f"/v1/organizations/{org_id}/workspaces", headers=auth)
            assert listed.status_code == 200
            assert len(listed.json()) == 2

            # Nur die ANLAGE ist zu — und meldet jetzt die gesenkte Grenze.
            still_blocked = _create_workspace(client, auth, org_id, "vierter")
            assert still_blocked.status_code == 402, still_blocked.text
            assert still_blocked.json()["params"] == {"limit": 1}
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_loeschung_gibt_den_platz_wieder_frei(
    monkeypatch: pytest.MonkeyPatch, make_auth_headers: AuthFactory
) -> None:
    """AK 5: Create → Grenze erreicht → Delete → Create ist wieder `201`.

    Belegt zugleich, dass die Zaehlung keinen Statusfilter braucht: `workspace`
    hat kein Soft-Delete (Migration 0006), eine geloeschte Zeile existiert
    schlicht nicht mehr.
    """
    _patch_workspace_quota(monkeypatch, limit=2, edition="cloud")

    owner = fresh_user_id()
    setup_workspace(owner)
    auth = make_auth_headers(owner)
    slug = f"wsd-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            org_id = _create_org(client, auth, slug)
            created = _create_workspace(client, auth, org_id, "temporaer")
            assert created.status_code == 201, created.text
            ws_id = created.json()["id"]

            assert _create_workspace(client, auth, org_id, "zuviel").status_code == 402

            deleted = client.delete(f"/v1/workspaces/{ws_id}", headers=auth)
            assert deleted.status_code == 204, deleted.text

            again = _create_workspace(client, auth, org_id, "wieder-frei")
            assert again.status_code == 201, again.text
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_workspace_quota_greift_in_onprem_nicht(
    monkeypatch: pytest.MonkeyPatch, make_auth_headers: AuthFactory
) -> None:
    """AK 4: On-Prem/OSS ist unbegrenzt — und zaehlt nicht einmal.

    `resolved` bleibt leer: die `is_cloud()`-Wache greift vor der
    Entitlement-Aufloesung, es gibt also keinen Roundtrip gegen die Grenze.
    """
    resolved = _patch_workspace_quota(monkeypatch, limit=1, edition="onprem")

    owner = fresh_user_id()
    setup_workspace(owner)
    auth = make_auth_headers(owner)
    slug = f"wso-{secrets.token_hex(4)}"
    try:
        with TestClient(app) as client:
            org_id = _create_org(client, auth, slug)
            # Default-Workspace (1) liegt bereits auf der Grenze; On-Prem
            # ignoriert sie — mehrfach.
            for name in ("eins", "zwei", "drei"):
                resp = _create_workspace(client, auth, org_id, name)
                assert resp.status_code == 201, resp.text
            assert resolved == []
    finally:
        _drop_company_org(slug)
        cleanup_workspaces([owner])
