"""WorkArea-REST-Aufrufe des MCP-Servers (ADR-0047, WP8).

Freie Funktionen statt weiterer `ApiClient`-Methoden (Architektur-
Entscheidung 3.2): `client.py` bleibt unangetastet, jede neue Domain liegt in
`clients/<domain>.py`. Die Funktionen nutzen bewusst die privaten
Request-Helper des `ApiClient` (`_get`/`_write`/`_request` und
`_workspace_prefix`) — dieses Modul ist ein paket-internes Friend-Modul
DESSELBEN Adapters (gleiche Fehler-Uebersetzung in `ToolError`, gleiche
Timeouts), keine externe API.

Pfade: Welle-2-Router `work_areas.py` / `wa_artifacts.py` / `wa_ingest.py` /
`wa_search.py` unter `/v1/workspaces/{ws_id}`.
"""

from __future__ import annotations

from uuid import UUID

from who2be_mcp.client import ApiClient
from who2be_models import (
    ArtifactAppend,
    ArtifactCreate,
    ArtifactMarkdown,
    ArtifactPatch,
    ArtifactRead,
    IngestRequest,
    IngestResult,
    WorkAreaRead,
    WorkAreaSearchHit,
)


async def create_artifact(
    client: ApiClient, area_id: UUID | None, data: ArtifactCreate
) -> ArtifactRead:
    """`POST .../work-areas/{area_id}/artifacts`; ohne Area `POST .../artifacts`
    (private Area des gebundenen Agenten, serverseitig aufgeloest)."""
    prefix = client._workspace_prefix
    path = f"{prefix}/artifacts" if area_id is None else f"{prefix}/work-areas/{area_id}/artifacts"
    payload = await client._write("POST", path, data)
    return ArtifactRead.model_validate(payload)


async def append_artifact(
    client: ApiClient, artifact_id: UUID, data: ArtifactAppend
) -> ArtifactRead:
    """`POST .../wa-artifacts/{id}/append` — lockfreies Anhaengen (rev+1)."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/wa-artifacts/{artifact_id}/append", data
    )
    return ArtifactRead.model_validate(payload)


async def patch_artifact(client: ApiClient, artifact_id: UUID, data: ArtifactPatch) -> ArtifactRead:
    """`PATCH .../wa-artifacts/{id}` — optimistisches Block-Edit; eine veraltete
    `expected_rev` reicht der Client als 409-`ToolError` mit dem
    `rev_conflict`-Detail (aktuelle rev) an den Agenten durch."""
    payload = await client._write(
        "PATCH", f"{client._workspace_prefix}/wa-artifacts/{artifact_id}", data
    )
    return ArtifactRead.model_validate(payload)


async def read_artifact(
    client: ApiClient, artifact_id: UUID, anchor: str | None = None
) -> ArtifactMarkdown:
    """`GET .../wa-artifacts/{id}?anchor=` — Markdown mit `[#block_id]`-Ankern;
    `anchor` liefert nur den einen Block."""
    params = {"anchor": anchor} if anchor is not None else None
    payload = await client._get(
        f"{client._workspace_prefix}/wa-artifacts/{artifact_id}", params=params
    )
    return ArtifactMarkdown.model_validate(payload)


async def list_work_areas(client: ApiClient) -> list[WorkAreaRead]:
    """`GET .../work-areas` — sichtbare Areas; loest fuer agent-gebundene Tokens
    die private Auto-Anlage aus (erster Zugriff, ADR-0047)."""
    payload = await client._get(f"{client._workspace_prefix}/work-areas")
    return [WorkAreaRead.model_validate(item) for item in payload]


async def list_artifacts(client: ApiClient, area_id: UUID) -> list[ArtifactRead]:
    """`GET .../work-areas/{area_id}/artifacts` — Metadaten-Liste einer Area."""
    payload = await client._get(f"{client._workspace_prefix}/work-areas/{area_id}/artifacts")
    return [ArtifactRead.model_validate(item) for item in payload]


async def delete_artifact(client: ApiClient, artifact_id: UUID) -> None:
    """`DELETE .../wa-artifacts/{id}` — antwortet 204 OHNE Body, daher direkt
    `_request` statt `_write` (das wuerde `response.json()` parsen)."""
    await client._request("DELETE", f"{client._workspace_prefix}/wa-artifacts/{artifact_id}")


async def ingest(client: ApiClient, area_id: UUID | None, data: IngestRequest) -> IngestResult:
    """`POST .../work-areas/{area_id}/ingest`; ohne Area `POST .../ingest`
    (private Area). Dedup-Treffer (200, `deduplicated=True`) sind kein Fehler."""
    prefix = client._workspace_prefix
    path = f"{prefix}/ingest" if area_id is None else f"{prefix}/work-areas/{area_id}/ingest"
    payload = await client._write("POST", path, data)
    return IngestResult.model_validate(payload)


async def search_workarea(
    client: ApiClient, query: str, area_id: UUID | None = None
) -> list[WorkAreaSearchHit]:
    """`GET .../workarea-search?q=&area_id=` — Anker + Snippet je Treffer."""
    params: dict[str, str] = {"q": query}
    if area_id is not None:
        params["area_id"] = str(area_id)
    payload = await client._get(f"{client._workspace_prefix}/workarea-search", params=params)
    return [WorkAreaSearchHit.model_validate(item) for item in payload]
