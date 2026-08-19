"""Integrationstests fuer die Tabellen-API (ADR-0049, WP13 — Spec K).

Kritische Invarianten:

- Roundtrip: create (Katalog + SQLite-DDL) → describe (Schema, row_count 0,
  Konventionen leer) → list; Doppel-Name in der Area → 409
  `concurrent_conflict`.
- Idempotenter Import (Spec K): 3 Zeilen → {3,0}, identischer Doppel-Import →
  {0,3}; Row ohne `occurred_at` bzw. mit unbekannter Spalte → 422.
- Read-only als ENGINE-GarantIE (Spec-K-Akzeptanz): DROP/UPDATE/PRAGMA →
  403 `query_not_readonly`; ein Aggregat ueber 10.000 Zeilen liefert NUR
  Aggregatzeilen (row_count 1, keine Rohzeilen in der Antwort).
- Formate: markdown/csv via `rendered`; `limit` deckelt + `truncated`.
- Gates (H1-Muster): Agent ohne Grant → 404 (kein Existenz-Leak), Read-Grant
  ohne Write → 403 `area_forbidden`, ohne Capability → 403
  `missing_capability`, viewer-Agent-Token → 403 `insufficient_role`;
  fremder Workspace → 404.

Laeuft gegen echte Postgres (Katalog) + tmp-TableStore (`set_table_store`,
frische Instanz je Test — die per-Area-Locks binden an die Test-Loop).
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

_SCHEMA: dict[str, Any] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "purpose", "type": "text"},
        {"name": "account", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "purpose", "account"],
}

# Spec-K-Beispiel: Kontoauszugs-Zeilen, Dedupe ueber Datum/Betrag/Zweck/Konto.
_ROWS: list[dict[str, Any]] = [
    {
        "occurred_at": "2026-08-01T12:00:00+00:00",
        "amount": 12.5,
        "purpose": "Miete",
        "account": "giro",
    },
    {
        "occurred_at": "2026-08-02T09:30:00+00:00",
        "amount": -3.2,
        "purpose": "Kaffee",
        "account": "giro",
    },
    {
        "occurred_at": "2026-08-02T10:00:00+00:00",
        "amount": 100,
        "purpose": "Gehalt",
        "account": "spar",
    },
]


@pytest.fixture
def table_store(tmp_path: Path) -> Iterator[TableStore]:
    """Frischer TableStore je Test (Locks binden an die Loop des Tests)."""
    store = TableStore(base_dir=tmp_path)
    set_table_store(store)
    yield store
    reset_table_store()


def _create_table(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    area_id: str,
    name: str = "transactions",
) -> Any:
    return client.post(
        f"{prefix}/work-areas/{area_id}/tables",
        json={"name": name, "schema": _SCHEMA},
        headers=headers,
    )


def _insert(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    table_id: str,
    rows: list[dict[str, Any]],
) -> Any:
    return client.post(f"{prefix}/wa-tables/{table_id}/rows", json={"rows": rows}, headers=headers)


def _query(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    table_id: str,
    sql: str,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {"sql": sql}
    body.update(overrides)
    return client.post(f"{prefix}/wa-tables/{table_id}/query", json=body, headers=headers)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_create_describe_roundtrip_und_namenskonflikt(make_auth_headers: AuthFactory) -> None:
    """create → describe (Schema-Echo, row_count 0, Konventionen leer) → list;
    Doppel-Name in der Area → 409 `concurrent_conflict`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Tabellen")

            created = _create_table(client, prefix, auth, area_id)
            assert created.status_code == 201, created.text
            table = created.json()
            assert table["name"] == "transactions"
            assert table["area_id"] == area_id
            assert table["schema"]["dedupe_columns"] == _SCHEMA["dedupe_columns"]
            table_id = table["id"]

            described = client.get(f"{prefix}/wa-tables/{table_id}", headers=auth)
            assert described.status_code == 200, described.text
            body = described.json()
            assert body["row_count"] == 0
            assert body["conventions"] == []
            assert [c["name"] for c in body["schema"]["columns"]] == [
                "occurred_at",
                "amount",
                "purpose",
                "account",
            ]
            assert set(body["column_stats"]) == {"occurred_at", "amount", "purpose", "account"}

            listed = client.get(f"{prefix}/work-areas/{area_id}/tables", headers=auth)
            assert listed.status_code == 200
            assert [t["id"] for t in listed.json()] == [table_id]

            duplicate = _create_table(client, prefix, auth, area_id)
            assert duplicate.status_code == 409, duplicate.text
            assert duplicate.json()["reason"] == "concurrent_conflict"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_tabelle_bleibt_auffindbar_und_ist_loeschbar(make_auth_headers: AuthFactory) -> None:
    """Der Betriebsbefund vom 2026-08-17: Tabellen waren eine Sackgasse.

    Ein Agent konnte eine Tabelle anlegen und sie im naechsten Lauf
    strukturell nicht wiederfinden — `search_workarea` indiziert
    Artifact-Passagen, `timeline` verlangt die ID bereits, und ein Listing gab
    es ueber MCP nicht. Loeschen ging gar nicht, jeder Ausweichname hinterliess
    eine Leiche.

    Geprueft wird die Kette, die ein Agent tatsaechlich geht:
    auflisten → wiederfinden → Namenskonflikt mit ID → loeschen → Name frei.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Auffindbarkeit")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]
            assert _insert(client, prefix, auth, table_id, _ROWS).status_code == 200

            # 1) Wiederfinden — mit nichts als der Area.
            listed = client.get(f"{prefix}/work-areas/{area_id}/tables", headers=auth)
            assert listed.status_code == 200, listed.text
            assert [(t["id"], t["name"]) for t in listed.json()] == [(table_id, "transactions")]

            # 2) Der Namenskonflikt nennt die ID der bestehenden Tabelle,
            #    statt auf einen Pfad zu verweisen, den ein Agent nicht gehen
            #    kann — damit heilt sich auch ein Agent ohne Listing selbst.
            konflikt = _create_table(client, prefix, auth, area_id)
            assert konflikt.status_code == 409, konflikt.text
            assert konflikt.json()["reason"] == "concurrent_conflict"
            assert table_id in konflikt.json()["detail"]

            # 3) Loeschen raeumt BEIDE Seiten — Katalog und SQLite-Datei.
            assert client.delete(f"{prefix}/wa-tables/{table_id}", headers=auth).status_code == 204
            assert client.get(f"{prefix}/wa-tables/{table_id}", headers=auth).status_code == 404
            assert client.get(f"{prefix}/work-areas/{area_id}/tables", headers=auth).json() == []

            # 4) Der eigentliche Beweis fuer (3): der Name ist wieder frei.
            #    Bliebe die SQLite-Tabelle liegen, liefe die Neuanlage in
            #    "already exists" → 409, und der Name waere dauerhaft verbrannt.
            erneut = _create_table(client, prefix, auth, area_id)
            assert erneut.status_code == 201, erneut.text
            assert erneut.json()["id"] != table_id
            # Frische Tabelle: die alten Zeilen sind mitgegangen.
            beschrieben = client.get(
                f"{prefix}/wa-tables/{erneut.json()['id']}", headers=auth
            ).json()
            assert beschrieben["row_count"] == 0

            # Unbekannte Tabelle → 404 (kein Existenz-Leak).
            assert client.delete(f"{prefix}/wa-tables/{_GHOST}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_delete_gates(make_auth_headers: AuthFactory) -> None:
    """Loeschen ist ein Schreibpfad: Rolle, Capability und Area-Grant zaehlen."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Delete-Gates")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]

            # Agent mit Read-Grant + Write-Capability → 403 `area_forbidden`.
            ro_id, ro_tok = agent_token(client, prefix, "nur-lesen", {"workarea_write": True}, auth)
            grant(client, prefix, auth, area_id, ro_id, "read")
            verweigert = client.delete(f"{prefix}/wa-tables/{table_id}", headers=ro_tok)
            assert verweigert.status_code == 403, verweigert.text
            assert verweigert.json()["reason"] == "area_forbidden"

            # Agent OHNE Grant → 404 (die Tabelle existiert fuer ihn nicht).
            _, fremd = agent_token(client, prefix, "ohne-grant", {"workarea_write": True}, auth)
            assert client.delete(f"{prefix}/wa-tables/{table_id}", headers=fremd).status_code == 404

            # Write-Grant ohne Capability → 403 `missing_capability`.
            wr_id, wr_tok = agent_token(client, prefix, "ohne-cap", {}, auth)
            grant(client, prefix, auth, area_id, wr_id, "write")
            ohne_cap = client.delete(f"{prefix}/wa-tables/{table_id}", headers=wr_tok)
            assert ohne_cap.status_code == 403, ohne_cap.text
            assert ohne_cap.json()["reason"] == "missing_capability"

            # Und die Tabelle steht nach allen Fehlversuchen unveraendert da.
            assert client.get(f"{prefix}/wa-tables/{table_id}", headers=auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_describe_liefert_gesetzte_konventionen(make_auth_headers: AuthFactory) -> None:
    """describe mit NICHT-leerer Konventions-Liste — der Fall aus dem Betrieb.

    Der Roundtrip-Test oben prueft nur `conventions == []`; damit lief der
    describe-Pfad nie ueber eine echte Konventions-Zeile. Live war die Folge
    ein 500, sobald eine Area der dokumentierten Reihenfolge folgte
    (Konvention setzen → importieren) — ausgerechnet fuer das Tool, das den
    Agenten als "DER Einstieg vor jeder Query" angeboten wird.

    Der Test prueft deshalb das, was der Agent bekommt: die Konvention muss
    als OBJEKT ankommen, nicht als JSON-String. Ein `== {...}` faengt beide
    Bruchstellen — Serverfehler und doppelt encodiertes JSON.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    convention = {"decimal_separator": ",", "date_format": "DD.MM.YYYY", "currency": "EUR"}
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Konventionen im describe")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]

            saved = client.put(
                f"{prefix}/work-areas/{area_id}/conventions/n26",
                json={"convention": convention},
                headers=auth,
            )
            assert saved.status_code == 200, saved.text

            described = client.get(f"{prefix}/wa-tables/{table_id}", headers=auth)
            assert described.status_code == 200, described.text
            conventions = described.json()["conventions"]
            assert [c["source_name"] for c in conventions] == ["n26"]
            assert conventions[0]["convention"] == convention
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_idempotenter_import_und_row_validierung(make_auth_headers: AuthFactory) -> None:
    """Spec K: 3 Zeilen → {3,0}; identischer Doppel-Import → {0,3}. Row ohne
    `occurred_at` → 422, unbekannte Spalte → 422 (nichts persistiert)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Import")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]

            first = _insert(client, prefix, auth, table_id, _ROWS)
            assert first.status_code == 200, first.text
            assert first.json() == {"inserted": 3, "skipped": 0}

            second = _insert(client, prefix, auth, table_id, _ROWS)
            assert second.status_code == 200, second.text
            assert second.json() == {"inserted": 0, "skipped": 3}

            # Row ohne occurred_at → 422 (Pflicht je Zeile, Anforderung N).
            missing = _insert(
                client, prefix, auth, table_id, [{"amount": 1, "purpose": "x", "account": "giro"}]
            )
            assert missing.status_code == 422, missing.text
            assert "occurred_at" in missing.text

            # Unparsebares occurred_at → ebenfalls 422.
            broken = _insert(
                client,
                prefix,
                auth,
                table_id,
                [{"occurred_at": "gestern mittag", "amount": 1}],
            )
            assert broken.status_code == 422, broken.text

            # Unbekannte Spalte → 422 mit Klartext.
            unknown = _insert(
                client,
                prefix,
                auth,
                table_id,
                [{"occurred_at": "2026-08-03T08:00:00+00:00", "amount": 1, "kommentar": "?"}],
            )
            assert unknown.status_code == 422, unknown.text
            assert "kommentar" in unknown.text

            # Die Fehlversuche haben nichts persistiert.
            count = _query(client, prefix, auth, table_id, 'SELECT count(*) FROM "transactions"')
            assert count.json()["rows"] == [[3]]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_query_readonly_engine_garantie(make_auth_headers: AuthFactory) -> None:
    """Spec-K-Akzeptanz: DROP/UPDATE/PRAGMA → 403 `query_not_readonly`
    (Datenbestand unveraendert); ein Syntaxfehler ist dagegen 400."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "ReadOnly")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]
            assert _insert(client, prefix, auth, table_id, _ROWS).status_code == 200

            for sql in (
                'DROP TABLE "transactions"',
                "UPDATE \"transactions\" SET purpose = 'x'",
                "PRAGMA journal_mode=DELETE",
            ):
                denied = _query(client, prefix, auth, table_id, sql)
                assert denied.status_code == 403, f"{sql}: {denied.text}"
                assert denied.json()["reason"] == "query_not_readonly"
                assert denied.json()["actionable_by"] == "agent"

            # Der Datenbestand ist unveraendert — nichts hat geschrieben.
            count = _query(client, prefix, auth, table_id, 'SELECT count(*) FROM "transactions"')
            assert count.status_code == 200
            assert count.json()["rows"] == [[3]]

            # Syntaxfehler ist KEINE Read-only-Verletzung → 400.
            broken = _query(client, prefix, auth, table_id, "SELEC kaputt")
            assert broken.status_code == 400, broken.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_aggregat_ueber_10000_zeilen_ohne_rohzeilen(make_auth_headers: AuthFactory) -> None:
    """Spec K: ein Aggregat ueber 10.000 Zeilen liefert NUR Aggregatzeilen —
    row_count 1, keine Rohzeilen in der Antwort, nicht truncated."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Masse")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]

            total_rows = 10_000
            batch_size = 1_000  # ROWS_INSERT_MAX_ROWS pro Request
            for start in range(0, total_rows, batch_size):
                rows = [
                    {
                        "occurred_at": "2026-08-01T12:00:00+00:00",
                        "amount": i,
                        "purpose": f"posten-{i}",
                        "account": "giro" if i % 2 == 0 else "spar",
                    }
                    for i in range(start, start + batch_size)
                ]
                res = _insert(client, prefix, auth, table_id, rows)
                assert res.status_code == 200, res.text
                assert res.json() == {"inserted": batch_size, "skipped": 0}

            result = _query(
                client,
                prefix,
                auth,
                table_id,
                'SELECT count(*) AS n, sum(amount) AS total FROM "transactions"',
            )
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["row_count"] == 1
            assert body["truncated"] is False
            assert body["rows"] == [[total_rows, sum(range(total_rows))]]

            # describe zaehlt alle Zeilen, liefert aber ebenfalls NIE Rohzeilen.
            described = client.get(f"{prefix}/wa-tables/{table_id}", headers=auth).json()
            assert described["row_count"] == total_rows
            assert described["column_stats"]["amount"]["min"] == 0
            assert described["column_stats"]["amount"]["max"] == total_rows - 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_query_formate_und_truncated(make_auth_headers: AuthFactory) -> None:
    """Formate (Entscheidung 7): markdown/csv via `rendered` (rows leer);
    `limit` deckelt das Ergebnis und setzt `truncated`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    sql = 'SELECT purpose, amount FROM "transactions" ORDER BY amount'
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Formate")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]
            assert _insert(client, prefix, auth, table_id, _ROWS).status_code == 200

            markdown = _query(client, prefix, auth, table_id, sql, format="markdown")
            assert markdown.status_code == 200, markdown.text
            md_body = markdown.json()
            assert md_body["rows"] is None
            assert md_body["columns"] == ["purpose", "amount"]
            lines = md_body["rendered"].splitlines()
            assert lines[0] == "| purpose | amount |"
            assert lines[1] == "| --- | --- |"
            assert "| Kaffee | -3.2 |" in lines

            csv_result = _query(client, prefix, auth, table_id, sql, format="csv")
            assert csv_result.status_code == 200
            csv_lines = csv_result.json()["rendered"].splitlines()
            assert csv_lines[0] == "purpose,amount"
            assert csv_lines[1] == "Kaffee,-3.2"

            capped = _query(client, prefix, auth, table_id, sql, limit=2)
            assert capped.status_code == 200
            capped_body = capped.json()
            assert capped_body["row_count"] == 2
            assert len(capped_body["rows"]) == 2
            assert capped_body["truncated"] is True
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_gates_grants_und_fremder_workspace(make_auth_headers: AuthFactory) -> None:
    """H1-Muster: Agent ohne Grant → 404 (kein Existenz-Leak); Read-Grant ohne
    Write → 403 `area_forbidden` (Reads ok); ohne Capability → 403
    `missing_capability`; viewer-Agent-Token → 403 `insufficient_role`;
    fremder Workspace → 404."""
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    ws_other = setup_workspace(other)
    auth = make_auth_headers(owner)
    other_auth = make_auth_headers(other)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Gates")
            table_id = _create_table(client, prefix, auth, area_id).json()["id"]
            assert _insert(client, prefix, auth, table_id, _ROWS).status_code == 200

            # Agent MIT Capability, aber ohne Grant: alles 404 (kein Leak).
            _, no_grant = agent_token(client, prefix, "tbl-nogrant", {"workarea_write": True}, auth)
            sql = 'SELECT count(*) FROM "transactions"'
            assert _query(client, prefix, no_grant, table_id, sql).status_code == 404
            assert client.get(f"{prefix}/wa-tables/{table_id}", headers=no_grant).status_code == 404
            assert _insert(client, prefix, no_grant, table_id, _ROWS).status_code == 404
            assert (
                client.get(f"{prefix}/work-areas/{area_id}/tables", headers=no_grant).status_code
                == 404
            )

            # Read-Grant: query/describe ok, Schreiben 403 area_forbidden.
            ro_id, ro_tok = agent_token(client, prefix, "tbl-ro", {"workarea_write": True}, auth)
            grant(client, prefix, auth, area_id, ro_id, "read")
            assert _query(client, prefix, ro_tok, table_id, sql).status_code == 200
            assert client.get(f"{prefix}/wa-tables/{table_id}", headers=ro_tok).status_code == 200
            ro_insert = _insert(client, prefix, ro_tok, table_id, _ROWS)
            assert ro_insert.status_code == 403
            assert ro_insert.json()["reason"] == "area_forbidden"

            # Agent OHNE workarea_write, trotz Write-Grant: 403 missing_capability.
            no_cap_id, no_cap = agent_token(client, prefix, "tbl-nocap", {}, auth)
            grant(client, prefix, auth, area_id, no_cap_id, "write")
            blocked = _create_table(client, prefix, no_cap, area_id, name="zweite")
            assert blocked.status_code == 403
            assert blocked.json()["reason"] == "missing_capability"
            cap_insert = _insert(client, prefix, no_cap, table_id, _ROWS)
            assert cap_insert.status_code == 403
            assert cap_insert.json()["reason"] == "missing_capability"

            # viewer-Agent-Token: Rollen-Gate VOR Capability (H1) — schreibt nie.
            viewer_id, viewer_tok = agent_token(
                client, prefix, "tbl-viewer", {"workarea_write": True}, auth, role="viewer"
            )
            grant(client, prefix, auth, area_id, viewer_id, "write")
            viewer_insert = _insert(client, prefix, viewer_tok, table_id, _ROWS)
            assert viewer_insert.status_code == 403
            assert viewer_insert.json()["reason"] == "insufficient_role"

            # Fremder Workspace: dieselbe table_id ist dort unsichtbar (404).
            other_prefix = f"/v1/workspaces/{ws_other}"
            assert (
                client.get(f"{other_prefix}/wa-tables/{table_id}", headers=other_auth).status_code
                == 404
            )
            assert _query(client, other_prefix, other_auth, table_id, sql).status_code == 404
            # Und eine Ghost-ID ist von alldem nicht unterscheidbar.
            assert client.get(f"{prefix}/wa-tables/{_GHOST}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner, other])


@pytest.fixture
def broken_table_store(tmp_path: Path) -> Iterator[TableStore]:
    """TableStore auf einem NICHT benutzbaren Basispfad.

    Stellt den Deploy-Fehlerfall nach: der Store kann sein Verzeichnis nicht
    anlegen. In Produktion ist das ein Named Volume, dessen Mount-Punkt root
    gehoert, waehrend der Container als uid 1000 laeuft.

    Nachgestellt wird es hier ueber eine DATEI als Basisverzeichnis — `mkdir`
    darunter scheitert dann mit `NotADirectoryError` (einem OSError).
    Bewusst NICHT ueber Rechtebits (`chmod 0o500`): Testlaeufe als root
    ignorieren die, der Fehlerfall traete gar nicht ein und der Test waere
    still wirkungslos.
    """
    blocker = tmp_path / "kein-verzeichnis"
    blocker.write_text("Diese Datei steht da, wo ein Verzeichnis sein muesste.")
    store = TableStore(base_dir=blocker)
    set_table_store(store)
    yield store
    reset_table_store()


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "broken_table_store")
def test_unbenutzbarer_store_meldet_503_statt_500(make_auth_headers: AuthFactory) -> None:
    """Ein nicht beschreibbarer Tabellen-Store ist 503 `tablestore_unavailable`.

    Regression zu einem echten Deploy-Fehler: das Volume war gemountet, der
    Mount-Punkt gehoerte aber root, der Container laeuft unprivilegiert — der
    `PermissionError` aus `tablestore/engine.py::_connect_rw` lief ungefangen
    bis zum 500 durch. Ein Betreiber sah nur „Who2Be-API-Fehler (500)" und
    hatte keinen Hinweis, wo er suchen soll.

    Geprueft wird beides, was daran falsch war: der Status (503 statt 500,
    `actionable_by='human'` — kein Retry hilft) und dass die Meldung die
    Stellschraube nennt, ohne Serverpfad oder OS-Fehler auszuplaudern.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "kaputter-store")
            created = _create_table(client, prefix, auth, area_id)

            assert created.status_code == 503, created.text
            problem = created.json()
            assert problem["reason"] == "tablestore_unavailable", problem
            assert problem["actionable_by"] == "human", problem
            # Die Meldung muss den Betreiber zur Stellschraube fuehren …
            assert "WHO2BE_TABLESTORE_DIR" in problem["detail"], problem
            # … aber weder den Serverpfad noch den OS-Fehler nach aussen geben.
            assert "kein-verzeichnis" not in problem["detail"], problem
            assert "NotADirectoryError" not in problem["detail"], problem

            # Kein Katalog-Eintrag ohne SQLite-Tabelle: die Transaktion des
            # create-Pfads muss auch bei diesem Fehler zurueckgerollt haben.
            listed = client.get(f"{prefix}/work-areas/{area_id}/tables", headers=auth)
            assert listed.status_code == 200, listed.text
            assert listed.json() == [], listed.json()
    finally:
        cleanup_workspaces([owner])
