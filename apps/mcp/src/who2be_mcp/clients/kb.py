"""KB-REST-Aufrufe des MCP-Servers (ADR-0047, WP9).

Freie Funktionen statt weiterer `ApiClient`-Methoden (Architektur-
Entscheidung 3.2): `client.py` bleibt unangetastet, jede neue Domain liegt in
`clients/<domain>.py`. Die Funktionen nutzen bewusst die privaten
Request-Helper des `ApiClient` (`_get`/`_write` und `_workspace_prefix`) —
dieses Modul ist ein paket-internes Friend-Modul DESSELBEN Adapters (gleiche
Fehler-Uebersetzung in `ToolError`, gleiche Timeouts), keine externe API.

Pfade: Welle-2-Router `kb.py` unter `/v1/workspaces/{ws_id}`. Der
Promote-Pfad (`POST .../wa-artifacts/{id}/promote`, Router `wa_artifacts.py`)
existiert seit WP14; sein `target_resource_id` ist ein QUERY-Parameter — das
Tool ist seit WP19 registriert.
"""

from __future__ import annotations

from uuid import UUID

from who2be_mcp.client import ApiClient
from who2be_models import (
    EdgeType,
    KbEdgeCreate,
    KbEdgeRead,
    KbNeighbor,
    KbNodeCreate,
    KbNodeRead,
    KbNodeUpdate,
    KbSearchHit,
    ResourceRead,
)


async def search_kb(client: ApiClient, query: str, limit: int = 20) -> list[KbSearchHit]:
    """`GET .../kb-search?q=&limit=` — rangsortierte KB-Treffer (Anker
    ``node:<id>`` + Snippet); per Konstruktion nie WorkArea-Inhalte."""
    params = {"q": query, "limit": str(limit)}
    payload = await client._get(f"{client._workspace_prefix}/kb-search", params=params)
    return [KbSearchHit.model_validate(item) for item in payload]


async def create_node(client: ApiClient, data: KbNodeCreate) -> KbNodeRead:
    """`POST .../kb/nodes` — belegte Aussage anlegen; `source_ref_kind` und die
    Quell-Areas leitet der Server ab (422 `anchor_unresolvable` reicht der
    Client als `ToolError` mit dem API-`detail` durch)."""
    payload = await client._write("POST", f"{client._workspace_prefix}/kb/nodes", data)
    return KbNodeRead.model_validate(payload)


async def update_node(client: ApiClient, node_id: UUID, data: KbNodeUpdate) -> KbNodeRead:
    """`PATCH .../kb/nodes/{id}` — Teilupdate mit Tier-Regeln (Serverlogik O);
    422 `tier_upgrade_forbidden` kommt als `ToolError`-Detail beim Agenten an."""
    payload = await client._write("PATCH", f"{client._workspace_prefix}/kb/nodes/{node_id}", data)
    return KbNodeRead.model_validate(payload)


async def create_edge(client: ApiClient, data: KbEdgeCreate) -> KbEdgeRead:
    """`POST .../kb/edges` — getypte, belegpflichtige Kante in EINER
    Transaktion; die 422er (`evidence_missing`/`anchor_unresolvable`/
    `correlation_underpowered` mit tatsaechlichem n) reicht der Client als
    `ToolError` mit dem API-`detail` durch."""
    payload = await client._write("POST", f"{client._workspace_prefix}/kb/edges", data)
    return KbEdgeRead.model_validate(payload)


async def neighbors(
    client: ApiClient, anchor: str, edge_type: EdgeType | None = None, depth: int = 1
) -> list[KbNeighbor]:
    """`GET .../kb/neighbors?anchor=&type=&depth=` — Nachbar-Nodes; `co_n`
    traegt bei `co_occurs_with` immer die Fallzahl (Spec O)."""
    params: dict[str, str] = {"anchor": anchor, "depth": str(depth)}
    if edge_type is not None:
        params["type"] = edge_type.value
    payload = await client._get(f"{client._workspace_prefix}/kb/neighbors", params=params)
    return [KbNeighbor.model_validate(item) for item in payload]


async def promote_artifact(
    client: ApiClient, artifact_id: UUID, target_resource_id: UUID | None = None
) -> ResourceRead:
    """`POST .../wa-artifacts/{id}/promote?target_resource_id=` — WorkArea-
    Artifact als Resource-DRAFT kuratieren (nie direkt active, Spec G).

    `target_resource_id` ist ein QUERY-Parameter (Router `wa_artifacts.py`,
    `Annotated[UUID | None, Query()]`), kein Body-Feld: die Route nimmt gar
    keinen Body entgegen, ein mitgeschickter waere still ignoriert worden —
    der Promote haette dann kommentarlos eine NEUE Resource angelegt, statt
    die benannte zu ergaenzen. Der Request geht daher bewusst body-los raus.
    """
    params = None if target_resource_id is None else {"target_resource_id": str(target_resource_id)}
    payload = await client._write(
        "POST",
        f"{client._workspace_prefix}/wa-artifacts/{artifact_id}/promote",
        None,
        params=params,
    )
    return ResourceRead.model_validate(payload)
