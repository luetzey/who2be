"""Integrationstests fuer die Timeline (Spec N, ADR-0047/0049 — WP15).

Kritische Invarianten (Spec-Akzeptanzen N):

- Gebuckelt wird IMMER ueber `occurred_at`: ein am Dienstag Geschehenes,
  heute Erfasstes erscheint unter Dienstag — nie unter dem Erfassungsdatum.
- Merge uebers Datum: Artifact + Node + Tabellen-Zeilen desselben Tags
  ergeben EINE Scheibe mit allen counts; ein Tag nur mit Notiz ist eine
  volle Scheibe (Buckets = Vereinigung der Quellen).
- `occurred_precision='unknown'` landet NIE in einer Datums-Scheibe —
  nur im separaten, fensterlosen unknown-Bucket.
- Quellen-Gate: explizites `table:<id>` ohne read-Grant → 404, exakt wie
  eine unbekannte Tabelle (Security-Review L1: kein Existenz-Orakel).
- Scope: Agenten sehen nur Artifacts ihrer Grant-Areas und Nodes, deren
  Source-Areas vollstaendig lesbar sind (Filter IN der SQL).
- week-Granularitaet bucketet auf den ISO-Wochen-Montag (Postgres UND das
  app-seitige Tabellen-Bucketing).
- Fenster-Validierung: to <= from_ → 422, > 366 Tage → 422, unbekannte
  Quelle → 422.

Laeuft gegen echte Postgres + tmp-TableStore (`set_table_store`, frische
Instanz je Test — Muster `test_wa_tables`).
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from who2be_api.testing.api_helpers import agent_token, grant, shared_area

from who2be_api.main import app
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_GHOST = "00000000-0000-0000-0000-000000000000"

# 2026-08-03 ist ein Montag, 2026-08-04 der Dienstag derselben ISO-Woche,
# 2026-08-11 der Dienstag der Folgewoche (Montag 2026-08-10).
_TUESDAY = "2026-08-04T09:00:00Z"
_WINDOW = {"from_": "2026-08-01T00:00:00Z", "to": "2026-08-31T00:00:00Z"}

_SCHEMA: dict[str, Any] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "purpose", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "purpose"],
}


@pytest.fixture
def table_store(tmp_path: Path) -> Iterator[TableStore]:
    """Frischer TableStore je Test (Locks binden an die Loop des Tests)."""
    store = TableStore(base_dir=tmp_path)
    set_table_store(store)
    yield store
    reset_table_store()


def _create_artifact(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    area_id: str | None,
    occurred_at: str = _TUESDAY,
    **overrides: Any,
) -> str:
    body: dict[str, Any] = {
        "title": "Notiz",
        "content_md": "Eine Notiz.",
        "occurred_at": occurred_at,
    }
    body.update(overrides)
    url = f"{prefix}/artifacts" if area_id is None else f"{prefix}/work-areas/{area_id}/artifacts"
    created = client.post(url, json=body, headers=headers)
    assert created.status_code == 201, created.text
    artifact_id: str = created.json()["id"]
    return artifact_id


def _create_node(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    source_ref: str,
    occurred_at: str = _TUESDAY,
) -> str:
    created = client.post(
        f"{prefix}/kb/nodes",
        json={
            "content": "Eine belegte Aussage.",
            "tier": "hypothesis",
            "source_ref": source_ref,
            "occurred_at": occurred_at,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    node_id: str = created.json()["id"]
    return node_id


def _table_with_rows(
    client: TestClient,
    prefix: str,
    auth: dict[str, str],
    area_id: str,
    rows: list[dict[str, Any]],
    name: str = "transactions",
) -> str:
    created = client.post(
        f"{prefix}/work-areas/{area_id}/tables",
        json={"name": name, "schema": _SCHEMA},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    table_id: str = created.json()["id"]
    if rows:
        inserted = client.post(
            f"{prefix}/wa-tables/{table_id}/rows", json={"rows": rows}, headers=auth
        )
        assert inserted.status_code == 200, inserted.text
    return table_id


def _timeline(client: TestClient, prefix: str, headers: dict[str, str], **params: Any) -> Any:
    query: dict[str, Any] = dict(_WINDOW)
    query.update(params)
    return client.get(f"{prefix}/timeline", params=query, headers=headers)


def _slice_by_bucket(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["bucket"]: entry for entry in body["slices"]}


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_bucket_nach_occurred_at_nicht_erfassungsdatum(make_auth_headers: AuthFactory) -> None:
    """Spec-N-Akzeptanz: ein Artifact ueber den Dienstag, HEUTE erfasst
    (created_at=now, weit ausserhalb des Fensters), erscheint unter dem
    Dienstag — und nirgendwo sonst."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Timeline")
            artifact_id = _create_artifact(client, prefix, auth, area_id, occurred_at=_TUESDAY)

            res = _timeline(client, prefix, auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert [entry["bucket"] for entry in body["slices"]] == ["2026-08-04"]
            the_slice = body["slices"][0]
            assert the_slice["items"] == [{"anchor": artifact_id, "kind": "artifact"}]
            assert the_slice["counts"] == {"artifact": 1}
            assert body["unknown"] == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_merge_eine_scheibe_mit_allen_counts(make_auth_headers: AuthFactory) -> None:
    """Spec N: Artifact + Node + Tabellen-Zeilen am selben Tag → EINE Scheibe
    mit allen counts; ein Tag nur mit Notiz (ohne Transaktionen) ist trotzdem
    eine volle Scheibe. Tabellen-Items: EIN `table:<id>`-Anker pro Bucket,
    NIE Row-Anker."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Merge")
            artifact_id = _create_artifact(client, prefix, auth, area_id, occurred_at=_TUESDAY)
            node_id = _create_node(client, prefix, auth, f"artifact:{artifact_id}")
            table_id = _table_with_rows(
                client,
                prefix,
                auth,
                area_id,
                rows=[
                    {"occurred_at": "2026-08-04T10:00:00+00:00", "amount": 12.5, "purpose": "a"},
                    {"occurred_at": "2026-08-04T15:30:00+00:00", "amount": -3, "purpose": "b"},
                ],
            )
            # Tag nur mit Notiz: 2026-08-06 hat weder Node noch Transaktionen.
            lonely_id = _create_artifact(
                client, prefix, auth, area_id, occurred_at="2026-08-06T08:00:00Z"
            )

            res = _timeline(client, prefix, auth, sources=f"artifacts,nodes,table:{table_id}")
            assert res.status_code == 200, res.text
            body = res.json()
            assert [entry["bucket"] for entry in body["slices"]] == ["2026-08-04", "2026-08-06"]

            merged = _slice_by_bucket(body)["2026-08-04"]
            assert merged["counts"] == {"artifact": 1, "node": 1, "table_rows": 2}
            items = {(item["anchor"], item["kind"]) for item in merged["items"]}
            assert items == {
                (artifact_id, "artifact"),
                (f"node:{node_id}", "node"),
                (f"table:{table_id}", "table_rows"),
            }
            # Genau EIN Tabellen-Item trotz zweier Zeilen (keine Row-Anker).
            assert len(merged["items"]) == 3

            lonely = _slice_by_bucket(body)["2026-08-06"]
            assert lonely["counts"] == {"artifact": 1}
            assert lonely["items"] == [{"anchor": lonely_id, "kind": "artifact"}]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_unknown_precision_nur_im_unknown_bucket(make_auth_headers: AuthFactory) -> None:
    """Spec-N-Akzeptanz: `occurred_precision='unknown'` landet NIE in einer
    Datums-Scheibe — nur im unknown-Bucket, auch wenn `occurred_at` weit
    ausserhalb des Fensters liegt (der Bucket ist fensterlos)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Unknown")
            unknown_id = _create_artifact(
                client,
                prefix,
                auth,
                area_id,
                occurred_at="2020-01-01T00:00:00Z",
                occurred_precision="unknown",
            )
            dated_id = _create_artifact(
                client, prefix, auth, area_id, occurred_at="2026-08-05T12:00:00Z"
            )

            res = _timeline(client, prefix, auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert [entry["bucket"] for entry in body["slices"]] == ["2026-08-05"]
            assert body["slices"][0]["items"] == [{"anchor": dated_id, "kind": "artifact"}]
            assert body["unknown"] == [{"anchor": unknown_id, "kind": "artifact"}]
            sliced_anchors = {item["anchor"] for entry in body["slices"] for item in entry["items"]}
            assert unknown_id not in sliced_anchors
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_table_quelle_ohne_grant_404(make_auth_headers: AuthFactory) -> None:
    """Security-Review L1: explizite `table:<id>`-Quelle ohne read-Grant →
    404 wie eine unbekannte Tabelle (kein Existenz-Orakel, kein stilles
    Weglassen). Frueher war das ein 403 `area_forbidden` — die
    Unterscheidung verriet, welche Tabellen-IDs im Workspace existieren."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            table_area = shared_area(client, prefix, auth, "Tabellen-Area")
            other_area = shared_area(client, prefix, auth, "Andere-Area")
            table_id = _table_with_rows(client, prefix, auth, table_area, rows=[])

            agent_id, agent_tok = agent_token(client, prefix, "tl-agent", {}, auth)
            grant(client, prefix, auth, other_area, agent_id, "read")

            denied = _timeline(client, prefix, agent_tok, sources=f"table:{table_id}")
            assert denied.status_code == 404, denied.text

            # Ununterscheidbar von einer Tabelle, die es gar nicht gibt.
            ghost = _timeline(client, prefix, agent_tok, sources=f"table:{_GHOST}")
            assert ghost.status_code == 404, ghost.text
            assert ghost.json()["detail"] == denied.json()["detail"]

            # Mit read-Grant auf die Tabellen-Area laeuft dieselbe Abfrage.
            grant(client, prefix, auth, table_area, agent_id, "read")
            allowed = _timeline(client, prefix, agent_tok, sources=f"table:{table_id}")
            assert allowed.status_code == 200, allowed.text

            missing = _timeline(client, prefix, auth, sources=f"table:{_GHOST}")
            assert missing.status_code == 404, missing.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_agent_sieht_nur_areas_mit_grant(make_auth_headers: AuthFactory) -> None:
    """Spec E: das private Artifact von Agent A fehlt in der Timeline von
    Agent B (Area-Scope IN der SQL); der Mensch (editor+) sieht beide."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, a_tok = agent_token(client, prefix, "tl-a", {"workarea_write": True}, auth)
            b_id, b_tok = agent_token(client, prefix, "tl-b", {"workarea_write": True}, auth)
            shared_id = shared_area(client, prefix, auth, "Geteilt")
            grant(client, prefix, auth, shared_id, b_id, "read")

            private_artifact = _create_artifact(client, prefix, a_tok, None)
            shared_artifact = _create_artifact(client, prefix, auth, shared_id)

            b_view = _timeline(client, prefix, b_tok)
            assert b_view.status_code == 200, b_view.text
            b_slice = _slice_by_bucket(b_view.json())["2026-08-04"]
            assert b_slice["counts"] == {"artifact": 1}
            assert b_slice["items"] == [{"anchor": shared_artifact, "kind": "artifact"}]

            owner_view = _timeline(client, prefix, auth)
            owner_slice = _slice_by_bucket(owner_view.json())["2026-08-04"]
            assert owner_slice["counts"] == {"artifact": 2}
            anchors = {item["anchor"] for item in owner_slice["items"]}
            assert anchors == {private_artifact, shared_artifact}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_node_sichtbarkeit_respektiert(make_auth_headers: AuthFactory) -> None:
    """Spec E: ein Node, dessen Source-Area die private Area von Agent A ist,
    fehlt in der Timeline von Agent B (NOT-EXISTS in der SQL); der Mensch
    sieht ihn."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, a_tok = agent_token(client, prefix, "tl-node-a", {"workarea_write": True}, auth)
            b_id, b_tok = agent_token(client, prefix, "tl-node-b", {"workarea_write": True}, auth)
            shared_id = shared_area(client, prefix, auth, "Node-Geteilt")
            grant(client, prefix, auth, shared_id, b_id, "read")

            private_artifact = _create_artifact(client, prefix, a_tok, None)
            node_id = _create_node(client, prefix, auth, f"artifact:{private_artifact}")

            b_view = _timeline(client, prefix, b_tok, sources="nodes")
            assert b_view.status_code == 200, b_view.text
            assert b_view.json()["slices"] == []

            owner_view = _timeline(client, prefix, auth, sources="nodes")
            owner_slice = _slice_by_bucket(owner_view.json())["2026-08-04"]
            assert owner_slice["counts"] == {"node": 1}
            assert owner_slice["items"] == [{"anchor": f"node:{node_id}", "kind": "node"}]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_week_granularitaet_bucketet_auf_montag(make_auth_headers: AuthFactory) -> None:
    """week: Dienstag+Mittwoch derselben ISO-Woche fallen in den Montags-
    Bucket (Postgres `date_trunc` UND das app-seitige Tabellen-Bucketing),
    die Folgewoche in den naechsten — Tabellen-Item trotzdem nur EINMAL."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Wochen")
            _create_artifact(client, prefix, auth, area_id, occurred_at=_TUESDAY)
            _create_artifact(client, prefix, auth, area_id, occurred_at="2026-08-05T10:00:00Z")
            _create_artifact(client, prefix, auth, area_id, occurred_at="2026-08-11T10:00:00Z")
            table_id = _table_with_rows(
                client,
                prefix,
                auth,
                area_id,
                rows=[
                    {"occurred_at": "2026-08-04T10:00:00+00:00", "amount": 1, "purpose": "a"},
                    {"occurred_at": "2026-08-05T10:00:00+00:00", "amount": 2, "purpose": "b"},
                ],
            )

            res = _timeline(
                client,
                prefix,
                auth,
                granularity="week",
                sources=f"artifacts,table:{table_id}",
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert [entry["bucket"] for entry in body["slices"]] == ["2026-08-03", "2026-08-10"]

            first_week = _slice_by_bucket(body)["2026-08-03"]
            assert first_week["counts"] == {"artifact": 2, "table_rows": 2}
            table_items = [i for i in first_week["items"] if i["kind"] == "table_rows"]
            assert table_items == [{"anchor": f"table:{table_id}", "kind": "table_rows"}]

            second_week = _slice_by_bucket(body)["2026-08-10"]
            assert second_week["counts"] == {"artifact": 1}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_fenster_und_quellen_validierung(make_auth_headers: AuthFactory) -> None:
    """`to` <= `from_` → 422; Fenster > 366 Tage → 422; unbekanntes
    Quellen-Token → 422 (jeweils VOR jedem Datenzugriff)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            inverted = _timeline(
                client,
                prefix,
                auth,
                from_="2026-08-10T00:00:00Z",
                to="2026-08-01T00:00:00Z",
            )
            assert inverted.status_code == 422, inverted.text

            too_wide = _timeline(
                client,
                prefix,
                auth,
                from_="2025-01-01T00:00:00Z",
                to="2026-08-01T00:00:00Z",
            )
            assert too_wide.status_code == 422, too_wide.text
            assert "366" in too_wide.text

            bad_source = _timeline(client, prefix, auth, sources="blobs")
            assert bad_source.status_code == 422, bad_source.text
            assert "blobs" in bad_source.text
    finally:
        cleanup_workspaces([owner])
