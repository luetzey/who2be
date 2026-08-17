"""Integrationstests fuer die Knowledge Base (ADR-0047, WP7 — Spec D + E).

Kritische Invarianten:
- Belegpflicht (Spec D): Node nur mit aufloesbarem `source_ref` (+
  `kb_node_source_area`-Rows aus den Artifact-Areas); Kante ohne Evidence
  bzw. mit unaufloesbarem Evidence-Anker → 422 OHNE Teilzustand
  (COUNT-Assertions auf `kb_edge`/`kb_edge_evidence`).
- Serverlogik O: `co_occurs_with` mit n=19 → 422 `correlation_underpowered`
  (tatsaechliches n im detail), n=20 → 201; neighbors traegt die Fallzahl;
  Hochstufen auf `verified` immer 422; `hypothesis → derived` nur mit Beleg
  ANDERER Art.
- Korrelations-Disziplin (Spec O §10.7, WP18): inhaltliche Kanten
  (`supports`/`belongs_to`/`derived_from`) mit AUSSCHLIESSLICH
  Timeline-url:-Evidence auf einer Seite → 422 `evidence_missing`;
  `hypothesis → derived` an einem Node, dessen einzige Kanten
  `co_occurs_with` sind, verlangt einen Inhalts-Beleg (artifact|blob) —
  ein weiterer url:-Anker → 422 `tier_upgrade_forbidden`
  („Ko-Okkurrenz"), artifact-/sha256-Zweitbeleg → 200; ohne Kanten greift
  nur die Kind-Verschiedenheit.
- Sichtbarkeit (Spec E): Node aus zwei Areas ist nur mit BEIDEN Grants
  sichtbar (GET 404 + 0 Suchtreffer sonst); Capability-Gate: Token nur mit
  `workarea_write` darf keine Nodes anlegen (403 `missing_capability`).
- Index-Trennung (Spec C): ein Begriff, der nur in einem WorkArea-Artifact
  steht, liefert in der KB-Suche 0 Treffer.
- Sprache (0082): die KB stemmt wie die WorkArea-Suche — „Fehlercodes"
  findet „Fehlercode"; unbekannte Sprachen fallen auf `'simple'` zurueck
  (kein Fehler, nur kein Stemming); Migration 0082 zieht Bestandszeilen nach.
"""

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_GHOST = "00000000-0000-0000-0000-000000000000"


def _db_fetchval(sql: str, *args: object) -> Any:
    """Direkter DB-Read fuer Zustands-Assertions (Superuser, an RLS vorbei)."""

    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _db_execute(sql: str, *args: object) -> None:
    """Direkter DB-Write — stellt Altbestand nach bzw. faehrt eine Migration."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    asyncio.run(_run())


def _edge_counts(ws: UUID) -> tuple[int, int]:
    edges = _db_fetchval("SELECT count(*) FROM kb_edge WHERE workspace_id = $1", ws)
    evidence = _db_fetchval("SELECT count(*) FROM kb_edge_evidence WHERE workspace_id = $1", ws)
    return int(edges), int(evidence)


def _agent_token(
    client: TestClient, prefix: str, name: str, policy: dict[str, object], auth: dict[str, str]
) -> tuple[str, dict[str, str]]:
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["id"]
    token = client.post(f"{prefix}/tokens", json={"name": name, "agent_id": agent_id}, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


def _shared_area(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> str:
    created = client.post(f"{prefix}/work-areas", json={"name": name}, headers=auth)
    assert created.status_code == 201, created.text
    area_id: str = created.json()["id"]
    return area_id


def _grant(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, agent_id: str, level: str
) -> None:
    res = client.put(
        f"{prefix}/work-areas/{area_id}/grants/{agent_id}", json={"level": level}, headers=auth
    )
    assert res.status_code == 200, res.text


def _artifact(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, content_md: str
) -> tuple[str, str]:
    """Legt ein doc-Artifact an; Rueckgabe (artifact_id, erster block_id)."""
    created = client.post(
        f"{prefix}/work-areas/{area_id}/artifacts",
        json={"title": "Beleg", "content_md": content_md, "occurred_at": "2026-08-01T12:00:00Z"},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    block_id: str = body["blocks"][0]["block_id"]
    artifact_id: str = body["id"]
    return artifact_id, block_id


def _node(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    source_ref: str,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {
        "content": "Kunde Alpha bevorzugt Textilfarbe Indigo.",
        "tier": "hypothesis",
        "source_ref": source_ref,
        "occurred_at": "2026-08-01T00:00:00Z",
    }
    body.update(overrides)
    return client.post(f"{prefix}/kb/nodes", json=body, headers=headers)


def _co_edge(a_id: str, b_id: str, evidence: str, co_n: int) -> dict[str, Any]:
    return {
        "from_anchor": f"node:{a_id}",
        "to_anchor": f"node:{b_id}",
        "type": "co_occurs_with",
        "evidence_from": [evidence],
        "evidence_to": [evidence],
        "co_query": "SELECT count(*) FROM verkauf WHERE farbe='indigo'",
        "co_n": co_n,
        "co_from": "2026-01-01T00:00:00Z",
        "co_to": "2026-06-30T00:00:00Z",
    }


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_create_node_artifact_quelle_und_source_areas(make_auth_headers: AuthFactory) -> None:
    """Artifact-Beleg → 201 mit `source_ref_kind='artifact'` + Source-Area-Row;
    unaufloesbare Belege (Ghost-Artifact, kaputter sha256) → 422."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Quelle")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Indigo-Notiz.")

            created = _node(client, prefix, auth, f"{artifact_id}#{block_id}")
            assert created.status_code == 201, created.text
            node = created.json()
            assert node["source_ref_kind"] == "artifact"
            assert node["tier"] == "hypothesis" and node["status"] == "live"
            rows = _db_fetchval(
                "SELECT count(*) FROM kb_node_source_area WHERE node_id = $1 AND area_id = $2",
                UUID(node["id"]),
                UUID(area_id),
            )
            assert int(rows) == 1

            # Read-Roundtrip (Mensch editor+ ist unbeschraenkt).
            read = client.get(f"{prefix}/kb/nodes/{node['id']}", headers=auth)
            assert read.status_code == 200 and read.json()["id"] == node["id"]

            # Unaufloesbarer Beleg: Ghost-Artifact bzw. kaputter sha256 → 422.
            ghost = _node(client, prefix, auth, _GHOST)
            assert ghost.status_code == 422, ghost.text
            assert ghost.json()["reason"] == "anchor_unresolvable"
            assert _GHOST in ghost.json()["detail"]
            bad_sha = _node(client, prefix, auth, "sha256:abc")
            assert bad_sha.status_code == 422
            assert bad_sha.json()["reason"] == "anchor_unresolvable"

            # Unbekannter Block eines existierenden Artifacts → ebenfalls 422.
            bad_block = _node(client, prefix, auth, f"{artifact_id}#gibtsnich")
            assert bad_block.status_code == 422
            assert bad_block.json()["reason"] == "anchor_unresolvable"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_edge_belegpflicht_ohne_teilzustand(make_auth_headers: AuthFactory) -> None:
    """Kante ohne `evidence_to` → 422 und KEINE Edge-Row; unaufloesbarer
    Evidence-Anker → 422 + vollstaendiger Rollback (auch keine Evidence)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Kanten")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Kanten-Beleg.")
            evidence = f"{artifact_id}#{block_id}"
            a_id = _node(client, prefix, auth, evidence).json()["id"]
            b_id = _node(
                client, prefix, auth, evidence, content="Zweite Aussage ueber Indigo."
            ).json()["id"]

            # Ohne evidence_to: Pydantic-422 an der Modellgrenze, kein Insert.
            missing = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "supports",
                    "evidence_from": [evidence],
                },
                headers=auth,
            )
            assert missing.status_code == 422, missing.text
            assert _edge_counts(ws) == (0, 0)

            # Unaufloesbarer Evidence-Anker: 422 + Rollback (kein Teilzustand).
            broken = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "supports",
                    "evidence_from": [evidence],
                    "evidence_to": [f"{artifact_id}#gibtsnich"],
                },
                headers=auth,
            )
            assert broken.status_code == 422, broken.text
            assert broken.json()["reason"] == "anchor_unresolvable"
            assert _edge_counts(ws) == (0, 0)

            # Beide Seiten belegt und aufloesbar → 201 (Edge + 2 Evidence).
            ok = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "supports",
                    "evidence_from": [evidence],
                    "evidence_to": [evidence],
                },
                headers=auth,
            )
            assert ok.status_code == 201, ok.text
            edge = ok.json()
            assert edge["from_node_id"] == a_id and edge["to_node_id"] == b_id
            assert edge["evidence_from"] == [evidence] and edge["evidence_to"] == [evidence]
            assert _edge_counts(ws) == (1, 2)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_co_occurs_fallzahl_und_neighbors(make_auth_headers: AuthFactory) -> None:
    """co_n=19 → 422 `correlation_underpowered` mit „19" im detail (VOR dem
    DB-CHECK); co_n=20 → 201; neighbors traegt die Fallzahl IMMER mit."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Korrelation")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Zahlen-Beleg.")
            evidence = f"{artifact_id}#{block_id}"
            a_id = _node(client, prefix, auth, evidence).json()["id"]
            b_id = _node(
                client, prefix, auth, evidence, content="Regen korreliert mit Indigo-Kaeufen."
            ).json()["id"]

            underpowered = client.post(
                f"{prefix}/kb/edges", json=_co_edge(a_id, b_id, evidence, 19), headers=auth
            )
            assert underpowered.status_code == 422, underpowered.text
            problem = underpowered.json()
            assert problem["reason"] == "correlation_underpowered"
            assert "19" in problem["detail"]
            assert _edge_counts(ws) == (0, 0)

            ok = client.post(
                f"{prefix}/kb/edges", json=_co_edge(a_id, b_id, evidence, 20), headers=auth
            )
            assert ok.status_code == 201, ok.text
            assert ok.json()["co_n"] == 20

            neighbors = client.get(
                f"{prefix}/kb/neighbors", params={"anchor": f"node:{a_id}"}, headers=auth
            )
            assert neighbors.status_code == 200, neighbors.text
            hits = neighbors.json()
            assert [n["node"]["id"] for n in hits] == [b_id]
            assert hits[0]["edge_type"] == "co_occurs_with"
            assert hits[0]["direction"] == "out"
            assert hits[0]["co_n"] == 20

            # Gegenrichtung: b sieht a als eingehende Kante, Fallzahl dabei.
            back = client.get(
                f"{prefix}/kb/neighbors", params={"anchor": f"node:{b_id}"}, headers=auth
            )
            assert [n["direction"] for n in back.json()] == ["in"]
            assert back.json()[0]["co_n"] == 20
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_content_kanten_verlangen_beleg_jenseits_der_timeline(
    make_auth_headers: AuthFactory,
) -> None:
    """Spec O §10.7 (WP18, Punkt 1): eine inhaltliche Kante, deren Evidence auf
    einer Seite NUR aus Timeline-url:-Ankern besteht → 422 `evidence_missing`
    ohne Teilzustand; ein Inhalts-Anker NEBEN dem Timeline-Verweis genuegt;
    fuer `co_occurs_with` ist reine Timeline-Evidence der Normalfall."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    timeline = f"url:https://who2be.example{prefix}/timeline?from=2026-01-01&to=2026-06-30"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Zeitachse")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Inhalts-Beleg.")
            anchor = f"{artifact_id}#{block_id}"
            a_id = _node(client, prefix, auth, anchor).json()["id"]
            b_id = _node(
                client, prefix, auth, anchor, content="Regentage im ersten Halbjahr."
            ).json()["id"]

            # supports mit NUR Timeline-Evidence auf der from-Seite → 422.
            blocked = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "supports",
                    "evidence_from": [timeline],
                    "evidence_to": [anchor],
                },
                headers=auth,
            )
            assert blocked.status_code == 422, blocked.text
            problem = blocked.json()
            assert problem["reason"] == "evidence_missing"
            assert "co_occurs_with" in problem["detail"]
            assert _edge_counts(ws) == (0, 0)

            # belongs_to, beide Seiten nur Timeline-Verweise → ebenfalls 422.
            blocked_both = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "belongs_to",
                    "evidence_from": [timeline],
                    "evidence_to": [timeline],
                },
                headers=auth,
            )
            assert blocked_both.status_code == 422
            assert blocked_both.json()["reason"] == "evidence_missing"
            assert _edge_counts(ws) == (0, 0)

            # Ein Inhalts-Anker NEBEN dem Timeline-Verweis → 201.
            ok = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{a_id}",
                    "to_anchor": f"node:{b_id}",
                    "type": "supports",
                    "evidence_from": [timeline, anchor],
                    "evidence_to": [anchor],
                },
                headers=auth,
            )
            assert ok.status_code == 201, ok.text

            # co_occurs_with lebt von der Zeitachse: reine Timeline-Evidence
            # plus co_-Felder → 201 (die Korrelation IST die Behauptung).
            co = client.post(
                f"{prefix}/kb/edges", json=_co_edge(a_id, b_id, timeline, 20), headers=auth
            )
            assert co.status_code == 201, co.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_tier_upgrade_bei_nur_ko_okkurrenz_belegen(make_auth_headers: AuthFactory) -> None:
    """Spec-Akzeptanz O (WP18, Punkt 2, starke Form): ein hypothesis-Node aus
    Korrelation (einzige Kanten: co_occurs_with) steigt NICHT auf derived,
    solange kein Inhalts-Beleg (artifact|blob) existiert — ein weiterer
    url:-Anker → 422; ein artifact- oder sha256-Zweitbeleg → 200; ohne
    Kanten greift die Regel nicht (dort zaehlt nur Kind-Verschiedenheit)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    timeline = f"url:https://who2be.example{prefix}/timeline?from=2026-01-01&to=2026-06-30"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Ko-Okkurrenz")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Inhalts-Beleg.")
            anchor = f"{artifact_id}#{block_id}"
            b_id = _node(
                client, prefix, auth, anchor, content="Indigo-Kaeufe im Fruehjahr."
            ).json()["id"]

            # Node A haengt aus Korrelation heraus NUR an einer co-Kante.
            a_id = _node(
                client,
                prefix,
                auth,
                "url:https://example.org/regenstatistik",
                content="Regen faellt mit Indigo-Kaeufen zusammen.",
            ).json()["id"]
            co = client.post(
                f"{prefix}/kb/edges", json=_co_edge(a_id, b_id, timeline, 20), headers=auth
            )
            assert co.status_code == 201, co.text

            # Zweitbeleg WIEDER nur url: → 422 mit dem Ko-Okkurrenz-Detail
            # (die Korrelations-Regel greift VOR der Kind-Verschiedenheit).
            url_only = client.patch(
                f"{prefix}/kb/nodes/{a_id}",
                json={"tier": "derived", "additional_source_ref": "url:https://example.org/b"},
                headers=auth,
            )
            assert url_only.status_code == 422, url_only.text
            problem = url_only.json()
            assert problem["reason"] == "tier_upgrade_forbidden"
            assert "Ko-Okkurrenz" in problem["detail"]

            # artifact-Zweitbeleg IST ein Inhalts-Beleg jenseits der
            # Korrelation → 200, obwohl alle Kanten co_occurs_with sind.
            upgraded = client.patch(
                f"{prefix}/kb/nodes/{a_id}",
                json={"tier": "derived", "additional_source_ref": anchor},
                headers=auth,
            )
            assert upgraded.status_code == 200, upgraded.text
            assert upgraded.json()["tier"] == "derived"

            # sha256-Zweitbeleg (Blob im Katalog) zaehlt ebenfalls als
            # Inhalts-Beleg → 200.
            c_id = _node(
                client,
                prefix,
                auth,
                "url:https://example.org/temperaturreihe",
                content="Temperatur faellt mit Indigo-Kaeufen zusammen.",
            ).json()["id"]
            co_c = client.post(
                f"{prefix}/kb/edges", json=_co_edge(c_id, b_id, timeline, 20), headers=auth
            )
            assert co_c.status_code == 201, co_c.text
            sha = "ab" * 32
            _db_fetchval(
                "INSERT INTO wa_blob (workspace_id, sha256, size_bytes, media_type, storage_key) "
                "VALUES ($1, $2, 42, 'application/pdf', $3) RETURNING sha256",
                ws,
                sha,
                f"blobs/{ws}/{sha}",
            )
            via_blob = client.patch(
                f"{prefix}/kb/nodes/{c_id}",
                json={"tier": "derived", "additional_source_ref": f"sha256:{sha}"},
                headers=auth,
            )
            assert via_blob.status_code == 200, via_blob.text
            assert via_blob.json()["tier"] == "derived"

            # Ohne Kanten greift die Regel nicht: url + url scheitert an der
            # Kind-Gleichheit (Detail OHNE Ko-Okkurrenz-Bezug).
            d_id = _node(
                client,
                prefix,
                auth,
                "url:https://example.org/d",
                content="These ganz ohne Kanten.",
            ).json()["id"]
            same_kind = client.patch(
                f"{prefix}/kb/nodes/{d_id}",
                json={"tier": "derived", "additional_source_ref": "url:https://example.org/e"},
                headers=auth,
            )
            assert same_kind.status_code == 422, same_kind.text
            detail = same_kind.json()["detail"]
            assert "ANDERER Art" in detail and "Ko-Okkurrenz" not in detail
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_tier_regeln(make_auth_headers: AuthFactory) -> None:
    """Hochstufen auf `verified` per Update → IMMER 422 (auch Mensch);
    `hypothesis → derived` ohne additional → 422, mit gleichartigem Beleg →
    422, mit andersartigem Beleg → 200; Downgrade frei."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Tier")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Tier-Beleg.")
            anchor = f"{artifact_id}#{block_id}"

            derived_id = _node(client, prefix, auth, anchor, tier="derived").json()["id"]
            upgrade = client.patch(
                f"{prefix}/kb/nodes/{derived_id}", json={"tier": "verified"}, headers=auth
            )
            assert upgrade.status_code == 422, upgrade.text
            assert upgrade.json()["reason"] == "tier_upgrade_forbidden"

            hypo_id = _node(
                client, prefix, auth, anchor, content="Indigo-These ohne Zweitbeleg."
            ).json()["id"]
            no_additional = client.patch(
                f"{prefix}/kb/nodes/{hypo_id}", json={"tier": "derived"}, headers=auth
            )
            assert no_additional.status_code == 422
            assert no_additional.json()["reason"] == "tier_upgrade_forbidden"

            # Gleicher Beleg-Kind (artifact → artifact): ebenfalls 422.
            same_kind = client.patch(
                f"{prefix}/kb/nodes/{hypo_id}",
                json={"tier": "derived", "additional_source_ref": anchor},
                headers=auth,
            )
            assert same_kind.status_code == 422
            assert same_kind.json()["reason"] == "tier_upgrade_forbidden"

            # Beleg ANDERER Art (url statt artifact) → 200, tier=derived.
            upgraded = client.patch(
                f"{prefix}/kb/nodes/{hypo_id}",
                json={
                    "tier": "derived",
                    "additional_source_ref": "url:https://example.org/zweitbeleg",
                },
                headers=auth,
            )
            assert upgraded.status_code == 200, upgraded.text
            assert upgraded.json()["tier"] == "derived"

            # Downgrade ist frei.
            downgraded = client.patch(
                f"{prefix}/kb/nodes/{derived_id}", json={"tier": "hypothesis"}, headers=auth
            )
            assert downgraded.status_code == 200
            assert downgraded.json()["tier"] == "hypothesis"

            # Unbekannter Node → 404 (kein Existenz-Leak).
            assert (
                client.patch(
                    f"{prefix}/kb/nodes/{_GHOST}", json={"tier": "hypothesis"}, headers=auth
                ).status_code
                == 404
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_capability_gates(make_auth_headers: AuthFactory) -> None:
    """Spec E: Token nur mit `workarea_write` → 403 bei create_node; `kb_write`
    ohne `kb_edge_write` → 403 bei create_edge; mit Capability klappt es."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Gates")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Gate-Beleg.")
            anchor = f"{artifact_id}#{block_id}"

            # Nur workarea_write: KB-Schreiben bleibt zu (403, kein 404/422).
            wa_id, wa_tok = _agent_token(
                client, prefix, "kb-nur-wa", {"workarea_write": True}, auth
            )
            _grant(client, prefix, auth, area_id, wa_id, "write")
            blocked = _node(client, prefix, wa_tok, anchor)
            assert blocked.status_code == 403, blocked.text
            assert blocked.json()["reason"] == "missing_capability"

            # kb_write reicht fuer Nodes, nicht fuer Kanten.
            kb_id, kb_tok = _agent_token(client, prefix, "kb-nodes", {"kb_write": True}, auth)
            _grant(client, prefix, auth, area_id, kb_id, "read")
            created = _node(client, prefix, kb_tok, anchor)
            assert created.status_code == 201, created.text
            node_id = created.json()["id"]
            edge = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{node_id}",
                    "to_anchor": anchor,
                    "type": "supports",
                    "evidence_from": [anchor],
                    "evidence_to": [anchor],
                },
                headers=kb_tok,
            )
            assert edge.status_code == 403
            assert edge.json()["reason"] == "missing_capability"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_sichtbarkeit_node_aus_zwei_areas(make_auth_headers: AuthFactory) -> None:
    """Spec E: ein Node mit Quellen aus Areas A+B ist fuer einen Agenten mit
    nur A unsichtbar (GET 404, kb-search 0) und erst mit BEIDEN Grants
    sichtbar; der Mensch (editor+) sieht ihn immer."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_a = _shared_area(client, prefix, auth, "Area-A")
            area_b = _shared_area(client, prefix, auth, "Area-B")
            art_a, block_a = _artifact(client, prefix, auth, area_a, "Beleg in A.")
            art_b, block_b = _artifact(client, prefix, auth, area_b, "Beleg in B.")

            created = _node(
                client,
                prefix,
                auth,
                f"{art_a}#{block_a}",
                content="Grenzueberschreitende Marmeladenpreise steigen.",
                content_ref=f"{art_b}#{block_b}",
            )
            assert created.status_code == 201, created.text
            node_id = created.json()["id"]
            rows = _db_fetchval(
                "SELECT count(*) FROM kb_node_source_area WHERE node_id = $1", UUID(node_id)
            )
            assert int(rows) == 2  # A und B materialisiert

            nur_a_id, nur_a = _agent_token(client, prefix, "kb-nur-a", {}, auth)
            _grant(client, prefix, auth, area_a, nur_a_id, "read")
            beide_id, beide = _agent_token(client, prefix, "kb-beide", {}, auth)
            _grant(client, prefix, auth, area_a, beide_id, "read")
            _grant(client, prefix, auth, area_b, beide_id, "read")

            # Nur A: GET 404 (kein Existenz-Leak) + 0 Suchtreffer.
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=nur_a).status_code == 404
            search_a = client.get(
                f"{prefix}/kb-search", params={"q": "Marmeladenpreise"}, headers=nur_a
            )
            assert search_a.status_code == 200 and search_a.json() == []

            # A+B: sichtbar — GET 200 und genau ein Treffer mit node:-Anker.
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=beide).status_code == 200
            search_beide = client.get(
                f"{prefix}/kb-search", params={"q": "Marmeladenpreise"}, headers=beide
            )
            hits = search_beide.json()
            assert [h["node_id"] for h in hits] == [node_id]
            assert hits[0]["anchor"] == f"node:{node_id}"
            assert len(hits[0]["snippet"]) <= 200

            # Mensch (editor+): immer sichtbar.
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_kb_suche_findet_keine_workarea_inhalte(make_auth_headers: AuthFactory) -> None:
    """Spec C (Index-Trennung): ein Begriff, der NUR in einem WorkArea-Artifact
    steht, liefert in der KB-Suche 0 Treffer — per Konstruktion."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Trennung")
            _artifact(client, prefix, auth, area_id, "Das Zebrastreifenprojekt startet morgen.")

            search = client.get(
                f"{prefix}/kb-search", params={"q": "Zebrastreifenprojekt"}, headers=auth
            )
            assert search.status_code == 200 and search.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_kb_suche_findet_deutsche_wortformen(make_auth_headers: AuthFactory) -> None:
    """Die KB stemmt wie die WorkArea-Suche (Befund B, 2026-08-16).

    Vorher indizierte `kb_node.search` mit `'simple'` — kein Stemming. Eine
    Aussage ueber den „Fehlercode" war damit fuer eine Suche nach
    „Fehlercodes" unsichtbar, waehrend `search_workarea` denselben Text
    fand (`wa_chunk` bildet ueber `locale` auf `german` ab). Fuer einen
    Agenten ist dieser Unterschied nicht lesbar: kein Treffer sieht aus wie
    kein Wissen.

    Geprueft wird in BEIDE Richtungen — Singular findet Plural und
    umgekehrt —, damit der Test nicht zufaellig an einer Richtung haengt.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Sprache")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Beleg.")
            node_id = _node(
                client,
                prefix,
                auth,
                f"{artifact_id}#{block_id}",
                content="Der Fehlercode E-102 betrifft den Vorlagendruck.",
            ).json()["id"]

            for begriff in ("Fehlercodes", "Fehlercode", "Vorlagendrucks"):
                hits = client.get(f"{prefix}/kb-search", params={"q": begriff}, headers=auth).json()
                assert [h["node_id"] for h in hits] == [node_id], begriff

            # Kein Freibrief: ein unbeteiligtes Wort trifft weiterhin nicht.
            leer = client.get(f"{prefix}/kb-search", params={"q": "Buchhaltung"}, headers=auth)
            assert leer.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_kb_suche_faellt_bei_unbekannter_sprache_auf_simple(
    make_auth_headers: AuthFactory,
) -> None:
    """Unbekannte Content-Sprache → `'simple'`: exakte Treffer, kein Fehler.

    Die Abbildung kennt `de` und `en`; alles andere faellt bewusst auf
    `'simple'` zurueck (Muster `wa_chunk`/0076). Wichtig ist, dass der
    Fallback KEIN Fehler ist — die Suche funktioniert, sie stemmt nur nicht.

    `content_locale` wird direkt in der DB gesetzt, NICHT ueber
    `setup_workspace(content_locale='fr')`: die App-Schicht kennt nur de/en
    (`builder_content.SUPPORTED_LOCALES`) und koennte einen fr-Workspace gar
    nicht seeden. Die DB-Schicht ist bewusst offen (0069: kein CHECK) — und
    genau dort sitzt der Fallback, den dieser Test prueft.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    _db_execute("UPDATE workspace SET content_locale = 'fr' WHERE id = $1", ws)
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Sprache-FR")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Beleg.")
            node_id = _node(
                client,
                prefix,
                auth,
                f"{artifact_id}#{block_id}",
                content="Le code erreur E-102 concerne l'impression.",
            ).json()["id"]
            assert _db_fetchval("SELECT locale FROM kb_node WHERE id = $1", UUID(node_id)) == "fr"

            treffer = client.get(f"{prefix}/kb-search", params={"q": "erreur"}, headers=auth)
            assert treffer.status_code == 200
            assert [h["node_id"] for h in treffer.json()] == [node_id]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_migration_0082_zieht_bestandsnodes_nach(make_auth_headers: AuthFactory) -> None:
    """Bestandsdaten aus der Zeit vor der Sprach-Spalte.

    Nachgestellt wird eine Zeile, deren `locale` nicht zum Workspace passt
    (vor 0082 gab es die Spalte gar nicht, der Effekt ist derselbe: der
    Index steht auf der falschen Config). Die Migrationsdatei selbst laeuft
    darauf — sie backfillt aus `workspace.content_locale` und baut die
    generierte Spalte neu; ein zweiter Lauf ist ein No-op.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Altbestand")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Beleg.")
            node_id = _node(
                client,
                prefix,
                auth,
                f"{artifact_id}#{block_id}",
                content="Die Wartung der Presse ist faellig.",
            ).json()["id"]

            _db_execute("UPDATE kb_node SET locale = 'xx' WHERE id = $1", UUID(node_id))
            assert (
                client.get(f"{prefix}/kb-search", params={"q": "Wartungen"}, headers=auth).json()
                == []
            )

            _db_execute((MIGRATIONS_DIR / "0082_kb_node_locale.sql").read_text(encoding="utf-8"))

            assert _db_fetchval("SELECT locale FROM kb_node WHERE id = $1", UUID(node_id)) == "de"
            hits = client.get(f"{prefix}/kb-search", params={"q": "Wartungen"}, headers=auth).json()
            assert [h["node_id"] for h in hits] == [node_id]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_derived_from_propagiert_source_areas(make_auth_headers: AuthFactory) -> None:
    """`derived_from` UNIONt die Source-Areas des Parents (to) monoton ins
    Kind (from): ein vorher quellenloser (fuer alle sichtbarer) Node wird
    fuer Agenten ohne Grant auf die Parent-Area unsichtbar."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "KB-Ableitung")
            artifact_id, block_id = _artifact(client, prefix, auth, area_id, "Parent-Beleg.")
            evidence = f"{artifact_id}#{block_id}"

            parent_id = _node(client, prefix, auth, evidence).json()["id"]
            # Kind mit url-Beleg: zunaechst OHNE Source-Areas → fuer alle lesbar.
            child_id = _node(
                client,
                prefix,
                auth,
                "url:https://example.org/ableitung",
                content="Abgeleitete Indigo-These.",
            ).json()["id"]
            _, kein_grant = _agent_token(client, prefix, "kb-kein-grant", {}, auth)
            assert (
                client.get(f"{prefix}/kb/nodes/{child_id}", headers=kein_grant).status_code == 200
            )

            edge = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{child_id}",
                    "to_anchor": f"node:{parent_id}",
                    "type": "derived_from",
                    "evidence_from": [evidence],
                    "evidence_to": [evidence],
                },
                headers=auth,
            )
            assert edge.status_code == 201, edge.text

            child_areas = _db_fetchval(
                "SELECT count(*) FROM kb_node_source_area WHERE node_id = $1 AND area_id = $2",
                UUID(child_id),
                UUID(area_id),
            )
            assert int(child_areas) == 1  # Parent-Area ist ins Kind gewandert.
            # Sichtbarkeits-Folge: ohne Grant auf die Area ist das Kind nun 404.
            assert (
                client.get(f"{prefix}/kb/nodes/{child_id}", headers=kein_grant).status_code == 404
            )
    finally:
        cleanup_workspaces([owner])
