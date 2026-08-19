"""Integrationstests fuer `POST /wa-tables/{id}/save-result` (WP16, M-Ersatz).

Kritische Invarianten (Entscheidung 7 / Spec §10.6):

- Der SERVER friert Query + Ergebnis als doc-Artifact ein: der Markdown-Body
  enthaelt das SQL VERBATIM und die von der Engine gerenderten Zahlen —
  „Keine Zahl stammt aus Modell-Text" (Summen-Assertion aus dem Result-Set).
- Das Artifact entsteht in DERSELBEN Area wie die Tabelle (type=doc,
  `occurred_at` aus dem Request, Default-Praezision `day`) und ist sofort
  ueber die WorkArea-Suche auffindbar (Chunk-Sync im Anlage-Pfad).
- Schreibversuche (DROP) → 403 `query_not_readonly`, Syntaxfehler → 400 —
  in beiden Faellen entsteht KEIN Artifact (COUNT-Assertion).
- `limit` < Ergebniszeilen → gekuerztes Ergebnis mit Hinweis im Intro.
- Gates (H1-Muster `wa_tables`): Agent ohne Grant → 404 (kein Existenz-Leak),
  Read-Grant ohne Write → 403 `area_forbidden` VOR der Query.

Laeuft gegen echte Postgres + tmp-TableStore (`set_table_store`, Muster
`test_wa_tables.py`).
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from who2be_api.testing.api_helpers import agent_token

from who2be_api.main import app
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_SCHEMA: dict[str, Any] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "purpose", "type": "text"},
        {"name": "account", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "purpose", "account"],
}


# 5 Zeilen mit markanter Summe: 10+17+20+30+40 = 117 — die Zahl kommt in
# keinem Eingabetext vor, nur die Engine kann sie ins Artifact rendern.
def _row(day: int, amount: int, purpose: str, account: str) -> dict[str, Any]:
    return {
        "occurred_at": f"2026-08-{day:02d}T09:00:00+00:00",
        "amount": amount,
        "purpose": purpose,
        "account": account,
    }


_ROWS: list[dict[str, Any]] = [
    _row(1, 10, "miete", "giro"),
    _row(2, 17, "kaffee", "giro"),
    _row(3, 20, "strom", "giro"),
    _row(4, 30, "moebel", "spar"),
    _row(5, 40, "gehalt", "spar"),
]

_AGG_SQL = 'SELECT count(*) AS n, sum(amount) AS total FROM "transactions"'


@pytest.fixture
def table_store(tmp_path: Path) -> Iterator[TableStore]:
    """Frischer TableStore je Test (Locks binden an die Loop des Tests)."""
    store = TableStore(base_dir=tmp_path)
    set_table_store(store)
    yield store
    reset_table_store()


def _setup_table(
    client: TestClient, prefix: str, auth: dict[str, str], area_name: str
) -> tuple[str, str]:
    """Area + Tabelle `transactions` + 5 Zeilen — Ausgangslage aller Tests."""
    created_area = client.post(f"{prefix}/work-areas", json={"name": area_name}, headers=auth)
    assert created_area.status_code == 201, created_area.text
    area_id: str = created_area.json()["id"]
    created = client.post(
        f"{prefix}/work-areas/{area_id}/tables",
        json={"name": "transactions", "schema": _SCHEMA},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    table_id: str = created.json()["id"]
    inserted = client.post(
        f"{prefix}/wa-tables/{table_id}/rows", json={"rows": _ROWS}, headers=auth
    )
    assert inserted.status_code == 200, inserted.text
    assert inserted.json() == {"inserted": 5, "skipped": 0}
    return area_id, table_id


def _save(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    table_id: str,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {
        "sql": _AGG_SQL,
        "title": "Augustbilanz Girokonto",
        "occurred_at": "2026-08-15T00:00:00+00:00",
    }
    body.update(overrides)
    return client.post(f"{prefix}/wa-tables/{table_id}/save-result", json=body, headers=headers)


def _artifact_count(client: TestClient, prefix: str, auth: dict[str, str], area_id: str) -> int:
    listed = client.get(f"{prefix}/work-areas/{area_id}/artifacts", headers=auth)
    assert listed.status_code == 200, listed.text
    return len(listed.json())


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_save_result_friert_query_und_server_zahlen_ein(make_auth_headers: AuthFactory) -> None:
    """Spec-Akzeptanz: das Artifact traegt das SQL VERBATIM und die vom
    SERVER gerenderten Zahlen (Summe 117 aus dem Result-Set — „Keine Zahl
    stammt aus Modell-Text"); es liegt in derselben Area, type=doc,
    `occurred_at` aus dem Request; die WorkArea-Suche findet es sofort."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Bilanz")

            saved = _save(client, prefix, auth, table_id)
            assert saved.status_code == 201, saved.text
            artifact = saved.json()
            assert artifact["type"] == "doc"
            assert artifact["area_id"] == area_id
            assert artifact["title"] == "Augustbilanz Girokonto"
            assert artifact["occurred_at"].startswith("2026-08-15T00:00:00")
            # Default-Praezision `day` (Auswertungen sind tagesgenau).
            assert artifact["occurred_precision"] == "day"

            read = client.get(f"{prefix}/wa-artifacts/{artifact['id']}", headers=auth)
            assert read.status_code == 200, read.text
            markdown = read.json()["markdown"]
            # Die Query steht VERBATIM im Artifact (Spec M: Evidence).
            assert _AGG_SQL in markdown
            # Die Zahlen hat der SERVER aus dem Result-Set gerendert.
            assert "| n | total |" in markdown
            assert "| 5 | 117 |" in markdown
            assert "Eingefrorenes Query-Ergebnis vom" in markdown
            assert "(Tabelle 'transactions', 1 Zeilen)" in markdown

            # Chunk-Sync im Anlage-Pfad: die Suche findet den Titel sofort.
            hits = client.get(
                f"{prefix}/workarea-search", params={"q": "Augustbilanz"}, headers=auth
            )
            assert hits.status_code == 200, hits.text
            assert any(hit["artifact_id"] == artifact["id"] for hit in hits.json())
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_drop_sql_403_und_kein_artifact(make_auth_headers: AuthFactory) -> None:
    """DROP → 403 `query_not_readonly`, Syntaxfehler → 400 — in beiden
    Faellen entsteht KEIN Artifact (COUNT-Assertion) und der Datenbestand
    bleibt unveraendert."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "ReadOnly")
            assert _artifact_count(client, prefix, auth, area_id) == 0

            denied = _save(client, prefix, auth, table_id, sql='DROP TABLE "transactions"')
            assert denied.status_code == 403, denied.text
            assert denied.json()["reason"] == "query_not_readonly"

            broken = _save(client, prefix, auth, table_id, sql="SELEC kaputt")
            assert broken.status_code == 400, broken.text

            # KEIN Artifact entstanden; die Tabelle ist unveraendert.
            assert _artifact_count(client, prefix, auth, area_id) == 0
            count = client.post(
                f"{prefix}/wa-tables/{table_id}/query",
                json={"sql": 'SELECT count(*) FROM "transactions"'},
                headers=auth,
            )
            assert count.json()["rows"] == [[5]]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_truncated_hinweis_bei_limit(make_auth_headers: AuthFactory) -> None:
    """`limit` < Ergebniszeilen: das Artifact traegt nur die gekappten Zeilen
    und den `gekuerzt`-Hinweis im Intro — der Leser sieht den Schnitt."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, table_id = _setup_table(client, prefix, auth, "Kappung")

            saved = _save(
                client,
                prefix,
                auth,
                table_id,
                sql='SELECT purpose, amount FROM "transactions" ORDER BY amount',
                title="Kleinste Posten",
                limit=2,
            )
            assert saved.status_code == 201, saved.text

            read = client.get(f"{prefix}/wa-artifacts/{saved.json()['id']}", headers=auth)
            markdown = read.json()["markdown"]
            assert "(Tabelle 'transactions', 2 Zeilen, gekuerzt)" in markdown
            assert "| miete | 10 |" in markdown
            assert "| kaffee | 17 |" in markdown
            # Die Zeilen jenseits des Caps sind NICHT im Artifact.
            assert "gehalt" not in markdown
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_gates_agent_ohne_grant_404_und_read_grant_403(make_auth_headers: AuthFactory) -> None:
    """H1-Muster: Agent ohne Grant → 404 (kein Existenz-Leak); Read-Grant
    ohne Write → 403 `area_forbidden` VOR der Query — kein Artifact."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Gates")

            _, no_grant = agent_token(client, prefix, "sqr-nogrant", {"workarea_write": True}, auth)
            assert _save(client, prefix, no_grant, table_id).status_code == 404

            ro_id, ro_tok = agent_token(client, prefix, "sqr-ro", {"workarea_write": True}, auth)
            granted = client.put(
                f"{prefix}/work-areas/{area_id}/grants/{ro_id}",
                json={"level": "read"},
                headers=auth,
            )
            assert granted.status_code == 200, granted.text
            forbidden = _save(client, prefix, ro_tok, table_id)
            assert forbidden.status_code == 403, forbidden.text
            assert forbidden.json()["reason"] == "area_forbidden"

            assert _artifact_count(client, prefix, auth, area_id) == 0
    finally:
        cleanup_workspaces([owner])
