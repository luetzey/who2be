"""Integrationstests fuer Kategorisierung + Konventionen (WP17 — Spec L/M2).

Spec-Akzeptanzen:

- „Regel VOR Modell": ein Kategorie-Wert ohne matchende aktive Regel und ohne
  deckendes `new_rules`-Element → 422 `rule_required`, NICHTS persistiert
  (weder Regeln noch SQLite-Rows — COUNT-Assertions).
- `new_rules` werden VOR der Anwendung persistiert; die Kategorie kommt aus
  der REGEL (ein abweichender Client-Wert wird ueberschrieben). Derselbe
  Haendler bekommt in zwei Importen dieselbe Kategorie — auch bei
  Modellwechsel (zweiter Import OHNE `new_rules`, die Regel greift).
- Zwei aktive Regeln mit verschiedenen Kategorien auf derselben Row → Row
  bleibt NULL + `kb_conflict(kind='rule')` — kein stilles Gewinnen; offene
  Konflikte desselben Paars werden nicht gedoppelt.
- Regel-Upsert kategorisiert rueckwirkend neu (SQLite-Wert aendert sich,
  Konflikt-Rows bleiben unangetastet) und wird im `audit_log` protokolliert
  (`workarea.rules_reapplied`).
- Spec M2: `source_name` ohne Quell-Konvention → 422 `convention_missing`
  (VOR jedem Write); mit Konvention wird importiert.
- Gates (H1-Muster): Agent ohne Grant → 404 (kein Existenz-Leak), Read-Grant
  ohne Write → 403 `area_forbidden`, ohne Capability → 403
  `missing_capability`, viewer-Token → 403 `insufficient_role`.

Laeuft gegen echte Postgres (Regeln/Konventionen/Konflikte/Audit) +
tmp-TableStore (`set_table_store`, Muster `test_wa_tables.py`).
"""

import asyncio
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_api.main import app
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.api_helpers import agent_token, db_execute, grant
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

# Spec-L-Beispiel: Kontoauszugs-Tabelle mit Haendler-Matching (`merchant`)
# und Server-gesetzter Kategorie (`category`).
_SCHEMA: dict[str, Any] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "merchant", "type": "text"},
        {"name": "category", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "merchant"],
    "match_column": "merchant",
    "category_column": "category",
}


def _db_fetch(sql: str, *args: object) -> list[Any]:
    async def _run() -> list[Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


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
    """Shared Area + Regel-Tabelle; liefert (area_id, table_id)."""
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
    return area_id, table_id


def _row(
    merchant: str,
    *,
    category: str | None = None,
    occurred: str = "2026-08-01T12:00:00+00:00",
    amount: float = 1,
) -> dict[str, Any]:
    row: dict[str, Any] = {"occurred_at": occurred, "amount": amount, "merchant": merchant}
    if category is not None:
        row["category"] = category
    return row


def _insert(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    table_id: str,
    rows: list[dict[str, Any]],
    **extra: Any,
) -> Any:
    body: dict[str, Any] = {"rows": rows}
    body.update(extra)
    return client.post(f"{prefix}/wa-tables/{table_id}/rows", json=body, headers=headers)


def _query_rows(
    client: TestClient, prefix: str, headers: dict[str, str], table_id: str, sql: str
) -> list[list[Any]]:
    result = client.post(f"{prefix}/wa-tables/{table_id}/query", json={"sql": sql}, headers=headers)
    assert result.status_code == 200, result.text
    rows: list[list[Any]] = result.json()["rows"]
    return rows


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_rule_required_ohne_teilzustand(make_auth_headers: AuthFactory) -> None:
    """Spec-L-Akzeptanz „Regel VOR Modell": Kategorie-Wert ohne matchende Regel
    → 422 `rule_required`, und NICHTS ist persistiert — auch das mitgelieferte
    (nicht deckende) `new_rules`-Element rollt zurueck (eine Transaktion)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "RegelVorModell")

            denied = _insert(
                client,
                prefix,
                auth,
                table_id,
                [_row("Miete Wohnung GmbH", category="wohnen")],
                new_rules=[{"pattern": "edeka", "category": "lebensmittel"}],
            )
            assert denied.status_code == 422, denied.text
            body = denied.json()
            assert body["reason"] == "rule_required"
            assert body["actionable_by"] == "agent"

            # NICHTS persistiert: weder die neue Regel (Postgres) ...
            rule_count = _db_fetch(
                "SELECT count(*) AS n FROM wa_category_rule WHERE area_id = $1", UUID(area_id)
            )
            assert rule_count[0]["n"] == 0
            # ... noch SQLite-Rows.
            assert _query_rows(
                client, prefix, auth, table_id, 'SELECT count(*) FROM "transactions"'
            ) == [[0]]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_new_rules_persistiert_regel_schlaegt_client_und_modellwechsel(
    make_auth_headers: AuthFactory,
) -> None:
    """`new_rules` werden persistiert und die Kategorie kommt aus der REGEL
    (der bewusst abweichende Client-Wert wird ueberschrieben). Zweiter Import
    desselben Haendlers OHNE `new_rules` → gleiche Kategorie (Spec-Akzeptanz
    „auch bei Modellwechsel")."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Modellwechsel")

            first = _insert(
                client,
                prefix,
                auth,
                table_id,
                # Client behauptet 'voellig-falsch' — die Regel muss gewinnen.
                [_row("REWE Markt Koeln", category="voellig-falsch")],
                new_rules=[{"pattern": "rewe", "category": "lebensmittel", "confidence": 0.9}],
            )
            assert first.status_code == 200, first.text
            assert first.json() == {"inserted": 1, "skipped": 0}
            assert _query_rows(
                client, prefix, auth, table_id, 'SELECT category FROM "transactions"'
            ) == [["lebensmittel"]]

            # Die Regel ist persistiert; created_by attribuiert der SERVER.
            rules = client.get(f"{prefix}/work-areas/{area_id}/category-rules", headers=auth)
            assert rules.status_code == 200, rules.text
            [rule] = rules.json()
            assert rule["pattern"] == "rewe"
            assert rule["category"] == "lebensmittel"
            assert rule["created_by"] == f"user:{owner}"
            assert rule["confidence"] == 0.9
            assert rule["active"] is True

            # Modellwechsel: zweiter Import OHNE new_rules und ohne
            # Client-Kategorie — die persistierte Regel greift.
            second = _insert(
                client,
                prefix,
                auth,
                table_id,
                [_row("REWE City", occurred="2026-08-02T09:00:00+00:00")],
            )
            assert second.status_code == 200, second.text
            assert _query_rows(
                client, prefix, auth, table_id, 'SELECT DISTINCT category FROM "transactions"'
            ) == [["lebensmittel"]]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_regel_konflikt_row_null_und_kb_conflict(make_auth_headers: AuthFactory) -> None:
    """Zwei aktive Regeln, verschiedene Kategorien, beide matchen → Row bleibt
    NULL + `kb_conflict(kind='rule')` mit beiden Regel-IDs — kein stilles
    Gewinnen; das offene Paar wird beim zweiten Import nicht gedoppelt."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Konflikt")

            imported = _insert(
                client,
                prefix,
                auth,
                table_id,
                [_row("REWE Markt")],
                new_rules=[
                    {"pattern": "rewe", "category": "lebensmittel"},
                    {"pattern": "markt", "category": "einkauf"},
                ],
            )
            assert imported.status_code == 200, imported.text
            assert imported.json() == {"inserted": 1, "skipped": 0}
            # Kein stilles Gewinnen: die Row bleibt unkategorisiert.
            assert _query_rows(
                client, prefix, auth, table_id, 'SELECT category FROM "transactions"'
            ) == [[None]]

            rules = client.get(f"{prefix}/work-areas/{area_id}/category-rules", headers=auth).json()
            rule_ids = {rule["pattern"]: rule["id"] for rule in rules}
            conflicts = _db_fetch(
                "SELECT kind, a_id, b_id, reason, resolved_at FROM kb_conflict "
                "WHERE workspace_id = $1 AND kind = 'rule'",
                ws,
            )
            assert len(conflicts) == 1
            conflict = conflicts[0]
            assert {str(conflict["a_id"]), str(conflict["b_id"])} == set(rule_ids.values())
            assert "REWE Markt" in conflict["reason"]
            assert conflict["resolved_at"] is None

            # Zweiter Import derselben Konstellation: offenes Paar nicht doppeln.
            again = _insert(
                client,
                prefix,
                auth,
                table_id,
                [_row("REWE Markt", occurred="2026-08-03T08:00:00+00:00")],
            )
            assert again.status_code == 200, again.text
            still = _db_fetch(
                "SELECT count(*) AS n FROM kb_conflict WHERE workspace_id = $1 AND kind = 'rule'",
                ws,
            )
            assert still[0]["n"] == 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_regel_upsert_rekategorisiert_rueckwirkend_und_auditiert(
    make_auth_headers: AuthFactory,
) -> None:
    """Regel-Upsert (201/200) kategorisiert bestehende SQLite-Rows NEU und
    protokolliert den Lauf im `audit_log`; Konflikt-Rows (zweite Regel mit
    anderer Kategorie matcht dieselbe Row) bleiben unangetastet."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    rules_url_suffix = "/category-rules"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Rueckwirkend")
            seeded = _insert(
                client,
                prefix,
                auth,
                table_id,
                [
                    _row("Shell Tankstelle 42"),
                    _row("DB Bahn", occurred="2026-08-02T07:00:00+00:00"),
                ],
            )
            assert seeded.status_code == 200, seeded.text

            created = client.post(
                f"{prefix}/work-areas/{area_id}{rules_url_suffix}",
                json={"pattern": "shell", "category": "mobilitaet"},
                headers=auth,
            )
            assert created.status_code == 201, created.text
            rule_id = created.json()["id"]
            assert created.json()["created_by"] == f"user:{owner}"

            # Rueckwirkend: die Shell-Row ist jetzt kategorisiert, DB Bahn nicht.
            assert _query_rows(
                client,
                prefix,
                auth,
                table_id,
                'SELECT merchant, category FROM "transactions" ORDER BY merchant',
            ) == [["DB Bahn", None], ["Shell Tankstelle 42", "mobilitaet"]]

            audits = _db_fetch(
                "SELECT target, detail, jsonb_typeof(detail) AS kind FROM audit_log "
                "WHERE workspace_id = $1 AND action = 'workarea.rules_reapplied'",
                ws,
            )
            assert len(audits) == 1
            assert audits[0]["target"] == rule_id
            # Seit dem jsonb-Bind-Fix (2026-08-16) steht ein OBJEKT in der
            # Spalte, kein JSON-String mehr: `audit_service` serialisiert
            # weiterhin selbst, der Insert bindet den String aber an
            # `$6::text::jsonb` — damit greift der Pool-Codec nicht mehr ein
            # zweites Mal. Altzeilen bleiben bewusst wie sie sind.
            assert audits[0]["kind"] == "object"
            # `_db_fetch` haelt keinen jsonb-Codec, liefert also den rohen
            # Text — einmal parsen genuegt.
            detail = json.loads(audits[0]["detail"])
            assert detail["rule_id"] == rule_id
            assert detail["tables"] == {"transactions": 1}

            # Upsert desselben Patterns → 200 (Ersetzung), erneut rueckwirkend.
            replaced = client.post(
                f"{prefix}/work-areas/{area_id}{rules_url_suffix}",
                json={"pattern": "shell", "category": "auto"},
                headers=auth,
            )
            assert replaced.status_code == 200, replaced.text
            assert replaced.json()["id"] == rule_id
            assert _query_rows(
                client,
                prefix,
                auth,
                table_id,
                "SELECT category FROM \"transactions\" WHERE merchant LIKE 'Shell%'",
            ) == [["auto"]]

            # Konfligierende neue Regel ('tank' matcht die Shell-Row ebenfalls,
            # andere Kategorie): die Row wird bei der Re-Kategorisierung NICHT
            # angefasst — Konflikte werden nie still aufgeloest.
            conflicting = client.post(
                f"{prefix}/work-areas/{area_id}{rules_url_suffix}",
                json={"pattern": "tank", "category": "energie"},
                headers=auth,
            )
            assert conflicting.status_code == 201, conflicting.text
            assert _query_rows(
                client,
                prefix,
                auth,
                table_id,
                "SELECT category FROM \"transactions\" WHERE merchant LIKE 'Shell%'",
            ) == [["auto"]]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_convention_missing_und_mit_konvention(make_auth_headers: AuthFactory) -> None:
    """Spec M2: `source_name` ohne Konvention → 422 `convention_missing` VOR
    jedem Write; nach `PUT .../conventions/{source}` wird importiert."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Konventionen")

            denied = _insert(client, prefix, auth, table_id, [_row("Miete")], source_name="n26")
            assert denied.status_code == 422, denied.text
            body = denied.json()
            assert body["reason"] == "convention_missing"
            assert body["actionable_by"] == "agent"
            assert _query_rows(
                client, prefix, auth, table_id, 'SELECT count(*) FROM "transactions"'
            ) == [[0]]

            saved = client.put(
                f"{prefix}/work-areas/{area_id}/conventions/n26",
                json={"convention": {"decimal_separator": ",", "date_format": "DD.MM.YYYY"}},
                headers=auth,
            )
            assert saved.status_code == 200, saved.text
            convention = saved.json()
            assert convention["source_name"] == "n26"
            assert convention["created_by"] == str(owner)
            assert convention["convention"]["decimal_separator"] == ","

            # Der GESPEICHERTE Zustand, nicht der Roundtrip: der Mapper faengt
            # einen JSON-String tolerant ab, ein Roundtrip-Assert wuerde eine
            # doppelte Encodierung also NICHT bemerken. Genau die stand bis
            # 2026-08-16 in der Spalte und hat `GET /wa-tables/{id}` mit 500
            # beendet — hier ist sie sichtbar.
            stored = _db_fetch(
                "SELECT jsonb_typeof(convention) AS kind FROM wa_source_convention "
                "WHERE workspace_id = $1 AND area_id = $2 AND source_name = $3",
                ws,
                UUID(area_id),
                "n26",
            )
            assert [row["kind"] for row in stored] == ["object"]

            listed = client.get(f"{prefix}/work-areas/{area_id}/conventions", headers=auth)
            assert listed.status_code == 200
            assert [c["source_name"] for c in listed.json()] == ["n26"]

            accepted = _insert(client, prefix, auth, table_id, [_row("Miete")], source_name="n26")
            assert accepted.status_code == 200, accepted.text
            assert accepted.json() == {"inserted": 1, "skipped": 0}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_migration_0081_packt_doppelt_encodierte_konvention_aus(
    make_auth_headers: AuthFactory,
) -> None:
    """Bestandsdaten aus der Zeit vor dem Fix (Befund 2026-08-16).

    Der Code-Fix repariert nur NEUE Zeilen. Wer die Konvention vorher gesetzt
    hat, traegt weiter einen JSON-String in der Spalte — Migration 0081 packt
    ihn aus. Der Test stellt den Altbestand ueber eine Connection OHNE
    jsonb-Codec nach und laesst die Migrationsdatei selbst darauf laufen,
    statt ihre Logik im Test nachzubauen.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    convention = {"decimal_separator": ",", "date_format": "DD.MM.YYYY"}
    kind_sql = (
        "SELECT jsonb_typeof(convention) AS kind FROM wa_source_convention "
        "WHERE workspace_id = $1 AND area_id = $2"
    )
    try:
        with TestClient(app) as client:
            area_id, table_id = _setup_table(client, prefix, auth, "Altbestand")
            saved = client.put(
                f"{prefix}/work-areas/{area_id}/conventions/n26",
                json={"convention": convention},
                headers=auth,
            )
            assert saved.status_code == 200, saved.text

            # Altbestand nachstellen: doppelt encodiert, also ein JSON-String.
            db_execute(
                "UPDATE wa_source_convention SET convention = $1::jsonb "
                "WHERE workspace_id = $2 AND area_id = $3",
                json.dumps(json.dumps(convention)),
                ws,
                UUID(area_id),
            )
            assert [r["kind"] for r in _db_fetch(kind_sql, ws, UUID(area_id))] == ["string"]

            db_execute(
                (MIGRATIONS_DIR / "0081_jsonb_double_encoded.sql").read_text(encoding="utf-8")
            )

            assert [r["kind"] for r in _db_fetch(kind_sql, ws, UUID(area_id))] == ["object"]
            described = client.get(f"{prefix}/wa-tables/{table_id}", headers=auth)
            assert described.status_code == 200, described.text
            assert described.json()["conventions"][0]["convention"] == convention
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "table_store")
def test_gates_regel_und_konventions_routen(make_auth_headers: AuthFactory) -> None:
    """H1-Muster: Agent ohne Grant → 404 (kein Existenz-Leak); Read-Grant ohne
    Write → Reads ok, Writes 403 `area_forbidden`; ohne Capability → 403
    `missing_capability`; viewer-Token → 403 `insufficient_role`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    rule_body = {"pattern": "rewe", "category": "lebensmittel"}
    convention_body = {"convention": {"decimal_separator": ","}}
    try:
        with TestClient(app) as client:
            area_id, _table_id = _setup_table(client, prefix, auth, "RuleGates")
            rules_url = f"{prefix}/work-areas/{area_id}/category-rules"
            conventions_url = f"{prefix}/work-areas/{area_id}/conventions"

            def _grant(agent_id: str, level: str) -> None:
                """Kurzform ueber Area/`auth` dieses Tests — Logik im Helfer."""
                grant(client, prefix, auth, area_id, agent_id, level)

            # Agent MIT Capability, aber ohne Grant: alles 404 (kein Leak).
            _, no_grant = agent_token(
                client, prefix, "rule-nogrant", {"workarea_write": True}, auth
            )
            assert client.get(rules_url, headers=no_grant).status_code == 404
            assert client.get(conventions_url, headers=no_grant).status_code == 404
            assert client.post(rules_url, json=rule_body, headers=no_grant).status_code == 404
            assert (
                client.put(
                    f"{conventions_url}/n26", json=convention_body, headers=no_grant
                ).status_code
                == 404
            )

            # Read-Grant: Reads ok, Writes 403 area_forbidden.
            ro_id, ro_tok = agent_token(client, prefix, "rule-ro", {"workarea_write": True}, auth)
            _grant(ro_id, "read")
            assert client.get(rules_url, headers=ro_tok).status_code == 200
            assert client.get(conventions_url, headers=ro_tok).status_code == 200
            ro_write = client.post(rules_url, json=rule_body, headers=ro_tok)
            assert ro_write.status_code == 403
            assert ro_write.json()["reason"] == "area_forbidden"

            # Agent OHNE workarea_write trotz Write-Grant: 403 missing_capability.
            no_cap_id, no_cap = agent_token(client, prefix, "rule-nocap", {}, auth)
            _grant(no_cap_id, "write")
            blocked = client.post(rules_url, json=rule_body, headers=no_cap)
            assert blocked.status_code == 403
            assert blocked.json()["reason"] == "missing_capability"

            # viewer-Token: Rollen-Gate VOR Capability (H1) — schreibt nie.
            viewer_id, viewer_tok = agent_token(
                client, prefix, "rule-viewer", {"workarea_write": True}, auth, role="viewer"
            )
            _grant(viewer_id, "write")
            viewer_write = client.put(
                f"{conventions_url}/n26", json=convention_body, headers=viewer_tok
            )
            assert viewer_write.status_code == 403
            assert viewer_write.json()["reason"] == "insufficient_role"

            # Agent MIT Write-Grant + Capability darf beides (Positivkontrolle).
            ok_id, ok_tok = agent_token(client, prefix, "rule-rw", {"workarea_write": True}, auth)
            _grant(ok_id, "write")
            agent_rule = client.post(
                rules_url, json={"pattern": "db bahn", "category": "mobilitaet"}, headers=ok_tok
            )
            assert agent_rule.status_code == 201, agent_rule.text
            assert agent_rule.json()["created_by"] == f"agent:{ok_id}"
    finally:
        cleanup_workspaces([owner])
