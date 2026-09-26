"""DB-freie Waechter fuer die Artifact-Seite der Speicher-Quota (Karte W8/P5).

Owner-Entscheidung 2026-09-24: „In die Speicher-Quota einrechnen — Artifact-Text
zaehlt wie Dateien, ein Limit fuer alles." Bis dahin zaehlte
`storage_quota_service` nur `wa_blob.size_bytes`; Artifact-Text
(`wa_artifact.content`) fiel unter KEIN Kontingent — bis 500.000 Zeichen je
Aufruf bei 30 Writes/min, rechnerisch 15 MB/min auch im Free-Tarif.

Drei Zusicherungen, jede mit eigenem Waechter — und keiner haengt an einer
Namenskonvention oder an einem Snapshot:

1. **Die Verbrauchssumme zaehlt BEIDE Quellen.** `STORAGE_USED_SQL` muss
   `wa_blob.size_bytes` UND `wa_artifact.content_bytes` summieren, in EINER
   Abfrage (sie laeuft bei jedem Schreibzugriff) und ohne `content::text`
   (das waere der TOAST-Vollscan, den die Migration 0087 gerade vermeidet).
2. **Jeder Content-Write pflegt `content_bytes` mit.** Geprueft an der SQL
   selbst, per AST ueber die beiden Repo-Module: wer `wa_artifact.content`
   schreibt, ohne `content_bytes` mitzuschreiben, laesst die Summe
   auseinanderlaufen — ein neuer Schreibpfad bricht diesen Test, auch wenn er
   keine Route hat und keiner Namenskonvention folgt.
3. **Jede Artifact-Schreibroute traegt das Gate.** Geprueft am
   FastAPI-Dependency-Baum der LIVE-App, nicht an einer Textliste.

Zusicherung 3 deckt fuenf Routen, nicht die drei der Kartenbeschreibung: die
erschoepfende Suche ueber die Repo-Methoden, die `wa_artifact.content`
schreiben (`insert_doc`, `append_blocks`, `patch_blocks`, `insert_doc_artifact`)
und deren Aufrufer, findet zusaetzlich `PATCH /wa-artifacts/{id}` (Voll-Ersatz
des Contents, derselbe 500k-Hebel wie append, nur ohne Block-Cap) und
`POST /wa-tables/{id}/save-result` (server-komponiertes doc-Artifact).

NICHT in der Liste und mit Grund: `POST /wa-artifacts/{id}/promote` erzeugt eine
*Resource*, keine Artifact-Bytes (dort ist `enforce_entity_quota` das richtige
Gate), und `DELETE /wa-artifacts/{id}` gibt Platz FREI — ein Gate darauf waere
der Weg zurueck unter die Grenze, den der „kein Datenverlust"-Vertrag (0084)
ausdruecklich offen haelt.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute

from who2be_api.core.config import Settings
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.entitlement import CLOUD_FREE_ENTITLEMENT, Entitlement
from who2be_api.main import app
from who2be_api.repositories import wa_artifact_repository, wa_blob_repository
from who2be_api.services import storage_quota_service
from who2be_api.services.storage_quota_service import (
    STORAGE_USED_SQL,
    StorageQuotaService,
    enforce_storage_quota,
)
from who2be_models import WorkspaceRole

# Jede Route, die Artifact-Bytes ENTSTEHEN laesst, mit Begruendung. Die
# Ingest-Routen tragen das Gate schon seit #536 und stehen mit, damit ein
# Rueckbau dort genauso auffaellt.
GATED_WRITE_ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/v1/workspaces/{workspace_id}/work-areas/{area_id}/artifacts"): (
        "insert_doc — neues doc-Artifact bis ARTIFACT_CONTENT_MAX_LENGTH"
    ),
    ("POST", "/v1/workspaces/{workspace_id}/artifacts"): (
        "insert_doc in die private Area des Agenten — derselbe Hebel ohne area_id"
    ),
    ("POST", "/v1/workspaces/{workspace_id}/wa-artifacts/{artifact_id}/append"): (
        "append_blocks — Zuwachs je Aufruf bis ARTIFACT_CONTENT_MAX_LENGTH"
    ),
    ("PATCH", "/v1/workspaces/{workspace_id}/wa-artifacts/{artifact_id}"): (
        "patch_blocks — VOLL-Ersatz des Contents; groesster Einzelpfad, in der "
        "Kartenbeschreibung nicht genannt"
    ),
    ("POST", "/v1/workspaces/{workspace_id}/wa-tables/{table_id}/save-result"): (
        "wa_tables.save_query_result ruft WaArtifactService.create mit "
        "server-komponiertem Content; in der Kartenbeschreibung nicht genannt"
    ),
    ("POST", "/v1/workspaces/{workspace_id}/ingest"): "Blob + abgeleiteter Text (#536)",
    ("POST", "/v1/workspaces/{workspace_id}/work-areas/{area_id}/ingest"): (
        "Blob + abgeleiteter Text (#536)"
    ),
}

# Schreibrouten auf `wa_artifact`, die BEWUSST kein Speicher-Gate tragen.
UNGATED_WITH_REASON: dict[tuple[str, str], str] = {
    ("DELETE", "/v1/workspaces/{workspace_id}/wa-artifacts/{artifact_id}"): (
        "gibt Platz FREI — der Weg zurueck unter die Grenze muss offen bleiben "
        "(kein-Datenverlust-Vertrag, Migration 0084)"
    ),
    ("POST", "/v1/workspaces/{workspace_id}/wa-artifacts/{artifact_id}/promote"): (
        "erzeugt eine Resource, keine Artifact-Bytes — dort greift enforce_entity_quota"
    ),
}


def _dependency_names(dependencies: Iterable[Any]) -> set[str]:
    """Namen aller Dependency-Callables, verschachtelte eingeschlossen."""
    names: set[str] = set()
    stack = list(dependencies)
    while stack:
        dep = stack.pop()
        call = getattr(dep, "call", None) or getattr(dep, "dependency", None)
        if call is not None:
            names.add(getattr(call, "__name__", ""))
        stack.extend(getattr(dep, "dependencies", ()))
    return names


def _api_routes() -> dict[tuple[str, str], set[str]]:
    """Inventar der LIVE-App: ``(Methode, Vollpfad) -> Dependency-Namen``.

    Die App bindet Router LAZY ein (`fastapi.routing._IncludedRouter`, s.
    `main.create_app`): `app.routes` enthaelt deshalb NICHT die Endpunkte,
    sondern Include-Wrapper mit `include_context` (Prefix + Router-Level-
    Dependencies) und `original_router`. Wer nur `app.routes` nach `APIRoute`
    filtert, sieht genau eine Route (`/v1/health`) und haelt ein leeres
    Inventar fuer „alles gedeckelt" — deshalb wird hier rekursiv abgestiegen
    und Prefix wie Router-Dependencies werden mitgefuehrt.

    Beides muss mit: das Gate darf am Endpunkt ODER am Router haengen (so
    haengt `require_agent_bound_token` fuer den ganzen WorkArea-Block).
    """
    found: dict[tuple[str, str], set[str]] = {}

    def walk(router: Any, prefix: str, inherited: set[str]) -> None:
        for route in router.routes:
            if isinstance(route, APIRoute):
                deps = inherited | _dependency_names(route.dependant.dependencies)
                # `APIRoute.methods` ist typseitig optional, praktisch immer
                # gesetzt (FastAPI leitet GET ab) — der Fallback haelt mypy
                # ruhig, ohne eine Route stillschweigend zu verschlucken.
                for method in route.methods or {"GET"}:
                    found[(method, prefix + route.path)] = deps
                continue
            ctx = getattr(route, "include_context", None)
            inner = getattr(route, "original_router", None)
            if ctx is not None and inner is not None:
                walk(inner, prefix + ctx.prefix, inherited | _dependency_names(ctx.dependencies))

    walk(app.router, "", set())
    return found


def test_route_inventory_is_not_empty() -> None:
    """Selbstpruefung des Inventars — der Waechter darf nicht leer leerlaufen.

    Ohne diesen Test wuerde ein Umbau der FastAPI-Router-Einbindung die drei
    Gate-Tests nicht rot machen, sondern STILL wirkungslos: ein leeres
    Inventar heisst „keine Route gefunden", und daraus laesst sich jede
    Zusicherung beweisen.
    """
    routes = _api_routes()
    assert len(routes) > 100, (
        f"Nur {len(routes)} Routen im Inventar — der Walker findet die "
        f"eingebundenen Router nicht mehr. Bis dahin sind die Gate-Tests "
        f"dieser Datei wirkungslos, nicht gruen."
    )
    assert ("GET", "/v1/health") in routes, "Der App-eigene Health-Endpunkt fehlt im Inventar."


@pytest.mark.parametrize(
    ("method", "path"),
    list(GATED_WRITE_ROUTES),
    ids=[f"{m} {p}" for m, p in GATED_WRITE_ROUTES],
)
def test_artifact_write_route_carries_storage_gate(method: str, path: str) -> None:
    """Zusicherung 3: jede Route, die Artifact-Bytes entstehen laesst, ist gedeckelt.

    Faellt auch dann, wenn die Route nur UMBENANNT wird — dann fehlt sie im
    Inventar der App und der Test nennt den Pfad, der nicht mehr existiert.
    """
    routes = _api_routes()
    assert (method, path) in routes, (
        f"Route {method} {path} existiert nicht (mehr). Wurde sie umbenannt, "
        f"gehoert der neue Pfad in GATED_WRITE_ROUTES — sonst schreibt hier "
        f"jemand ungedeckelt Artifact-Bytes. Grund des Eintrags: "
        f"{GATED_WRITE_ROUTES[(method, path)]}"
    )
    deps = routes[(method, path)]
    assert enforce_storage_quota.__name__ in deps, (
        f"{method} {path} traegt KEIN Speicher-Gate, laesst aber Artifact-Bytes "
        f"entstehen ({GATED_WRITE_ROUTES[(method, path)]}). "
        f"`dependencies=[Depends(enforce_storage_quota)]` ergaenzen. "
        f"Gefundene Dependencies: {sorted(deps)}"
    )


@pytest.mark.parametrize(
    ("method", "path"),
    list(UNGATED_WITH_REASON),
    ids=[f"{m} {p}" for m, p in UNGATED_WITH_REASON],
)
def test_freeing_routes_stay_ungated(method: str, path: str) -> None:
    """Gegenprobe: die beiden bewusst ungegateten Pfade bleiben offen.

    Ohne diesen Test waere „mehr Gates" immer die sichere Antwort — und ein
    Gate auf DELETE wuerde eine Org, die ueber ihr Limit gerutscht ist,
    dauerhaft einsperren: kein Write mehr, und auch kein Aufraeumen.
    """
    routes = _api_routes()
    assert (method, path) in routes, f"Route {method} {path} existiert nicht (mehr)."
    deps = routes[(method, path)]
    assert enforce_storage_quota.__name__ not in deps, (
        f"{method} {path} traegt ein Speicher-Gate, darf aber keines tragen: "
        f"{UNGATED_WITH_REASON[(method, path)]}"
    )


def _sql_literals(module: object) -> list[str]:
    """Alle SQL-verdaechtigen String-Literale eines Moduls (implizite
    Konkatenation und f-Strings zusammengesetzt).

    Am Quelltext statt an einem Mock: so greift die Pruefung auch auf SQL, die
    kein Test je ausfuehrt, und braucht keine Datenbank.
    """
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")  # type: ignore[arg-type]
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            # f-String: nur die statischen Teile; `{_FULL_COLUMNS}` ist fuer die
            # Frage „welche Spalten werden GESCHRIEBEN" ohne Belang.
            out.append(
                "".join(
                    part.value
                    for part in node.values
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
            )
    return out


def _artifact_content_writes(module: object) -> list[str]:
    """SQL-Anweisungen des Moduls, die `wa_artifact.content` schreiben."""
    writes = []
    for sql in _sql_literals(module):
        flat = " ".join(sql.split())
        writes_artifact = "INSERT INTO wa_artifact" in flat or "UPDATE wa_artifact" in flat
        if not writes_artifact:
            continue
        # `content` als geschriebene Spalte: in der INSERT-Spaltenliste oder als
        # `content =` im SET. Das reine Vorkommen von `content_ref`/`blob_sha256`
        # zaehlt nicht — blob/table-Artifacts tragen keinen Text.
        touches_content = "content =" in flat or " content," in flat or " content)" in flat
        if touches_content:
            writes.append(flat)
    return writes


@pytest.mark.parametrize(
    "module",
    [wa_artifact_repository, wa_blob_repository],
    ids=["wa_artifact_repository", "wa_blob_repository"],
)
def test_every_content_write_also_maintains_content_bytes(module: object) -> None:
    """Zusicherung 2: wer `content` schreibt, schreibt `content_bytes` mit.

    Der Waechter, der NICHT an Routen haengt: ein neuer Schreibpfad im Repo
    bricht ihn, egal wie die Methode heisst und ob sie je eine Route bekommt.
    Laufen die beiden auseinander, ist die Verbrauchssumme still falsch — und
    eine still falsche Quota ist schlimmer als keine.
    """
    writes = _artifact_content_writes(module)
    assert writes, (
        f"{getattr(module, '__name__', module)} enthaelt keine "
        f"`wa_artifact.content`-Schreib-SQL mehr — wurde sie verschoben? Dann "
        f"gehoert das neue Modul in die Parametrisierung dieses Tests."
    )
    for flat in writes:
        assert "content_bytes" in flat, (
            "SQL schreibt `wa_artifact.content`, pflegt aber `content_bytes` "
            "nicht mit — die Speicher-Summe laeuft damit auseinander "
            f"(Migration 0087). Betroffen:\n  {flat}"
        )
        # Der Wert MUSS aus dem geschriebenen Content berechnet werden. Ein
        # vom Client oder Service gelieferter Byte-Wert waere manipulierbar
        # bzw. wuerde bei `append` die Doppelzaehlung wieder aufmachen.
        assert "octet_length" in flat, (
            "`content_bytes` wird nicht per `octet_length(...)` aus dem "
            "geschriebenen Content berechnet. Ein uebergebener Wert ist nicht "
            f"belastbar (append muss den Zuwachs treffen). Betroffen:\n  {flat}"
        )


def test_storage_used_sql_counts_blobs_and_artifacts() -> None:
    """Zusicherung 1: EINE Abfrage, BEIDE Quellen, kein TOAST-Vollscan."""
    flat = " ".join(STORAGE_USED_SQL.split())
    assert "wa_blob" in flat and "size_bytes" in flat, (
        "Die Blob-Bytes fehlen in der Verbrauchssumme — das war die Zaehlung "
        "seit #536 und darf nicht wegfallen."
    )
    assert "wa_artifact" in flat and "content_bytes" in flat, (
        "Artifact-Bytes fehlen in der Verbrauchssumme. Owner-Entscheidung "
        "2026-09-24: ein Limit fuer alles."
    )
    # Genau EIN Statement: die Summe laeuft bei jedem Schreibzugriff, ein
    # zweiter Roundtrip waere spuerbar (und der Entitlement-Read in
    # `routers/entitlement.py` importiert dieselbe Konstante).
    assert flat.count(";") == 0, "STORAGE_USED_SQL darf nur EIN Statement sein."
    assert flat.lower().startswith("select"), "STORAGE_USED_SQL muss ein SELECT sein."
    # Der teure Weg, den Migration 0087 gerade vermeidet.
    assert "content::text" not in flat, (
        "`content::text` in der Summenabfrage detoastet jede Zeile des "
        "Workspace bei JEDEM Upload (~100 MB je Anfrage am Free-Limit). "
        "Dafuer gibt es die materialisierte Spalte `content_bytes` (0087)."
    )
    # Genau ein Parameter: der Workspace. Mehr waere ein anderer Vertrag als
    # der, den `routers/entitlement.py` und das Gate aufrufen.
    assert "$2" not in flat, "STORAGE_USED_SQL nimmt genau einen Parameter ($1)."


class _FakePool:
    """Liefert Org-Aufloesung und die eine Verbrauchssumme (Muster
    `test_storage_quota_service.FakePool`)."""

    def __init__(self, used_bytes: int) -> None:
        self._used = used_bytes
        self.sum_calls = 0
        self.queries: list[str] = []

    async def fetchval(self, query: str, *_args: object) -> object:
        self.queries.append(query)
        if "FROM workspace WHERE" in query:
            return uuid4()
        self.sum_calls += 1
        return self._used


class _FakePort:
    def __init__(self, entitlement: Entitlement) -> None:
        self._entitlement = entitlement

    async def resolve(self, _org_id: UUID) -> Entitlement:
        return self._entitlement


def _ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=False,
    )


def _service(
    monkeypatch: pytest.MonkeyPatch,
    entitlement: Entitlement,
    pool: _FakePool,
    edition: Literal["cloud", "onprem"] = "cloud",
) -> StorageQuotaService:
    monkeypatch.setattr(
        storage_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: _FakePort(entitlement),
    )
    return StorageQuotaService(pool, Settings(edition=edition))


def test_gate_uses_a_single_sum_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Artifact-Seite kostet KEINE zweite Abfrage.

    Der Test haelt die Kostenzusage der Karte fest: waere die Artifact-Summe
    eine eigene Rundreise, verdoppelte sich der Aufwand des Gates bei jedem
    der 30 Writes/min.
    """
    pool = _FakePool(used_bytes=0)
    asyncio.run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool).enforce(_ctx()))
    assert pool.sum_calls == 1, (
        f"Erwartet genau eine Summenabfrage, gesehen {pool.sum_calls}: {pool.queries}"
    )


def test_artifact_bytes_alone_can_trigger_402(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kern der Karte: ohne einen einzigen Blob reicht Artifact-Text fuer 402.

    Der Fake summiert bereits beide Quellen (so wie es die eine SQL tut); der
    Punkt hier ist, dass das Gate den Wert auch dann durchsetzt, wenn er
    ausschliesslich aus Artifact-Text stammt — genau die Luecke, durch die
    15 MB/min liefen.
    """
    limit = CLOUD_FREE_ENTITLEMENT.storage_quota_bytes
    assert limit is not None
    pool = _FakePool(used_bytes=limit)
    with pytest.raises(ApiError) as exc:
        asyncio.run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool).enforce(_ctx()))
    assert exc.value.status_code == 402
    assert exc.value.reason == "storage_quota_exceeded"
    assert exc.value.params == {"limit": limit, "used": limit}
