"""Zwei vollstaendig bestueckte Mandanten fuer die Isolationstests (ADR-0055 §7).

Die Isolationstests (`test_tenant_isolation.py`) rufen jede Route und jedes
MCP-Tool als Mandant A mit Objekt-IDs von Mandant B auf. Damit das etwas
beweist, muss es die IDs auch geben: dieser Helfer legt fuer **beide**
Mandanten denselben Bestand an — je Objektart, die eine Route adressieren
kann, mindestens ein Objekt. Symmetrisch, weil die Kontrolle einer
Cross-Tenant-Probe derselbe Aufruf mit den **eigenen** IDs ist: nur so ist
eine 404 von A ein Befund an der Mandantengrenze und nicht eine kaputte Probe.

Jedes Objekt traegt einen Marker (`ISO-<A|B>-<hex>`) im Namen bzw. Text.
Taucht der Marker von B in einer Antwort an A auf, ist das ein Leck — auch
wenn keine ID von B darin steht (z. B. in einem Suchtreffer).

Daneben der Fingerabdruck: ein Hash ueber alle Zeilen, die einem Mandanten
gehoeren (jede Tabelle mit `workspace_id` bzw. `org_id`), als Superuser an RLS
vorbei gelesen. Vorher/nachher gleich heisst: kein Aufruf von A hat bei B
etwas geschrieben, auch nicht still mit 404 als Antwort.

Liegt im `testing`-Paket statt im Testordner, damit mypy und pytest das Modul
gleich aufloesen (Begruendung wie `api_helpers.py`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
from fastapi.testclient import TestClient

from who2be_api.blobstore import reset_blob_store, set_blob_store
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core import rate_limit
from who2be_api.core.config import get_settings
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.api_helpers import db_execute, db_fetchval
from who2be_api.testing.workspace_setup import fresh_user_id, setup_workspace


@contextmanager
def isolation_stores(base_dir: Path) -> Iterator[None]:
    """Blob- und Tabellen-Store im Speicher bzw. unter `base_dir`, Rate-Limit aus.

    Das Schreib-Rate-Limit (30/min je Token) wuerde die gut 150
    Schreibaufrufe eines Isolationslaufs mit 429 abbrechen; es ist dort
    nicht Gegenstand.
    """
    set_blob_store(MemoryBlobStore())
    set_table_store(TableStore(base_dir=base_dir))
    enabled = rate_limit.limiter.enabled
    rate_limit.limiter.enabled = False
    try:
        yield
    finally:
        rate_limit.limiter.enabled = enabled
        reset_table_store()
        reset_blob_store()


# Tool-Policy, mit der die Agenten beider Mandanten alles duerfen, was eine
# Policy freigeben kann. Die Isolationsprobe soll an der Mandantengrenze
# scheitern, nicht an einer fehlenden Capability — sonst beweist eine 403
# nichts. `memory_mode=auto`, damit Gedaechtnis-Eintraege sofort aktiv sind.
FULL_POLICY: dict[str, object] = {
    "playbook_read": "all",
    "resource_read": "all",
    "agent_read": "all",
    "persona_write": True,
    "playbook_write": True,
    "resource_write": True,
    "agent_write": True,
    "system_prompt_write": True,
    "feedback_resolve": True,
    "promote_retire": True,
    "external_tool_write": True,
    "workarea_write": True,
    "kb_write": True,
    "kb_edge_write": True,
    "case_triage": True,
    "memory_mode": "auto",
}

_BLOCKS = [
    {
        "id": "b1",
        "type": "paragraph",
        "content": [{"type": "text", "text": "Isolation body.", "styles": {}}],
    }
]

TABLE_SCHEMA: dict[str, object] = {
    "columns": [
        {"name": "occurred_at", "type": "timestamp"},
        {"name": "amount", "type": "numeric", "nullable": False},
        {"name": "purpose", "type": "text"},
    ],
    "dedupe_columns": ["occurred_at", "amount", "purpose"],
}


@dataclass
class Tenant:
    """Ein Mandant mit allen IDs, die eine Route adressieren kann.

    `ids` ist die Ersetzungstabelle fuer die Platzhalter der Routen- und
    Tool-Vorlagen (`{persona_id}` usw.); `forbidden` sind die Zeichenketten,
    die in keiner Antwort an den jeweils anderen Mandanten auftauchen duerfen.
    """

    label: str
    user_id: UUID
    workspace_id: UUID
    org_id: UUID
    marker: str
    human: dict[str, str]
    agent: dict[str, str] = field(default_factory=dict)
    agent_token: str = ""
    ids: dict[str, str] = field(default_factory=dict)

    @property
    def prefix(self) -> str:
        return f"/v1/workspaces/{self.workspace_id}"

    def forbidden(self) -> set[str]:
        """Alles, was bei einem fremden Mandanten nie erscheinen darf.

        Bewusst ohne `version` (die Zahl 1 steht ueberall) und ohne die
        Block-ID (`b1` stammt aus der Vorlage und ist nicht eindeutig).
        """
        skip = {"version", "block_id", "source_name", "invite_token"}
        values = {v for k, v in self.ids.items() if k not in skip}
        values |= {str(self.user_id), str(self.workspace_id), str(self.org_id), self.marker}
        return values


def _ok(response: Any, what: str) -> Any:
    assert 200 <= response.status_code < 300, f"Seed {what}: {response.status_code} {response.text}"
    return response.json()


def _org_of(workspace_id: UUID) -> UUID:
    org: UUID = db_fetchval("SELECT org_id FROM workspace WHERE id = $1", workspace_id)
    return org


def human_headers(user_id: UUID, email: str, jwt_secret: str) -> dict[str, str]:
    """Supabase-artiges HS256-JWT **mit** `email`-Claim.

    Der Claim ist noetig, weil `POST /v1/invitations/{token}/accept` die
    E-Mail der Einladung gegen den Claim prueft — ohne Claim prueft die Route
    nichts, und die Probe wuerde den Bearer-Token-Pfad statt der
    Mandantengrenze testen.
    """
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def seed_tenant(client: TestClient, label: str, jwt_secret: str) -> Tenant:
    """Legt einen Mandanten samt Bestand an (ueber die API, wie ein Nutzer)."""
    user_id = fresh_user_id()
    ws = setup_workspace(user_id)
    marker = f"ISO-{label}-{uuid4().hex[:10]}"
    email = f"{marker.lower()}@example.com"
    t = Tenant(
        label=label,
        user_id=user_id,
        workspace_id=ws,
        org_id=_org_of(ws),
        marker=marker,
        human=human_headers(user_id, email, jwt_secret),
    )
    p, h = t.prefix, t.human
    ids = t.ids
    ids["workspace_id"] = str(ws)
    ids["organization_id"] = str(t.org_id)
    ids["version"] = "1"
    ids["source_name"] = "bank"

    # Zweites Mitglied (editor), damit Mitglieder-Routen ein Ziel haben, das
    # nicht der letzte Admin ist.
    member = fresh_user_id()
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'editor')",
        ws,
        member,
    )
    ids["user_id"] = str(member)

    persona = _ok(
        client.post(
            f"{p}/personas",
            json={
                "name": f"{marker} Persona",
                "content": {
                    "description": marker,
                    "system_prompt": f"{marker} prompt",
                    "content": {"description": marker, "blocks": _BLOCKS},
                },
            },
            headers=h,
        ),
        "persona",
    )
    ids["persona_id"] = persona["id"]
    versions = _ok(client.get(f"{p}/personas/{persona['id']}/versions", headers=h), "versions")
    ids["version_id"] = versions[0]["id"]

    for key in ("playbook_id", "child_playbook_id"):
        pb = _ok(
            client.post(
                f"{p}/playbooks",
                json={
                    "name": f"{marker} {key}",
                    "content": {
                        "description": marker,
                        "body": f"1. {marker}",
                        "type": "workflow",
                        "tags": [marker.lower()],
                        "triggers": marker.lower(),
                    },
                },
                headers=h,
            ),
            key,
        )
        ids[key] = pb["id"]

    for key in ("resource_id", "child_resource_id"):
        res = _ok(
            client.post(
                f"{p}/resources",
                json={
                    "name": f"{marker} {key}",
                    "content": {"description": marker, "blocks": _BLOCKS, "tags": [marker.lower()]},
                },
                headers=h,
            ),
            key,
        )
        ids[key] = res["id"]

    tool = _ok(
        client.post(
            f"{p}/external_tools",
            json={
                "name": f"{marker} Tool",
                "content": {
                    "display_name": marker,
                    "mcp_server_name": f"{marker} MCP",
                    "tool_names": ["add_task"],
                    "usage_notes": marker,
                    "tags": [],
                },
            },
            headers=h,
        ),
        "external_tool",
    )
    ids["tool_id"] = tool["id"]

    tpl = _ok(
        client.post(
            f"{p}/system-prompts",
            json={"name": f"{marker} Template", "content": {"description": marker, "body": marker}},
            headers=h,
        ),
        "system_prompt",
    )
    ids["template_id"] = tpl["id"]

    agent = _ok(
        client.post(
            f"{p}/agents",
            json={"name": f"{marker} Agent", "tool_policy": FULL_POLICY},
            headers=h,
        ),
        "agent",
    )
    ids["agent_id"] = agent["id"]
    token = _ok(
        client.post(
            f"{p}/tokens", json={"name": f"{marker} tok", "agent_id": agent["id"]}, headers=h
        ),
        "token",
    )
    t.agent_token = token["token"]
    t.agent = {"Authorization": f"Bearer {token['token']}"}
    # Ein zweiter Token desselben Agenten: Ziel fuer Rotieren/Umbenennen/
    # Widerrufen, damit die Probe nicht den Token entwertet, mit dem sie laeuft.
    spare = _ok(
        client.post(
            f"{p}/tokens", json={"name": f"{marker} spare", "agent_id": agent["id"]}, headers=h
        ),
        "spare token",
    )
    ids["token_id"] = spare["id"]

    area = _ok(client.post(f"{p}/work-areas", json={"name": f"{marker} Area"}, headers=h), "area")
    ids["area_id"] = area["id"]
    _ok(
        client.put(
            f"{p}/work-areas/{area['id']}/grants/{agent['id']}", json={"level": "write"}, headers=h
        ),
        "grant",
    )
    artifact = _ok(
        client.post(
            f"{p}/work-areas/{area['id']}/artifacts",
            json={
                "title": marker,
                "content_md": f"{marker} Notiz.",
                "occurred_at": "2026-08-01T12:00:00Z",
            },
            headers=h,
        ),
        "artifact",
    )
    ids["artifact_id"] = artifact["id"]
    ids["block_id"] = artifact["blocks"][0]["block_id"]

    table = _ok(
        client.post(
            f"{p}/work-areas/{area['id']}/tables",
            json={"name": f"t_{label.lower()}", "schema": TABLE_SCHEMA},
            headers=h,
        ),
        "table",
    )
    ids["table_id"] = table["id"]
    _ok(
        client.post(
            f"{p}/wa-tables/{table['id']}/rows",
            json={
                "rows": [
                    {"occurred_at": "2026-08-01T12:00:00+00:00", "amount": 1, "purpose": marker}
                ]
            },
            headers=h,
        ),
        "rows",
    )

    # Nodes legt der Agent an: `update_node` darf nur der erstellende Agent
    # (oder ein Mensch ab editor), und die MCP-Gegenprobe laeuft als Agent.
    for key in ("node_id", "node2_id"):
        node = _ok(
            client.post(
                f"{p}/kb/nodes",
                json={
                    "content": f"{marker} {key}",
                    "tier": "hypothesis",
                    "source_ref": f"{artifact['id']}#{ids['block_id']}",
                    "occurred_at": "2026-08-01T00:00:00Z",
                },
                headers=t.agent,
            ),
            key,
        )
        ids[key] = node["id"]

    memory = _ok(
        client.post(
            f"{p}/agent-memories",
            json={
                "fact": f"{marker} Nutzer mag Indigo",
                "category": "preference",
                "importance": 7,
                "origin": "user_stated",
            },
            headers=t.agent,
        ),
        "memory",
    )
    ids["memory_id"] = memory["id"]

    feedback = _ok(
        client.post(
            f"{p}/feedback",
            json={
                "entity_type": "playbook",
                "entity_id": ids["playbook_id"],
                "signal": "outdated",
                "note": marker,
            },
            headers=t.agent,
        ),
        "feedback",
    )
    ids["feedback_id"] = feedback["id"]

    case = _ok(
        client.post(
            f"{p}/test-cases",
            json={
                "agent_id": agent["id"],
                "title": marker,
                "input": marker,
                "expected_behavior": marker,
            },
            headers=h,
        ),
        "test case",
    )
    ids["case_id"] = case["id"]

    # Zwei Einladungen: eine als Ziel fuer das Widerrufen, eine fuer die
    # Annahme — eine angenommene Einladung laesst sich nicht mehr widerrufen.
    # Die zweite lautet auf die eigene Adresse, damit die Gegenprobe (B nimmt
    # die eigene Einladung an) am E-Mail-Abgleich vorbeikommt; als Mitglied
    # bleibt B dabei Admin (DO NOTHING im Repository).
    invitation = _ok(
        client.post(
            f"{p}/invitations",
            json={"email": f"invitee-{marker.lower()}@example.com", "role": "viewer"},
            headers=h,
        ),
        "invitation",
    )
    ids["invitation_id"] = invitation["id"]
    own = _ok(
        client.post(f"{p}/invitations", json={"email": email, "role": "viewer"}, headers=h),
        "own invitation",
    )
    ids["invite_token"] = own["token"]
    return t


async def _fingerprint(conn: asyncpg.Connection, tenant: Tenant) -> dict[str, str]:
    rows = await conn.fetch(
        """
        SELECT c.table_name, c.column_name
          FROM information_schema.columns c
          JOIN information_schema.tables t
            ON t.table_schema = c.table_schema AND t.table_name = c.table_name
         WHERE c.table_schema = 'public'
           AND t.table_type = 'BASE TABLE'
           AND c.column_name IN ('workspace_id', 'org_id')
         ORDER BY 1, 2
        """
    )
    result: dict[str, str] = {}
    for row in rows:
        table, column = row["table_name"], row["column_name"]
        key = tenant.workspace_id if column == "workspace_id" else tenant.org_id
        digest = await conn.fetchval(
            f"SELECT count(*)::text || ':' || coalesce(md5(string_agg(x::text, '|' "
            f'ORDER BY x::text)), \'\') FROM "{table}" x WHERE "{column}" = $1',
            key,
        )
        result[f"{table}.{column}"] = digest
    for table, column, key in (
        ("workspace", "id", tenant.workspace_id),
        ("organization", "id", tenant.org_id),
    ):
        result[f"{table}.{column}"] = await conn.fetchval(
            f"SELECT count(*)::text || ':' || coalesce(md5(string_agg(x::text, '|')), '') "
            f'FROM "{table}" x WHERE "{column}" = $1',
            key,
        )
    return result


def fingerprint(tenant: Tenant) -> dict[str, str]:
    """Hash je Tabelle ueber alle Zeilen des Mandanten (Superuser, an RLS vorbei)."""
    return asyncio.run(fingerprint_async(tenant))


async def fingerprint_async(tenant: Tenant) -> dict[str, str]:
    """Wie `fingerprint`, fuer Aufrufer mit laufender Event-Loop."""
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        return await _fingerprint(conn, tenant)
    finally:
        await conn.close()


def ghost_of(t: Tenant) -> Tenant:
    """Ein Mandant, den es nicht gibt: dieselben Schluessel, nur Zufalls-IDs.

    Jede fremde Probe laeuft ein zweites Mal mit diesen IDs. Unterscheidet
    sich die Antwort auf B-IDs von der auf unbekannte IDs, verraet der
    Endpunkt, dass es das fremde Objekt gibt (Existenz-Orakel) — auch wenn er
    keine Daten herausgibt. Gleiche Antwort heisst: Fremdes wird wie
    Unbekanntes behandelt, und das ist die Mandantengrenze.
    """
    fresh = {k: str(uuid4()) for k in t.ids}
    fresh |= {"version": "1", "source_name": "bank", "block_id": uuid4().hex[:8]}
    fresh["invite_token"] = uuid4().hex + uuid4().hex
    return Tenant(
        label="ghost",
        user_id=uuid4(),
        workspace_id=uuid4(),
        org_id=uuid4(),
        marker=f"ISO-G-{uuid4().hex[:10]}",
        human=t.human,
        agent=t.agent,
        ids=fresh,
    )


#: Abweisung an der Mandantengrenze: fremd wie unbekannt.
DENIED = frozenset({403, 404})
#: Anker (`<artifact>#<block>`, `node:<id>`) loest die KB einheitlich mit 422
#: `anchor_unresolvable` auf ("kein ... im Lese-Scope",
#: `services/kb_anchors.py::_unresolvable`) — fuer unbekannte und fremde Anker
#: gleich. Ob das stimmt, prueft der Orakel-Vergleich. Obermenge von
#: `DENIED`, weil der fremde Workspace (V1) vorher am Workspace-Gate endet.
ANCHOR_DENIED = DENIED | {422}


def control_passes(status: int) -> bool:
    """Gegenprobe (B mit eigenen IDs): am Objekt-Lookup und an der Validierung vorbei.

    Fachliche Ablehnungen (400/409/410, z. B. ein offener Draft) zaehlen als
    bestanden — sie kommen erst nach dem Lookup. 403/404 hiesse, dass die
    Probe selbst das Objekt nicht trifft; 422, dass ihr Body kaputt ist.
    """
    return status < 500 and status not in (401, 403, 404, 422, 429)


def leaks(text: str, sent: str, other: Tenant) -> list[str]:
    """Spuren von `other` in einer Antwort, ausgenommen was selbst gesendet wurde."""
    return sorted(s for s in other.forbidden() if s in text and s not in sent)
