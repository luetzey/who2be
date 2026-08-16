"""End-to-End-Durchlauf der WorkArea-/KB-Achse aus AGENTEN-Sicht (ADR-0047).

Anders als die fachlichen Tests daneben (`test_wa_artifacts.py`, `test_kb.py`)
prueft dieser Test keine einzelne Invariante, sondern **die Kette**, die ein
Agent ueber MCP tatsaechlich laeuft: Artifact anlegen → Anker lesen →
anhaengen → nebenlaeufig patchen → wiederfinden → belegte Aussage anlegen →
Kante ziehen → Nachbarn abfragen. Genau diese Reihenfolge scheitert, wenn
zwei fuer sich korrekte Bausteine nicht zusammenpassen (etwa: der Anker aus
einem Suchtreffer laesst sich nicht als KB-Beleg verwenden).

Die Gegenproben sind der eigentliche Zweck — sie belegen, dass die
Leitplanken scharf sind und nicht nur der Happy Path funktioniert:

- veraltete `expected_rev` → 409 `rev_conflict` MIT aktueller rev,
- unaufloesbarer Beleg am Node → 422 `anchor_unresolvable`,
- Kante mit LEERER Evidence-Seite → 422 vom Pydantic-Modell
  (`min_length=1`) — also OHNE `reason`, das ist die aeussere Schranke,
- Kante mit vorhandener, aber ins Leere zeigender Evidence → 422 aus dem
  SERVICE; danach existiert **keine halbe Kante** (der Fall, den ein Agent
  mit halluzinierten IDs wirklich produziert),
- `co_occurs_with` mit n=19 → 422 `correlation_underpowered` mit dem
  tatsaechlichen n im detail.

Die Zweistufigkeit der Belegpflicht (Modell vor Service) ist bewusst
mitgetestet: wer nur auf `reason` prueft, uebersieht, dass der eine Fall
die Fachlogik nie erreicht.

Laeuft mit einem agent-gebundenen Token — also durch dieselben Capability-
und Grant-Gates wie ein echter MCP-Aufruf, nicht am Menschen-Pfad vorbei.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

# Policy eines Fach-Agenten, dem der Betreiber die Arbeitsbereichs-Rechte
# gegeben hat — genau die drei Capabilities aus dem UI-Policy-Editor.
_AGENT_POLICY: dict[str, object] = {
    "workarea_write": True,
    "kb_write": True,
    "kb_edge_write": True,
}

_MD_A = (
    "# Preisentwicklung 2026\n\n"
    "Der Listenpreis des Basistarifs stieg zum 1. Juli 2026 von 49 auf 53 Euro.\n\n"
    "Die Erhoehung wurde im Kundenbrief mit gestiegenen Infrastrukturkosten begruendet."
)
_MD_B = "# Kuendigungen Q3 2026\n\nIm dritten Quartal 2026 kuendigten 41 Kunden des Basistarifs."


def _agent_token(
    client: TestClient, prefix: str, name: str, auth: dict[str, str]
) -> dict[str, str]:
    """Legt einen Agenten mit Arbeitsbereichs-Rechten an und bindet einen Token daran."""
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": _AGENT_POLICY}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    token = client.post(
        f"{prefix}/tokens", json={"name": name, "agent_id": agent.json()["id"]}, headers=auth
    )
    assert token.status_code == 201, token.text
    return {"Authorization": f"Bearer {token.json()['token']}"}


def _create_artifact(
    client: TestClient, prefix: str, agent_auth: dict[str, str], title: str, md: str, when: str
) -> dict[str, Any]:
    """Legt ein doc-Artifact in der PRIVATEN Area des Agenten an (`area_id` weggelassen)."""
    created = client.post(
        f"{prefix}/artifacts",
        json={
            "title": title,
            "content_md": md,
            # Pflicht-Input ohne now()-Fallback: der fachliche Zeitpunkt ist
            # eine Aussage, die der Server nicht erfinden darf.
            "occurred_at": when,
            "occurred_precision": "day",
        },
        headers=agent_auth,
    )
    assert created.status_code == 201, created.text
    body: dict[str, Any] = created.json()
    return body


@pytest.mark.integration
def test_agent_walkthrough_workarea_to_knowledge_base(
    migrated_db: None,  # noqa: ARG001 — Fixture-Reihenfolge
    patched_jwt_secret: str,  # noqa: ARG001
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)
    prefix = f"/v1/workspaces/{workspace_id}"
    human = make_auth_headers(owner)

    try:
        with TestClient(app) as client:
            agent = _agent_token(client, prefix, "Walkthrough-Agent", human)

            # --- A1: Artifact anlegen, private Area entsteht implizit ---------
            first = _create_artifact(
                client, prefix, agent, "Preisentwicklung", _MD_A, "2026-07-01T00:00:00Z"
            )
            artifact_id = first["id"]
            assert first["rev"] == 1
            assert first["type"] == "doc"

            # --- A2: Markdown-Read traegt Anker; ?anchor= liefert NUR den Block
            full = client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=agent)
            assert full.status_code == 200, full.text
            markdown = full.json()["markdown"]
            assert "[#" in markdown, markdown
            # Anker des Absatzes mit der Preisaussage herausziehen.
            block_line = next(line for line in markdown.splitlines() if "49 auf 53 Euro" in line)
            block_id = block_line.rsplit("[#", 1)[1].rstrip("]")

            single = client.get(
                f"{prefix}/wa-artifacts/{artifact_id}", params={"anchor": block_id}, headers=agent
            )
            assert single.status_code == 200, single.text
            only = single.json()["markdown"]
            assert "49 auf 53 Euro" in only
            # Der Sinn der Anker-Sprache: NUR der Block, nicht das Dokument.
            assert "Kundenbrief" not in only, only

            # --- A3: append ist lockfrei, rev steigt --------------------------
            appended = client.post(
                f"{prefix}/wa-artifacts/{artifact_id}/append",
                json={"content_md": "Nachtrag: Bestandskunden behalten den alten Preis bis 2027."},
                headers=agent,
            )
            assert appended.status_code == 200, appended.text
            current_rev = appended.json()["rev"]
            assert current_rev == 2

            # --- A4 (Gegenprobe): veraltete expected_rev → 409 mit aktueller rev
            stale = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={
                    "anchor": block_id,
                    "op": "replace",
                    "content_md": "Ueberschrieben.",
                    "expected_rev": 1,  # veraltet — inzwischen steht rev auf 2
                },
                headers=agent,
            )
            assert stale.status_code == 409, stale.text
            problem = stale.json()
            assert problem["reason"] == "rev_conflict", problem
            # Die aktuelle rev MUSS im Fehler stehen — sonst kann ein Agent
            # nicht gezielt erneut versuchen, sondern muesste raten.
            assert str(current_rev) in problem["detail"], problem

            # --- A5: Suche liefert Anker + Snippet, nicht das Dokument --------
            found = client.get(
                f"{prefix}/workarea-search", params={"q": "Listenpreis"}, headers=agent
            )
            assert found.status_code == 200, found.text
            hits = found.json()
            assert hits, "Die Suche findet die frisch angelegte Passage nicht."
            hit = hits[0]
            assert hit["artifact_id"] == artifact_id
            assert hit["anchor"] == f"{artifact_id}#{hit['block_id']}"
            assert hit["snippet"]

            # --- A6: zweites Artifact fuer die Kante --------------------------
            second = _create_artifact(
                client, prefix, agent, "Kuendigungen", _MD_B, "2026-09-30T00:00:00Z"
            )

            # --- B1: belegte Aussage — der Suchtreffer-Anker IST der Beleg ----
            node_a = client.post(
                f"{prefix}/kb/nodes",
                json={
                    "content": "Der Basistarif verteuerte sich zum 01.07.2026 um 4 Euro.",
                    "tier": "hypothesis",
                    "source_ref": f"artifact:{hit['anchor']}",
                    "occurred_at": "2026-07-01T00:00:00Z",
                },
                headers=agent,
            )
            assert node_a.status_code == 201, node_a.text
            node_a_id = node_a.json()["id"]
            # Die Beleg-ART leitet der SERVER ab — kein Client-Input.
            assert node_a.json()["source_ref_kind"] == "artifact"

            # --- B2 (Gegenprobe): unaufloesbarer Beleg → 422 ------------------
            ghost = client.post(
                f"{prefix}/kb/nodes",
                json={
                    "content": "Frei erfundene Aussage ohne Grundlage.",
                    "tier": "hypothesis",
                    "source_ref": "artifact:00000000-0000-0000-0000-000000000000#deadbeef",
                    "occurred_at": "2026-07-01T00:00:00Z",
                },
                headers=agent,
            )
            assert ghost.status_code == 422, ghost.text
            assert ghost.json()["reason"] == "anchor_unresolvable", ghost.json()

            # --- B3: zweite Aussage auf dem zweiten Artifact ------------------
            node_b = client.post(
                f"{prefix}/kb/nodes",
                json={
                    "content": "Im Q3 2026 kuendigten 41 Basistarif-Kunden.",
                    "tier": "hypothesis",
                    "source_ref": f"artifact:{second['id']}",
                    "occurred_at": "2026-09-30T00:00:00Z",
                },
                headers=agent,
            )
            assert node_b.status_code == 201, node_b.text
            node_b_id = node_b.json()["id"]

            # --- B4a (Gegenprobe): Kante ohne Evidence auf einer Seite --------
            # Die Belegpflicht ist ZWEISTUFIG. Die leere Liste faengt schon das
            # Pydantic-Modell (`min_length=1`) — die Antwort traegt deshalb die
            # FastAPI-Validierungsform OHNE `reason`, nicht die Problem-Details
            # des Service. Das ist die aeussere Schranke, nicht die Fachlogik.
            naked = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{node_a_id}",
                    "to_anchor": f"node:{node_b_id}",
                    "type": "supports",
                    "evidence_from": [hit["anchor"]],
                    "evidence_to": [],
                },
                headers=agent,
            )
            assert naked.status_code == 422, naked.text
            assert "reason" not in naked.json(), naked.json()

            # --- B4b (Gegenprobe): Evidence da, aber nicht aufloesbar ---------
            # Erst hier greift der SERVICE: die Anker sind formal in Ordnung,
            # zeigen aber ins Leere. Das ist der Fall, den ein Agent mit
            # halluzinierten IDs tatsaechlich produziert.
            ghost_evidence = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{node_a_id}",
                    "to_anchor": f"node:{node_b_id}",
                    "type": "supports",
                    "evidence_from": [hit["anchor"]],
                    "evidence_to": ["00000000-0000-0000-0000-000000000000#deadbeef"],
                },
                headers=agent,
            )
            assert ghost_evidence.status_code == 422, ghost_evidence.text
            assert ghost_evidence.json()["reason"] in {
                "anchor_unresolvable",
                "evidence_missing",
            }, ghost_evidence.json()

            # Kein Teilzustand: nach BEIDEN Ablehnungen existiert keine halbe
            # Kante — sonst haette die zweite Pruefung nach einem Teil-Insert
            # gegriffen und den Node bereits verknuepft zurueckgelassen.
            after_fail = client.get(
                f"{prefix}/kb/neighbors", params={"anchor": f"node:{node_a_id}"}, headers=agent
            )
            assert after_fail.status_code == 200, after_fail.text
            assert after_fail.json() == [], after_fail.json()

            # --- B5 (Gegenprobe O): Korrelation unter der Mindest-Fallzahl ----
            weak = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{node_a_id}",
                    "to_anchor": f"node:{node_b_id}",
                    "type": "co_occurs_with",
                    "evidence_from": [hit["anchor"]],
                    "evidence_to": [f"artifact:{second['id']}"],
                    "co_query": "Preiserhoehung und Kuendigung im selben Quartal",
                    "co_n": 19,  # eins unter der Grenze
                    "co_from": 12,
                    "co_to": 15,
                },
                headers=agent,
            )
            assert weak.status_code == 422, weak.text
            assert weak.json()["reason"] == "correlation_underpowered", weak.json()
            # Das tatsaechliche n gehoert in die Meldung — sonst weiss der
            # Agent nicht, wie weit er von der Schwelle entfernt ist.
            assert "19" in weak.json()["detail"], weak.json()

            # --- B6: gueltige Kante ------------------------------------------
            edge = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{node_a_id}",
                    "to_anchor": f"node:{node_b_id}",
                    "type": "supports",
                    "evidence_from": [hit["anchor"]],
                    "evidence_to": [f"artifact:{second['id']}"],
                },
                headers=agent,
            )
            assert edge.status_code == 201, edge.text

            # --- B7: KB-Suche findet die Aussage, NIE das Rohmaterial ---------
            kb_hits = client.get(f"{prefix}/kb-search", params={"q": "Basistarif"}, headers=agent)
            assert kb_hits.status_code == 200, kb_hits.text
            found_ids = {h["node_id"] for h in kb_hits.json()}
            assert node_a_id in found_ids, kb_hits.json()
            # Getrennte Indizes: ein WorkArea-Treffer hat hier nichts zu suchen.
            for h in kb_hits.json():
                assert h["anchor"].startswith("node:"), h

            # --- B8: Nachbarn tragen Typ und Richtung ------------------------
            neighbours = client.get(
                f"{prefix}/kb/neighbors", params={"anchor": f"node:{node_a_id}"}, headers=agent
            )
            assert neighbours.status_code == 200, neighbours.text
            assert len(neighbours.json()) == 1, neighbours.json()
            only_neighbour = neighbours.json()[0]
            assert only_neighbour["node"]["id"] == node_b_id
            assert only_neighbour["edge_type"] == "supports"
            assert only_neighbour["direction"] == "out"
    finally:
        cleanup_workspaces([owner])
