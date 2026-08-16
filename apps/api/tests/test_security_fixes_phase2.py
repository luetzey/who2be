"""Regressionstests zu den Security-Review-Findings 2026-08-16 (Phase 2).

Betroffene Subsysteme: Tabellen-Store (ADR-0049), Zugriffslog (ADR-0047
Spec F) und Promote. Je Finding mindestens ein reproduzierender Fall —
Muster `test_security_fixes.py` (Wellen 1–2):

- **H1**: freies SQL bricht nach dem Zeitbudget ab (408) statt einen
  `to_thread`-Worker dauerhaft zu blockieren.
- **H2**: Zell- und Ergebnisgroesse sind gedeckelt (413) — `randomblob`
  bzw. viele mittelgrosse Zellen sind kein Speicher-DoS mehr.
- **H3**: der Authorizer prueft FUNKTIONSNAMEN — `fts3_tokenizer` (roher
  Pointer-Zugriff), `randomblob`, `load_extension` & Co. sind verweigert,
  legitime Aggregate/Window-Funktionen laufen weiter.
- **H4**: ein Agent-Token kann die eigene Modell-Config nicht aendern; das
  Zugriffslog snapshottet sie zum Zugriffszeitpunkt.
- **H5**: das Zugriffsprotokoll ueberlebt den Agent-Delete (409 statt
  Cascade-Loeschung); Loeschen ist Menschen vorbehalten.
- **M1**: ungebundene Maschinen-Tokens erreichen WorkArea/KB nicht —
  dreifach: DB-CHECK (0048, bereits vorhanden), Router-Gate, Verdrahtung.
- **M2**: verschluckte Log-Schreibfehler sind zaehlbar.
- **M3**: `save_query_result` prueft das Rate-Limit VOR der Query.
- **M4**: server-komponiertes Markdown ist gegen Titel-/SQL-/Zell-Injektion
  entschaerft.
- **L2**: die Timeline deckelt die Zahl der Tabellen-Quellen.
- **L3/L4**: Promote schreibt `changed_by = user_id` (Agent in die Note) und
  ueberlebt lange Titel; dazu der Ziel-Pfad (`?target_resource_id=`), den der
  Review-Hinweis als still-verworfen gemeldet hatte.
- **L5**: der CSV-Export praefixiert Formel-Zellen.

(L1 — Timeline-Existenz-Orakel — liegt in `test_wa_timeline.py`, wo der
Quellen-Gate-Fall schon zuhause war.)
"""

import asyncio
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

import who2be_api.services.access_log as access_log_module
from who2be_api.core.config import get_settings
from who2be_api.core.errors import ApiGateError
from who2be_api.core.rate_limit import token_rate_limiter
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.core.workarea_scope import require_agent_bound_token
from who2be_api.main import app
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.services.wa_tables import (
    _compose_result_doc,
    _render_csv,
    _render_markdown,
)
from who2be_api.tablestore import MAX_CELL_BYTES, MAX_RESULT_BYTES, TableStore
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)
from who2be_models import AgentToolPolicy, WorkspaceRole

AuthFactory = Callable[[UUID], dict[str, str]]

# Kurzes Zeitbudget: der Timeout-Fall soll den Test nicht 5 s aufhalten.
_FAST_TIMEOUT_MS = 250

_SCHEMA: dict[str, Any] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "purpose", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "purpose"],
}

_ROWS: list[dict[str, Any]] = [
    {"occurred_at": "2026-08-01T12:00:00+00:00", "amount": 12.5, "purpose": "Miete"},
    {"occurred_at": "2026-08-02T09:30:00+00:00", "amount": -3.2, "purpose": "Kaffee"},
    {"occurred_at": "2026-08-02T10:00:00+00:00", "amount": 100, "purpose": "Gehalt"},
]

_ALL_WRITE_POLICY: dict[str, object] = {"workarea_write": True, "kb_write": True}


# --------------------------------------------------------------- Infrastruktur


def _db_fetch(sql: str, *args: object) -> list[Any]:
    async def _run() -> list[Any]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _db_execute(sql: str, *args: object) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.fixture
def fast_table_store(tmp_path: Path) -> Iterator[TableStore]:
    """TableStore mit kurzem Zeitbudget (H1) — frische Instanz je Test-Loop."""
    store = TableStore(base_dir=tmp_path, query_timeout_ms=_FAST_TIMEOUT_MS)
    set_table_store(store)
    yield store
    reset_table_store()


def _agent_token(
    client: TestClient,
    prefix: str,
    name: str,
    policy: dict[str, object],
    auth: dict[str, str],
) -> tuple[str, dict[str, str]]:
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["id"]
    token = client.post(f"{prefix}/tokens", json={"name": name, "agent_id": agent_id}, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


def _machine_ctx(agent_id: UUID | None) -> WorkspaceContext:
    """Maschinen-Kontext mit/ohne Agent-Bindung — fuer das M1-Gate."""
    return WorkspaceContext(
        workspace_id=UUID("00000000-0000-0000-0000-0000000000f1"),
        user_id=UUID("00000000-0000-0000-0000-0000000000f2"),
        role=WorkspaceRole.admin,
        is_api_token=True,
        agent_id=agent_id,
        tool_policy=AgentToolPolicy() if agent_id is not None else None,
    )


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


def _table(
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


def _query(
    client: TestClient, prefix: str, headers: dict[str, str], table_id: str, sql: str, **extra: Any
) -> Any:
    body: dict[str, Any] = {"sql": sql}
    body.update(extra)
    return client.post(f"{prefix}/wa-tables/{table_id}/query", json=body, headers=headers)


def _fat_rows(count: int, width: int) -> list[dict[str, Any]]:
    """Zeilen mit breiten Textzellen — Rohstoff der Groessen-Tests (H2)."""
    return [
        {
            "occurred_at": "2026-08-01T12:00:00+00:00",
            "amount": index,
            "purpose": f"{index:06d}" + "x" * width,
        }
        for index in range(count)
    ]


# --------------------------------------------------------------------- H1


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h1_endless_query_is_interrupted(make_auth_headers: AuthFactory) -> None:
    """Eine rekursive CTE ohne Abbruchbedingung endet als 408 — schnell.

    Ohne den Progress-Handler laeuft sie unbegrenzt weiter und belegt
    dauerhaft einen `to_thread`-Worker (verifiziert: >25 s ohne Fix).
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)

            started = time.monotonic()
            endless = _query(
                client,
                prefix,
                auth,
                table_id,
                "WITH RECURSIVE laeuft(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM laeuft) "
                "SELECT count(*) FROM laeuft",
            )
            elapsed = time.monotonic() - started
            assert endless.status_code == 408, endless.text
            # Grosszuegige Schranke (Budget + Overhead), aber weit unter dem
            # frueheren Verhalten „laeuft bis zum Prozessende".
            assert elapsed < 10, f"Abbruch dauerte {elapsed:.1f}s"

            # Und: der Store bedient danach normal weiter (kein kaputter Zustand).
            ok = _query(client, prefix, auth, table_id, 'SELECT count(*) FROM "transactions"')
            assert ok.status_code == 200, ok.text
            assert ok.json()["rows"] == [[3]]
    finally:
        cleanup_workspaces([owner])


def test_h1_describe_is_interrupted_too(tmp_path: Path) -> None:
    """Auch der describe-Pfad bricht am Zeitbudget ab (H1).

    Wichtig, weil `describe` pro Spalte einen FULL SCAN faehrt (count/min/max/
    distinct) und damit auf einer grossen Area genauso teuer ist wie eine
    Agenten-Query — es lief vorher voellig ungedeckelt.

    Engine-nah (kein Postgres): Budget 0 ms laesst die Aggregate am ersten
    Progress-Callback scheitern; genug Zeilen, damit dieser Callback ueberhaupt
    erreicht wird (er feuert nur alle 10.000 VM-Schritte).
    """
    from who2be_api.tablestore import QueryTimeout
    from who2be_api.tablestore.schema import ColumnSpec, ColumnType

    columns = [ColumnSpec(name="purpose", type=ColumnType.TEXT)]
    ws = UUID("00000000-0000-0000-0000-0000000000a1")
    area = UUID("00000000-0000-0000-0000-0000000000b1")
    rows = [{"purpose": f"wert-{index}"} for index in range(20_000)]

    seeder = TableStore(base_dir=tmp_path)

    async def _seed() -> None:
        await seeder.create_table(ws, area, "t", columns)
        await seeder.insert_rows(ws, area, "t", ["purpose"], rows, lambda row: str(row["purpose"]))

    asyncio.run(_seed())

    # Mit Budget: describe liefert normal.
    generous = TableStore(base_dir=tmp_path)
    described = asyncio.run(generous.describe(ws, area, "t", columns))
    assert described.row_count == 20_000

    # Ohne Budget: derselbe Aufruf bricht als QueryTimeout ab — nicht als
    # roher sqlite3-Fehler (der wuerde als 400 „Syntaxfehler" verkauft).
    exhausted = TableStore(base_dir=tmp_path, query_timeout_ms=0)
    with pytest.raises(QueryTimeout):
        asyncio.run(exhausted.describe(ws, area, "t", columns))

    # Nuance, bewusst festgehalten: der Handler zaehlt VM-SCHRITTE, nicht Zeit.
    # `SELECT count(*)` beantwortet SQLite aus dem B-Baum, ohne die VM 10.000
    # Schritte laufen zu lassen — eine solche Query wird nie unterbrochen. Das
    # ist richtig so (sie ist billig); das Budget zielt auf teure Plaene.
    cheap = asyncio.run(exhausted.run_readonly_query(ws, area, 'SELECT count(*) FROM "t"', limit=1))
    assert cheap.rows == [[20_000]]


# --------------------------------------------------------------------- H2


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h2_oversized_cell_and_result_are_413(make_auth_headers: AuthFactory) -> None:
    """Zell- und Ergebnisgrenze antworten 413 `ingest_too_large`.

    (a) `group_concat` ueber viel Text sprengt `MAX_CELL_BYTES` — dieselbe
    Grenze, an der `randomblob(200000000)` scheitert (dort schon am
    Authorizer, s. H3). (b) Dieselben Daten dreifach projiziert sprengen das
    Result-Budget, obwohl JEDE einzelne Zelle klein ist — der Fall, den ein
    Zeilen-Limit allein nicht abfaengt.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            # 200 x 6 KB = 1,2 MB Nutztext: ueber MAX_CELL_BYTES, unter
            # MAX_RESULT_BYTES — beide Grenzen mit EINEM Datenbestand.
            rows = _fat_rows(200, 6_000)
            assert MAX_CELL_BYTES < 200 * 6_000 < MAX_RESULT_BYTES
            table_id = _table(client, prefix, auth, area, rows)

            fat_cell = _query(
                client, prefix, auth, table_id, 'SELECT group_concat(purpose) FROM "transactions"'
            )
            assert fat_cell.status_code == 413, fat_cell.text
            assert fat_cell.json()["reason"] == "ingest_too_large"

            fat_result = _query(
                client,
                prefix,
                auth,
                table_id,
                'SELECT purpose, purpose, purpose FROM "transactions"',
                limit=1000,
            )
            assert fat_result.status_code == 413, fat_result.text
            assert fat_result.json()["reason"] == "ingest_too_large"

            # Kontrast: dieselbe Tabelle, verdichtet, bleibt bedienbar.
            aggregate = _query(
                client,
                prefix,
                auth,
                table_id,
                'SELECT count(*), sum(amount) FROM "transactions"',
            )
            assert aggregate.status_code == 200, aggregate.text
            assert aggregate.json()["rows"] == [[200, sum(range(200))]]
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- H3


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT fts3_tokenizer('simple')",
        "SELECT randomblob(1000)",
        "SELECT zeroblob(1000)",
        "SELECT load_extension('x')",
        "SELECT sqlite_compileoption_get(1)",
        "SELECT sqlite_compileoption_used('ENABLE_FTS3')",
        "SELECT hex(randomblob(200000000))",
    ],
    ids=[
        "fts3_tokenizer",
        "randomblob",
        "zeroblob",
        "load_extension",
        "compileoption_get",
        "compileoption_used",
        "randomblob-hex-dos",
    ],
)
def test_h3_denied_functions(make_auth_headers: AuthFactory, sql: str) -> None:
    """Nicht gelistete SQL-Funktionen werden verweigert (403).

    `fts3_tokenizer` ist der scharfe Fall: es liest UND schreibt rohe
    C-Pointer und war ueber den pauschalen SQLITE_FUNCTION-Allow erreichbar.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)
            denied = _query(client, prefix, auth, table_id, sql)
            assert denied.status_code == 403, denied.text
            assert denied.json()["reason"] == "query_not_readonly"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
@pytest.mark.parametrize(
    "sql", ["SELECT readfile('/etc/passwd')", "SELECT writefile('/tmp/x','y')"]
)
def test_h3_file_functions_are_unreachable(make_auth_headers: AuthFactory, sql: str) -> None:
    """`readfile`/`writefile` sind unerreichbar — auf ZWEI Wegen.

    Sie gehoeren nicht zur SQLite-Bibliothek, sondern zur CLI (`fileio`), sind
    im Library-Build also gar nicht registriert (Antwort: 400, „no such
    function"). Der einzige Weg, sie nachzuladen, waere `load_extension` — und
    das verweigert der Authorizer (403, s. `test_h3_denied_functions`). Der
    Test haelt beide Enden fest, damit ein spaeterer Build mit `fileio` nicht
    unbemerkt eine Datei-API oeffnet.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)
            res = _query(client, prefix, auth, table_id, sql)
            assert res.status_code in (400, 403), res.text
            if res.status_code == 400:
                assert "no such function" in res.json()["detail"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h3_legitimate_analytics_still_runs(make_auth_headers: AuthFactory) -> None:
    """Die Verschaerfung darf echte Analytik nicht brechen.

    Aggregate, CTE, Datums-/Textfunktionen und WINDOW-Funktionen in einer
    Query — Window-Funktionen laufen als SQLITE_FUNCTION und waeren ohne
    Eintrag in der Allowlist mit abgeschnitten worden.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)

            analytics = _query(
                client,
                prefix,
                auth,
                table_id,
                """
                WITH tage AS (
                    SELECT date(occurred_at) AS tag,
                           sum(amount)       AS summe,
                           count(*)          AS anzahl
                    FROM "transactions"
                    GROUP BY date(occurred_at)
                )
                SELECT tag,
                       round(summe, 2)                    AS summe,
                       anzahl,
                       row_number() OVER (ORDER BY tag)   AS rang,
                       lag(summe) OVER (ORDER BY tag)     AS vortag,
                       upper(coalesce(tag, ''))           AS label
                FROM tage
                ORDER BY tag
                """,
            )
            assert analytics.status_code == 200, analytics.text
            rows = analytics.json()["rows"]
            assert [row[0] for row in rows] == ["2026-08-01", "2026-08-02"]
            assert [row[3] for row in rows] == [1, 2]

            grouped = _query(
                client,
                prefix,
                auth,
                table_id,
                "SELECT group_concat(purpose), typeof(amount), length(purpose), "
                "printf('%s!', purpose) FROM \"transactions\"",
            )
            assert grouped.status_code == 200, grouped.text
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- H4


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h4_agent_cannot_change_own_model_config(make_auth_headers: AuthFactory) -> None:
    """Ein Agent-Token darf `model_provider`/`model_name` nicht setzen.

    Sonst faelscht ein Agent die Compliance-Attribution seiner eigenen
    Zugriffe (erst auf 'local' stellen, lesen, zurueckstellen).
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, agent_headers = _agent_token(
                client, prefix, "schreiber", {"agent_write": True}, auth
            )

            forbidden = client.put(
                f"{prefix}/agents/{agent_id}",
                json={"model_provider": "local", "model_name": "harmlos"},
                headers=agent_headers,
            )
            assert forbidden.status_code == 403, forbidden.text
            assert forbidden.json()["reason"] == "missing_capability"

            # Der Agent darf sich sonst weiter aendern (Builder-Pfad bleibt heil).
            renamed = client.put(
                f"{prefix}/agents/{agent_id}", json={"description": "neu"}, headers=agent_headers
            )
            assert renamed.status_code == 200, renamed.text

            # Der Mensch pflegt die Modell-Config — und nichts wurde vorher
            # heimlich gesetzt.
            human = client.put(
                f"{prefix}/agents/{agent_id}",
                json={"model_provider": "anthropic", "model_name": "claude-x"},
                headers=auth,
            )
            assert human.status_code == 200, human.text
            assert human.json()["model_provider"] == "anthropic"

            audits = _db_fetch(
                "SELECT detail FROM audit_log WHERE workspace_id = $1 "
                "AND action = 'agent.model_config_changed'",
                ws,
            )
            assert len(audits) == 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h4_access_log_snapshots_model_config(make_auth_headers: AuthFactory) -> None:
    """Das Log friert die Modell-Config zum Zugriffszeitpunkt ein.

    Eine spaetere Umstellung auf 'local' darf die Vergangenheit nicht
    umschreiben — genau das tat der Join auf die aktuelle Agent-Config.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, agent_headers = _agent_token(client, prefix, "leser", _ALL_WRITE_POLICY, auth)
            configured = client.put(
                f"{prefix}/agents/{agent_id}",
                json={"model_provider": "anthropic", "model_name": "claude-x"},
                headers=auth,
            )
            assert configured.status_code == 200, configured.text

            created = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "Beleg",
                    "content_md": "Inhalt",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=agent_headers,
            )
            assert created.status_code == 201, created.text

            # Nachtraeglich auf 'local' umstellen — der Snapshot bleibt.
            switched = client.put(
                f"{prefix}/agents/{agent_id}",
                json={"model_provider": "local", "model_name": "lokal"},
                headers=auth,
            )
            assert switched.status_code == 200, switched.text

            rows = _db_fetch(
                "SELECT model_provider_at_access, model_name_at_access "
                "FROM agent_access_log WHERE workspace_id = $1",
                ws,
            )
            assert rows, "kein Zugriffslog-Eintrag entstanden"
            assert all(row["model_provider_at_access"] == "anthropic" for row in rows)
            assert all(row["model_name_at_access"] == "claude-x" for row in rows)
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- H5


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_h5_access_log_survives_agent_delete(make_auth_headers: AuthFactory) -> None:
    """Der Agent-Delete raeumt das Protokoll NICHT mehr ab (409).

    Frueher trug der FK `ON DELETE CASCADE`: ein gewoehnlicher API-Delete
    loeschte die Protokollzeilen mit — der Cascade laeuft mit Owner-Rechten,
    der Append-only-Grant-Entzug greift dort nicht.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, agent_headers = _agent_token(
                client, prefix, "spurenleger", _ALL_WRITE_POLICY, auth
            )
            created = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "Beleg",
                    "content_md": "Inhalt",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=agent_headers,
            )
            assert created.status_code == 201, created.text
            before = _db_fetch(
                "SELECT id FROM agent_access_log WHERE agent_id = $1", UUID(agent_id)
            )
            assert before, "Voraussetzung: es gibt Protokollzeilen"

            blocked = client.delete(f"{prefix}/agents/{agent_id}", headers=auth)
            assert blocked.status_code == 409, blocked.text
            assert blocked.json()["reason"] == "concurrent_conflict"

            after = _db_fetch("SELECT id FROM agent_access_log WHERE agent_id = $1", UUID(agent_id))
            assert len(after) == len(before)  # nichts verloren

            # Und der Delete ist ohnehin Menschen vorbehalten.
            self_delete = client.delete(f"{prefix}/agents/{agent_id}", headers=agent_headers)
            assert self_delete.status_code == 403, self_delete.text
            assert self_delete.json()["reason"] == "missing_capability"

            # Ohne Protokollzeilen bleibt der Delete moeglich (kein Kollateral).
            fresh_id, _ = _agent_token(client, prefix, "unbenutzt", {}, auth)
            assert client.delete(f"{prefix}/agents/{fresh_id}", headers=auth).status_code == 204
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M1


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_m1_db_refuses_an_active_unbound_token(make_auth_headers: AuthFactory) -> None:
    """Erste Verteidigungslinie: ein AKTIVER ungebundener Token ist unmoeglich.

    Migration 0048 haelt das per CHECK `api_token_agent_bound_or_revoked`
    (agent-gebunden ODER widerrufen) und hat den Altbestand widerrufen. Der
    Review-Befund M1 („ungebundener Token liest alles und wird nie geloggt")
    ist damit bereits auf DB-Ebene geschlossen — der Test haelt das fest,
    damit ein spaeteres Lockern der Constraint auffaellt.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent_id, _ = _agent_token(client, prefix, "gebunden", {}, auth)
            token = client.post(
                f"{prefix}/tokens", json={"name": "t", "agent_id": agent_id}, headers=auth
            )
            assert token.status_code == 201, token.text

            # Die API laesst `agent_id` gar nicht erst weg …
            without = client.post(f"{prefix}/tokens", json={"name": "ohne"}, headers=auth)
            assert without.status_code == 422, without.text

            # … und direktes SQL scheitert am CHECK aus 0048.
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                _db_execute(
                    "UPDATE api_token SET agent_id = NULL WHERE id = $1",
                    UUID(token.json()["id"]),
                )
    finally:
        cleanup_workspaces([owner])


def test_m1_gate_rejects_unbound_machine_context() -> None:
    """Zweite Linie: das Router-Gate weist einen ungebundenen Maschinen-Kontext ab.

    Die DB-Constraint (s. o.) ist heute die harte Grenze; dieses Gate ist die
    Absicherung im Code — es greift, sobald ein Kontext OHNE Agent-Bindung
    entsteht (neuer Token-Typ, gelockerte Constraint, direkter DB-Eingriff),
    und haelt damit die Annahme der Scope-Aufloesung aufrecht: „nicht
    agent-gebunden" heisst dort „Mensch" und liest ALLES.
    """
    with pytest.raises(ApiGateError) as err:
        require_agent_bound_token(_machine_ctx(None))
    assert err.value.status == 403
    assert err.value.reason == "missing_capability"

    # Agent-gebundene Tokens und Menschen (JWT) passieren.
    require_agent_bound_token(_machine_ctx(UUID("00000000-0000-0000-0000-0000000000f3")))
    human = WorkspaceContext(
        workspace_id=UUID("00000000-0000-0000-0000-0000000000f1"),
        user_id=UUID("00000000-0000-0000-0000-0000000000f2"),
        role=WorkspaceRole.editor,
    )
    require_agent_bound_token(human)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_m1_gate_is_wired_to_every_workarea_route(make_auth_headers: AuthFactory) -> None:
    """Dritte Linie: das Gate haengt an JEDEM WorkArea-/KB-/Tabellen-Router.

    Ein ungebundener AKTIVER Token laesst sich heute nicht mehr bauen (DB-CHECK
    aus 0048) — der Kontext wird deshalb per `dependency_overrides` gestellt.
    Das prueft die Verdrahtung auf dem ECHTEN Request-Pfad: haengt das Gate an
    einem Router nicht, antwortet die Route 2xx/404 statt 403.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    ghost = "00000000-0000-0000-0000-000000000000"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)

            unbound = WorkspaceContext(
                workspace_id=ws,
                user_id=owner,
                role=WorkspaceRole.admin,
                is_api_token=True,
                agent_id=None,
                tool_policy=None,
            )
            app.dependency_overrides[get_current_workspace] = lambda: unbound
            try:
                probes = [
                    ("get", f"{prefix}/work-areas", None),
                    ("get", f"{prefix}/work-areas/{area}/artifacts", None),
                    ("get", f"{prefix}/wa-artifacts/{ghost}", None),
                    ("get", f"{prefix}/workarea-search", {"q": "x"}),
                    ("get", f"{prefix}/kb-search", {"q": "x"}),
                    ("get", f"{prefix}/kb/nodes/{ghost}", None),
                    ("get", f"{prefix}/work-areas/{area}/tables", None),
                    ("get", f"{prefix}/wa-tables/{table_id}", None),
                    (
                        "get",
                        f"{prefix}/timeline",
                        {"from_": "2026-08-01T00:00:00Z", "to": "2026-08-31T00:00:00Z"},
                    ),
                ]
                for method, path, params in probes:
                    res = getattr(client, method)(path, params=params)
                    assert res.status_code == 403, f"{path}: {res.status_code} {res.text}"
                    assert res.json()["reason"] == "missing_capability", path
            finally:
                app.dependency_overrides.pop(get_current_workspace, None)

            # Gegenprobe: mit demselben Kontext, aber agent-gebunden, ist die
            # Route wieder erreichbar — das Gate blockt nur die Bindungs-Luecke.
            agent_id, _ = _agent_token(client, prefix, "gebunden", {}, auth)
            bound = WorkspaceContext(
                workspace_id=ws,
                user_id=owner,
                role=WorkspaceRole.admin,
                is_api_token=True,
                agent_id=UUID(agent_id),
                tool_policy=AgentToolPolicy(),
            )
            app.dependency_overrides[get_current_workspace] = lambda: bound
            try:
                allowed = client.get(f"{prefix}/work-areas")
                assert allowed.status_code == 200, allowed.text
            finally:
                app.dependency_overrides.pop(get_current_workspace, None)
    finally:
        app.dependency_overrides.pop(get_current_workspace, None)
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M2


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_m2_failed_log_write_is_counted(
    make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein verschluckter Log-Fehler bleibt best-effort — aber zaehlbar."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"

    class _BrokenRepo:
        async def record(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("Log-Ziel nicht erreichbar")

    try:
        with TestClient(app) as client:
            _, agent_headers = _agent_token(client, prefix, "schreiber", _ALL_WRITE_POLICY, auth)
            access_log_module.reset_failed_log_writes()
            monkeypatch.setattr(access_log_module, "_repo", _BrokenRepo())

            created = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "Beleg",
                    "content_md": "Inhalt",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=agent_headers,
            )
            # Hauptpfad unbeeindruckt …
            assert created.status_code == 201, created.text
            # … aber die Luecke ist sichtbar.
            assert access_log_module.failed_log_writes() >= 1
    finally:
        access_log_module.reset_failed_log_writes()
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M3


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_m3_rate_limit_is_checked_before_the_query(
    make_auth_headers: AuthFactory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`save_query_result` prueft das Schreib-Limit VOR der Query.

    Vorher lief erst das (teure) SQL und dann das 429 im Artifact-Create —
    Arbeit ohne Gegenwert und ein Weg, die Drosselung zu umgehen.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    store = TableStore(base_dir=tmp_path, query_timeout_ms=_FAST_TIMEOUT_MS)
    set_table_store(store)
    executed: list[str] = []
    original = store.run_readonly_query

    async def _counting(*args: Any, **kwargs: Any) -> Any:
        executed.append(str(kwargs.get("sql") or args[2]))
        return await original(*args, **kwargs)

    monkeypatch.setattr(store, "run_readonly_query", _counting)
    token_rate_limiter.reset()
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Tabellen")
            table_id = _table(client, prefix, auth, area, _ROWS)
            agent_id, agent_headers = _agent_token(
                client,
                prefix,
                "sparsam",
                {"workarea_write": True, "write_rate_limit": 1},
                auth,
            )
            _grant(client, prefix, auth, area, agent_id, "write")

            save_body = {
                "sql": 'SELECT count(*) FROM "transactions"',
                "title": "Auswertung",
                "occurred_at": "2026-08-03T00:00:00Z",
            }
            first = client.post(
                f"{prefix}/wa-tables/{table_id}/save-result", json=save_body, headers=agent_headers
            )
            assert first.status_code == 201, first.text
            assert len(executed) == 1

            second = client.post(
                f"{prefix}/wa-tables/{table_id}/save-result", json=save_body, headers=agent_headers
            )
            assert second.status_code == 429, second.text
            # Entscheidend: die Query lief GAR NICHT mehr.
            assert len(executed) == 1
    finally:
        token_rate_limiter.reset()
        reset_table_store()
        cleanup_workspaces([owner])


# ------------------------------------------------------------------- M4 / L5


def test_m4_title_is_flattened_to_one_line() -> None:
    """Ein mehrzeiliger Titel kann keine eigenen Bloecke ins Artifact schreiben."""
    doc = _compose_result_doc(
        title="Bericht\n\n## Gefaelschte Ueberschrift\n\nAgent sagt: alles gut",
        table_name="transactions",
        sql="SELECT 1",
        columns=["n"],
        rows=[[1]],
        truncated=False,
    )
    lines = doc.splitlines()
    assert lines[0].startswith("# Bericht")
    # Der ganze Titel steckt in EINER Zeile — die gefaelschte Ueberschrift ist
    # damit Text, kein Block.
    assert "Gefaelschte Ueberschrift" in lines[0]
    assert not any(line.startswith("## ") for line in lines)


def test_m4_sql_fence_outlasts_backticks_in_sql() -> None:
    """Backticks IM SQL koennen den Fence nicht schliessen."""
    sql = "SELECT 1 -- ``` danach freier Text ```"
    doc = _compose_result_doc(
        title="Bericht",
        table_name="transactions",
        sql=sql,
        columns=["n"],
        rows=[[1]],
        truncated=False,
    )
    fences = [line for line in doc.splitlines() if line.startswith("`")]
    assert fences[0].startswith("````sql"), fences
    assert fences[-1] == "````"


def test_m4_cells_cannot_break_the_table_or_fake_anchors() -> None:
    """Zellinhalte bleiben Zellinhalte — keine neuen Zeilen, keine Anker."""
    rendered = _render_markdown(
        ["wert"],
        [["a | b\nneue Zeile [#deadbeef] Ende\r\tnoch mehr"]],
    )
    lines = rendered.splitlines()
    assert len(lines) == 3, lines  # Kopf, Trenner, EINE Datenzeile
    data = lines[2]
    assert "\\|" in data
    assert "[#" not in data
    assert "[ #deadbeef]" in data


def test_m4_title_anchor_marker_is_neutralized() -> None:
    doc = _compose_result_doc(
        title="Bericht [#aabbccdd] Ende",
        table_name="t",
        sql="SELECT 1",
        columns=["n"],
        rows=[[1]],
        truncated=False,
    )
    assert "[#" not in doc
    assert "[ #aabbccdd]" in doc


def test_l5_csv_formula_cells_are_prefixed() -> None:
    """Formel-Zellen bekommen ein fuehrendes `'` (OWASP CSV Injection)."""
    csv_text = _render_csv(
        ["wert", "betrag"],
        [
            ["=cmd|'/c calc'!A1", -3.2],
            ["+1+1", 5],
            ["-SUM(A1)", 0],
            ["@import", 1],
            ["harmlos", -7],
        ],
    )
    lines = csv_text.splitlines()
    assert lines[1].startswith("'=cmd")
    assert lines[2].startswith("'+1+1")
    assert lines[3].startswith("'-SUM(A1)")
    assert lines[4].startswith("'@import")
    assert lines[5].startswith("harmlos")
    # Zahlen bleiben Zahlen: ein negativer Betrag ist keine Formel.
    assert lines[1].endswith("-3.2")
    assert lines[5].endswith("-7")


# --------------------------------------------------------------------- L2


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_l2_timeline_caps_table_sources(make_auth_headers: AuthFactory) -> None:
    """Mehr als `TIMELINE_MAX_SOURCES` Tabellen-Quellen → 422.

    Jede Quelle ist ein eigener SQLite-Full-Scan; das Zeitbudget greift pro
    Query, nicht pro Request.
    """
    from who2be_api.routers.wa_timeline import TIMELINE_MAX_SOURCES

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    window = {"from_": "2026-08-01T00:00:00Z", "to": "2026-08-31T00:00:00Z"}
    try:
        with TestClient(app) as client:
            too_many = ",".join(
                f"table:00000000-0000-0000-0000-{index:012d}"
                for index in range(TIMELINE_MAX_SOURCES + 1)
            )
            res = client.get(
                f"{prefix}/timeline", params={**window, "sources": too_many}, headers=auth
            )
            assert res.status_code == 422, res.text
            assert str(TIMELINE_MAX_SOURCES) in res.json()["detail"]

            # Wiederholungen derselben Tabelle zaehlen nach dem Dedupe nicht.
            duplicated = ",".join(["table:00000000-0000-0000-0000-000000000001"] * 50)
            repeated = client.get(
                f"{prefix}/timeline", params={**window, "sources": duplicated}, headers=auth
            )
            assert repeated.status_code == 404, repeated.text  # unbekannte Tabelle, kein 422
    finally:
        cleanup_workspaces([owner])


# ------------------------------------------------------------------- L3 / L4


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_l3_l4_promote_actor_and_long_title(make_auth_headers: AuthFactory) -> None:
    """Promote: `changed_by` bleibt der USER, die Agent-ID steht in der Note;
    ein 300-Zeichen-Titel erzeugt keinen 500er mehr."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Eingang")
            agent_id, agent_headers = _agent_token(
                client,
                prefix,
                "promoter",
                {"workarea_write": True, "resource_write": True},
                auth,
            )
            _grant(client, prefix, auth, area, agent_id, "write")

            long_title = "Sehr langer Titel " * 16  # > 100 Slug-Zeichen
            created = client.post(
                f"{prefix}/work-areas/{area}/artifacts",
                json={
                    "title": long_title[:300],
                    "content_md": "# Kopf\n\nInhalt.",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=agent_headers,
            )
            assert created.status_code == 201, created.text

            promoted = client.post(
                f"{prefix}/wa-artifacts/{created.json()['id']}/promote", headers=agent_headers
            )
            # L4: kein 500 durch einen zu langen Slug.
            assert promoted.status_code == 201, promoted.text
            resource_id = promoted.json()["id"]
            assert len(promoted.json()["slug"]) <= 100

            history = _db_fetch(
                "SELECT changed_by, note FROM status_history "
                "WHERE entity_type = 'resource' AND entity_id = $1",
                UUID(resource_id),
            )
            assert len(history) == 1
            # L3: der User-Identitaetsraum der Spalte bleibt unvermischt …
            assert history[0]["changed_by"] == owner
            assert history[0]["changed_by"] != UUID(agent_id)
            # … die handelnde Maschine steht trotzdem drin.
            assert f"agent:{agent_id}" in history[0]["note"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "fast_table_store")
def test_promote_target_updates_instead_of_creating(make_auth_headers: AuthFactory) -> None:
    """`?target_resource_id=` ergaenzt die benannte Resource, statt neu anzulegen.

    Der Review-Hinweis („MCP schickt das Feld im Body, der Router liest die
    Query — der Wunsch wird still verworfen") ist inzwischen auf der
    MCP-Seite behoben (WP19, `clients/kb.py` ruft body-los mit `params`).
    Der Router bleibt bewusst query-only — dieser Test haelt fest, dass der
    Ziel-Pfad wirklich aktualisiert und nicht heimlich eine zweite Resource
    erzeugt.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Eingang")
            first = client.post(
                f"{prefix}/work-areas/{area}/artifacts",
                json={
                    "title": "Quelle",
                    "content_md": "# Kopf\n\nErste Fassung.",
                    "occurred_at": "2026-08-01T12:00:00Z",
                },
                headers=auth,
            )
            assert first.status_code == 201, first.text
            target = client.post(
                f"{prefix}/wa-artifacts/{first.json()['id']}/promote", headers=auth
            )
            assert target.status_code == 201, target.text
            target_id = target.json()["id"]

            second = client.post(
                f"{prefix}/work-areas/{area}/artifacts",
                json={
                    "title": "Nachtrag",
                    "content_md": "# Kopf\n\nZweite Fassung.",
                    "occurred_at": "2026-08-02T12:00:00Z",
                },
                headers=auth,
            )
            assert second.status_code == 201, second.text

            via_query = client.post(
                f"{prefix}/wa-artifacts/{second.json()['id']}/promote",
                params={"target_resource_id": target_id},
                headers=auth,
            )
            assert via_query.status_code == 201, via_query.text
            # Kein Neuanlegen: dieselbe Resource wurde aktualisiert.
            assert via_query.json()["id"] == target_id
            # Kein zweiter Eintrag: eine NEUE Resource truege den Titel des
            # zweiten Artifacts. (Der Workspace enthaelt daneben die
            # verwalteten Builder-Seeds — deshalb wird auf den Namen geprueft,
            # nicht auf die Gesamtzahl.)
            listed = client.get(f"{prefix}/resources", headers=auth)
            assert listed.status_code == 200, listed.text
            names = [entry["name"] for entry in listed.json()]
            assert "Nachtrag" not in names, names
            assert names.count("Quelle") == 1, names
    finally:
        cleanup_workspaces([owner])
