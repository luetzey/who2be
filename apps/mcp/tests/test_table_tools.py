"""Tool-Tests fuer die Tabellen-/Timeline-MCP-Tools (ADR-0049, WP19).

Test-Muster A (wie test_workarea_tools.py): die modulweiten async
Tool-Funktionen aus `who2be_mcp.tools.tables` werden direkt ueber
`asyncio.run` getrieben (kein pytest-asyncio im Stack), der HTTP-Verkehr
laeuft ueber `httpx.MockTransport`, `server.build_client` wird je Test auf
eine Factory gepatcht — die Tools loesen den Client zur Laufzeit ueber das
`server`-Modul auf, der Patch greift also unveraendert.

Abgedeckt: je Tool ein Roundtrip (Methode + Pfad + Body/Query), die
Modell-Validierung vor dem Request (fehlende `occurred_at`-Spalte), die
CSV-Kodierung der `timeline`-Quellen, `query_table` mit format=markdown, die
403-Durchreichung (`query_not_readonly`) als `ToolError` — und
`promote_artifact` (`tools/kb.py`, hier mitgetestet, weil es mit WP19
registriert wurde) mit `target_resource_id` als QUERY-Parameter: als
Body-Feld wuerde der Router es still ignorieren und eine neue Resource
anlegen.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.tools.kb import promote_artifact
from who2be_mcp.tools.tables import (
    create_table,
    delete_table,
    describe_table,
    insert_rows,
    list_category_rules,
    list_tables,
    query_table,
    save_query_result,
    set_convention,
    timeline,
    upsert_category_rule,
)
from who2be_models import (
    ArtifactRead,
    CategoryRuleRead,
    NewRule,
    QueryFormat,
    QueryResult,
    ResourceRead,
    SourceConventionRead,
    TableDescription,
    TimelineGranularity,
    TimelineResult,
    WaTableRead,
)

_WORKSPACE_ID = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"
_OCCURRED = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)

_SCHEMA: dict[str, object] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp", "nullable": False},
        {"name": "amount", "type": "numeric"},
        {"name": "merchant", "type": "text"},
        {"name": "category", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "merchant"],
    "match_column": "merchant",
    "category_column": "category",
}


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _body(request: httpx.Request) -> dict[str, object]:
    parsed = json.loads(request.content)
    assert isinstance(parsed, dict)
    return parsed


def _table_payload(table_id: UUID | None = None, area_id: UUID | None = None) -> dict[str, object]:
    return {
        "id": str(table_id or uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "area_id": str(area_id or uuid4()),
        "name": "umsaetze",
        "schema": _SCHEMA,
        "row_count": None,
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
    }


def _artifact_payload(artifact_id: UUID | None = None) -> dict[str, object]:
    return {
        "id": str(artifact_id or uuid4()),
        "area_id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "type": "doc",
        "title": "Ausgaben pro Kategorie",
        "rev": 1,
        "occurred_at": "2026-08-12T09:30:00Z",
        "occurred_precision": "day",
        "sensitivity": "general",
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
        "updated_by": "agent:00000000-0000-0000-0000-000000000001",
        "blocks": [{"block_id": "abc12345", "kind": "paragraph", "md": "| a | b |"}],
    }


def _rule_payload(area_id: UUID, pattern: str = "REWE%") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "area_id": str(area_id),
        "pattern": pattern,
        "category": "lebensmittel",
        "created_by": "agent:00000000-0000-0000-0000-000000000001",
        "confidence": 0.9,
        "active": True,
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
    }


def _convention_payload(area_id: UUID, source_name: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "area_id": str(area_id),
        "source_name": source_name,
        "convention": {"currency": "EUR", "decimal_separator": ","},
        "created_by": None,
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
    }


def _resource_payload() -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": "Marktnotizen",
        "slug": "marktnotizen",
        "current_version": 1,
        "current_status": "draft",
        "has_pending_draft": True,
        "content": {"description": "", "blocks": []},
        "created_at": "2026-08-12T09:31:00Z",
        "updated_at": "2026-08-12T09:31:00Z",
    }


# --- create_table ------------------------------------------------------------


def test_create_table_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_table_payload(area_id=area_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(create_table(area_id=str(area_id), name="umsaetze", schema=_SCHEMA))

    assert isinstance(result, WaTableRead)
    assert result.schema_.match_column == "merchant"
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/tables"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["name"] == "umsaetze"
    # Wire-Format traegt den Alias `schema` (Feldname ist `schema_`).
    schema = body["schema"]
    assert isinstance(schema, dict)
    assert schema["dedupe_columns"] == ["occurred_at", "amount", "merchant"]
    assert schema["category_column"] == "category"


def test_create_table_requires_occurred_at_column(monkeypatch: pytest.MonkeyPatch) -> None:
    # Zeitachsen-Invariante (Spec N) — Modell-Validator, kein API-Roundtrip.
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="occurred_at"):
        asyncio.run(
            create_table(
                area_id=str(uuid4()),
                name="umsaetze",
                schema={"columns": [{"name": "amount", "type": "numeric"}]},
            )
        )


def test_create_table_validates_area_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="Area-UUID"):
        asyncio.run(create_table(area_id="not-a-uuid", name="umsaetze", schema=_SCHEMA))


# --- list_tables / delete_table ----------------------------------------------


def test_list_tables_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Discovery-Pfad: welche Tabellen gibt es in dieser Area?

    Ohne ihn war eine Tabelle nach dem Anlegen ueber MCP strukturell nicht
    wiederauffindbar (Betriebsbefund 2026-08-17) — die Suche indiziert
    Artifact-Passagen, `timeline` verlangt die ID bereits.
    """
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json=[_table_payload(area_id=area_id)])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_tables(area_id=str(area_id)))

    assert [isinstance(t, WaTableRead) for t in result] == [True]
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/tables"


def test_list_tables_ohne_area_nimmt_die_private(monkeypatch: pytest.MonkeyPatch) -> None:
    """`area_id=None` = private Area — dieselbe Aufloesung wie `list_artifacts`.

    Beide ziehen sie aus `tools/area_ref`; zwei Kopien der Regel wuerden
    bedeuten, dass benachbarte Tools in verschiedene Areas schauen.
    """
    private_id = uuid4()
    pfade: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pfade.append(request.url.path)
        if request.url.path.endswith("/work-areas"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(private_id),
                        "workspace_id": str(_WORKSPACE_ID),
                        "name": "privat",
                        "scope": "private",
                        "agent_id": str(uuid4()),
                        "created_at": _OCCURRED.isoformat(),
                        "updated_at": _OCCURRED.isoformat(),
                    }
                ],
            )
        return httpx.Response(200, json=[])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(list_tables())
    assert pfade[-1] == f"{_PREFIX}/work-areas/{private_id}/tables"


def test_delete_table_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(204)

    monkeypatch.setattr(server, "build_client", _factory(handler))
    antwort = asyncio.run(delete_table(str(table_id)))

    assert seen["method"] == "DELETE"
    assert seen["path"] == f"{_PREFIX}/wa-tables/{table_id}"
    assert str(table_id) in antwort


def test_delete_table_validiert_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "build_client", _factory(lambda request: httpx.Response(204)))
    with pytest.raises(ToolError, match="Tabellen-UUID"):
        asyncio.run(delete_table("keine-uuid"))


# --- insert_rows -------------------------------------------------------------


def test_insert_rows_roundtrip_with_new_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(200, json={"inserted": 3, "skipped": 1})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        insert_rows(
            table_id=str(table_id),
            rows=[{"occurred_at": "2026-08-01T00:00:00Z", "amount": -12.5, "merchant": "REWE"}],
            source_artifact_id=str(artifact_id),
            source_name="giro_export",
            new_rules=[NewRule(pattern="REWE%", category="lebensmittel", confidence=0.9)],
        )
    )

    assert (result.inserted, result.skipped) == (3, 1)
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/wa-tables/{table_id}/rows"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["source_artifact_id"] == str(artifact_id)
    assert body["source_name"] == "giro_export"
    assert body["new_rules"] == [
        {"pattern": "REWE%", "category": "lebensmittel", "confidence": 0.9}
    ]
    rows = body["rows"]
    assert isinstance(rows, list) and rows[0]["merchant"] == "REWE"


def test_insert_rows_defaults_new_rules_to_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _body(request)
        return httpx.Response(200, json={"inserted": 1, "skipped": 0})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(insert_rows(table_id=str(uuid4()), rows=[{"occurred_at": "2026-08-01"}]))
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["new_rules"] == []
    assert body["source_name"] is None


def test_insert_rows_surfaces_rule_required_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    # „Regel vor Modell" (Spec L): eine Kategorie ohne Regel ist 422 — das
    # API-`detail` muss beim Agenten ankommen, damit er `new_rules` nachreicht.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"detail": "rule_required: Kategorie 'lebensmittel' hat keine Regel."}
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="rule_required"):
        asyncio.run(insert_rows(table_id=str(uuid4()), rows=[{"occurred_at": "2026-08-01"}]))


# --- query_table -------------------------------------------------------------


def test_query_table_roundtrip_json(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(
            200,
            json={
                "columns": ["category", "summe"],
                "rows": [["lebensmittel", -412.5]],
                "rendered": None,
                "row_count": 1,
                "truncated": False,
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        query_table(
            table_id=str(table_id),
            sql="SELECT category, sum(amount) AS summe FROM umsaetze GROUP BY category",
        )
    )

    assert isinstance(result, QueryResult)
    assert result.rows == [["lebensmittel", -412.5]]
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/wa-tables/{table_id}/query"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["format"] == "json"
    assert body["limit"] == 200
    assert body["sql"].startswith("SELECT category")


def test_query_table_markdown_format(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _body(request)
        return httpx.Response(
            200,
            json={
                "columns": ["category"],
                "rows": None,
                "rendered": "| category |\n| --- |\n| lebensmittel |",
                "row_count": 1,
                "truncated": True,
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        query_table(
            table_id=str(uuid4()),
            sql="SELECT category FROM umsaetze",
            format=QueryFormat.markdown,
            limit=50,
        )
    )

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["format"] == "markdown"
    assert body["limit"] == 50
    assert result.rows is None
    assert result.rendered is not None and result.rendered.startswith("| category |")
    assert result.truncated is True


def test_query_table_403_surfaces_query_not_readonly(monkeypatch: pytest.MonkeyPatch) -> None:
    # Read-only ist Engine-Garantie (ADR-0049) — das 403-`detail` reicht der
    # Client als ToolError durch, damit der Agent nicht blind neu formuliert.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "query_not_readonly: DROP ist nicht erlaubt."})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="query_not_readonly"):
        asyncio.run(query_table(table_id=str(uuid4()), sql="DROP TABLE umsaetze"))


# --- describe_table ----------------------------------------------------------


def test_describe_table_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "schema": _SCHEMA,
                "row_count": 412,
                "column_stats": {"amount": {"min": -900.0, "max": 12.0}},
                "conventions": [_convention_payload(area_id, "giro_export")],
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(describe_table(str(table_id)))

    assert isinstance(result, TableDescription)
    assert result.row_count == 412
    assert result.conventions[0].source_name == "giro_export"
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/wa-tables/{table_id}"


def test_describe_table_validates_table_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(ToolError, match="Tabellen-UUID"):
        asyncio.run(describe_table("not-a-uuid"))


# --- save_query_result -------------------------------------------------------


def test_save_query_result_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_artifact_payload(artifact_id=artifact_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        save_query_result(
            table_id=str(table_id),
            sql="SELECT category, sum(amount) FROM umsaetze GROUP BY category",
            title="Ausgaben pro Kategorie",
            occurred_at=_OCCURRED,
        )
    )

    assert isinstance(result, ArtifactRead)
    assert result.id == artifact_id
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/wa-tables/{table_id}/save-result"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["title"] == "Ausgaben pro Kategorie"
    assert body["occurred_precision"] == "day"
    occurred = body["occurred_at"]
    assert isinstance(occurred, str) and occurred.startswith("2026-08-12T09:30")


# --- timeline ----------------------------------------------------------------


def test_timeline_roundtrip_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "slices": [
                    {
                        "bucket": "2026-08-01",
                        "items": [{"anchor": "node:1", "kind": "node"}],
                        "counts": {"node": 1},
                    }
                ],
                "unknown": [{"anchor": "abc#b1", "kind": "artifact"}],
            },
        )

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        timeline(from_=datetime(2026, 8, 1, tzinfo=UTC), to=datetime(2026, 9, 1, tzinfo=UTC))
    )

    assert isinstance(result, TimelineResult)
    assert result.slices[0].counts == {"node": 1}
    # `unknown` bleibt separat — Eintraege ohne bekannte Zeit landen nie in
    # einer Zeitscheibe (Spec-Akzeptanz N).
    assert result.unknown[0].kind == "artifact"
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/timeline"
    params = seen["params"]
    assert isinstance(params, dict)
    # Der Router-Parameter heisst `from_` (kein Alias) — Default-Granularitaet
    # `day`, ohne `sources` entscheidet der Server (artifacts + nodes).
    assert params["from_"].startswith("2026-08-01T00:00:00")
    assert params["to"].startswith("2026-09-01T00:00:00")
    assert params["granularity"] == "day"
    assert "sources" not in params


def test_timeline_sends_sources_as_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    table_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"slices": [], "unknown": []})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(
        timeline(
            from_=datetime(2026, 8, 1, tzinfo=UTC),
            to=datetime(2026, 9, 1, tzinfo=UTC),
            sources=["artifacts", f"table:{table_id}"],
            granularity=TimelineGranularity.week,
        )
    )

    params = seen["params"]
    assert isinstance(params, dict)
    # EIN CSV-Wert statt Mehrfach-Parameter (der Router akzeptiert beides).
    assert params["sources"] == f"artifacts,table:{table_id}"
    assert params["granularity"] == "week"


# --- set_convention ----------------------------------------------------------


def test_set_convention_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(200, json=_convention_payload(area_id, "giro_export"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        set_convention(
            area_id=str(area_id),
            source_name="giro_export",
            convention={"currency": "EUR", "decimal_separator": ","},
        )
    )

    assert isinstance(result, SourceConventionRead)
    assert seen["method"] == "PUT"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/conventions/giro_export"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["convention"] == {"currency": "EUR", "decimal_separator": ","}


def test_set_convention_quotes_source_name_path_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    # `source_name` ist freier Text — ein `/` darf den Pfad nicht umbiegen.
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["raw_path"] = request.url.raw_path.decode()
        return httpx.Response(200, json=_convention_payload(area_id, "bank/giro"))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(set_convention(area_id=str(area_id), source_name="bank/giro", convention={}))

    assert seen["raw_path"] == f"{_PREFIX}/work-areas/{area_id}/conventions/bank%2Fgiro"


# --- Kategorie-Regeln --------------------------------------------------------


def test_upsert_category_rule_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = _body(request)
        return httpx.Response(201, json=_rule_payload(area_id))

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(
        upsert_category_rule(
            area_id=str(area_id), pattern="REWE%", category="lebensmittel", confidence=0.9
        )
    )

    assert isinstance(result, CategoryRuleRead)
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/category-rules"
    assert seen["body"] == {"pattern": "REWE%", "category": "lebensmittel", "confidence": 0.9}


def test_list_category_rules_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    area_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json=[_rule_payload(area_id), _rule_payload(area_id, "ALDI%")])

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(list_category_rules(str(area_id)))

    assert [rule.pattern for rule in result] == ["REWE%", "ALDI%"]
    assert seen["method"] == "GET"
    assert seen["path"] == f"{_PREFIX}/work-areas/{area_id}/category-rules"


# --- promote_artifact (tools/kb.py, mit WP19 registriert) --------------------


def test_promote_artifact_sends_target_as_query_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: die REST-Route nimmt `target_resource_id` als QUERY-Parameter
    # (`routers/wa_artifacts.py`) und hat gar kein Body-Modell. Als Body-Feld
    # wuerde der Wunsch still ignoriert — der Promote legte dann eine NEUE
    # Resource an, statt die benannte zu ergaenzen.
    artifact_id = uuid4()
    target_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["content"] = request.content
        return httpx.Response(201, json=_resource_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    result = asyncio.run(promote_artifact(str(artifact_id), target_resource_id=str(target_id)))

    assert isinstance(result, ResourceRead)
    assert seen["method"] == "POST"
    assert seen["path"] == f"{_PREFIX}/wa-artifacts/{artifact_id}/promote"
    assert seen["params"] == {"target_resource_id": str(target_id)}
    # Body-los: kein JSON-Payload, in dem das Ziel unbemerkt versanden koennte.
    assert seen["content"] == b""


def test_promote_artifact_without_target_sends_no_query(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact_id = uuid4()
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(201, json=_resource_payload())

    monkeypatch.setattr(server, "build_client", _factory(handler))
    asyncio.run(promote_artifact(str(artifact_id)))

    assert seen["params"] == {}


def test_promote_artifact_validates_target_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        server, "build_client", _factory(lambda request: httpx.Response(201, json={}))
    )
    with pytest.raises(ToolError, match="Resource-UUID"):
        asyncio.run(promote_artifact(str(uuid4()), target_resource_id="not-a-uuid"))
