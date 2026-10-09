"""Export und Import einer Organisation (ADR-0055 §4.6, R6).

Betreiber-Werkzeug `who2be-org-transfer`: Rueckgabe einer Organisation nach
Art. 28 Abs. 3 lit. g DSGVO, Wiederherstellung einer einzelnen Org und spaeter
der Umzug in eine andere Instanz. Gemeinsame Datenbank mit RLS bleibt das
Trennmodell (Owner-Entscheidung 2026-09-30); dieses Modul ist der Weg, eine
Org aus ihr herauszuloesen und wieder einzusetzen.

**Archiv** (`format_version` 1): ein tar mit

* `postgres/<tabelle>.jsonl` — je Datensatz eine `to_jsonb`-Zeile ohne
  generierte Spalten, byteweise sortiert. Die Datei ist zugleich die Pruefsumme
  der Tabelle: dieselben Zeilen ergeben dieselben Bytes.
* `tablestore/<workspace_id>/<area_id>.sqlite` — konsistenter Snapshot je
  WorkArea (`TableStore.snapshot_to`, ADR-0049).
* `blobs/<workspace_id>/<sha256>` — die Objekte des BlobStores (ADR-0048).
* `manifest.json` als letztes Mitglied: Org, Workspaces, angewandte
  Migrationen, Zeilenzahl und sha256 je Datei.

**Was nicht im Archiv liegt bzw. nicht importiert wird** (Owner-Entscheidung
2026-10-01): Zugangsdaten (`CREDENTIAL_TABLES`, W3) liegen nie im Archiv —
nach einem Import werden Agenten-Tokens, MCP-Connectoren und Einladungen neu
ausgestellt. Entitlements und Verbrauch (`EXPORT_ONLY_TABLES`, W1) werden
exportiert, aber nicht importiert: `org_entitlement` schreiben nur die
benannten Quellen (ADR-0028/0029). Nutzer-IDs bleiben unveraendert (W2), ein
Mapping auf Konten einer fremden Instanz ist ein Folgepaket.

**Import ist fail-closed.** Er prueft das ganze Archiv, bevor er schreibt:
Pruefsummen, Migrationsstand (identische Menge), dass jede Zeile zur Archiv-Org
gehoert und dass jeder Fremdschluessel innerhalb des Archivs bleibt. Danach
schreibt er Postgres in einer Transaktion, die SQLite-Dateien und Blobs vor
dem COMMIT; scheitert ein Schritt, wird zurueckgerollt und die geschriebenen
Dateien und Objekte werden wieder entfernt. IDs werden nicht umgeschrieben —
Inhalte tragen IDs inline (`{{resource:<id>}}`) —, eine Kollision bricht ab.
Eine Org ueber sich selbst zurueckzuspielen heisst deshalb: erst Org-Purge,
dann Import.

Laeuft wie `who2be-purge` als Owner-Verbindung (`DATABASE_URL`, RLS-Bypass).
Das Archiv verlaesst den Prozess nur verschluesselt: der Export verlangt einen
gpg-Empfaenger und schreibt ueber `gpg --encrypt` (W4); einen Klartext-Pfad
hat das CLI nicht. Der Import liest das entschluesselte Archiv aus einer Datei
oder von stdin (`gpg -d archiv.gpg | who2be-org-transfer import`).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any
from uuid import UUID

import asyncpg

from who2be_api.blobstore import (
    BlobNotFoundError,
    BlobStorePort,
    blob_key,
    build_blob_store,
    workspace_prefix,
)
from who2be_api.core.config import get_settings
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.tablestore import TableStore

FORMAT_NAME = "who2be-org-transfer"
FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"

#: Instanzweite Tabellen ohne Mandant — nie Teil einer Org. `routine_run` und
#: `worker_heartbeat` sind das Laufprotokoll des Workers (Migration 0102).
GLOBAL_TABLES = frozenset(
    {
        "schema_migrations",
        "oauth_client",
        "processed_webhook_event",
        "account_deletion",
        "routine_run",
        "worker_heartbeat",
    }
)
#: Zugangsdaten (Token-Hashes, OAuth-Codes, offene Einladungen) — nie im
#: Archiv (Owner-Entscheidung W3 = A). Ein Archiv geht bei der Rueckgabe an
#: den Kunden; Credential-Material hat dort nichts zu suchen.
CREDENTIAL_TABLES = frozenset(
    {"api_token", "oauth_authorization_code", "oauth_refresh_token", "workspace_invitation"}
)
#: Entitlement und Verbrauch: exportiert (Rueckgabe), nie importiert (W1 = A).
EXPORT_ONLY_TABLES = frozenset({"org_entitlement", "entitlement_history", "mcp_usage"})

# Abhaengigkeiten, die kein Fremdschluessel ausdrueckt: der BEFORE-INSERT-
# Trigger von `status_history` leitet `workspace_id` aus der Entity ab
# (Migration 0092) und findet sie nur, wenn sie schon eingefuegt ist.
_EXTRA_DEPENDENCIES: Mapping[str, tuple[str, ...]] = {
    "status_history": (
        "persona",
        "playbook",
        "resource",
        "system_prompt_template",
        "external_tool",
    ),
}

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

_COLUMNS_SQL = """
SELECT c.relname AS table_name,
       a.attname AS column_name,
       a.attgenerated <> '' AS is_generated,
       a.attidentity <> '' AS is_identity
  FROM pg_class c
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
 WHERE c.relnamespace = current_schema()::regnamespace
   AND c.relkind = 'r'
 ORDER BY c.relname, a.attnum
"""

_FOREIGN_KEYS_SQL = """
SELECT src.relname AS table_name,
       dst.relname AS ref_table,
       ARRAY(SELECT a.attname
               FROM unnest(k.conkey) WITH ORDINALITY u(n, o)
               JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.n
              ORDER BY u.o) AS columns,
       ARRAY(SELECT a.attname
               FROM unnest(k.confkey) WITH ORDINALITY u(n, o)
               JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.n
              ORDER BY u.o) AS ref_columns
  FROM pg_constraint k
  JOIN pg_class src ON src.oid = k.conrelid
  JOIN pg_class dst ON dst.oid = k.confrelid
 WHERE k.contype = 'f'
   AND k.connamespace = current_schema()::regnamespace
 ORDER BY 1, 2, 3
"""


class OrgTransferError(Exception):
    """Export oder Import abgebrochen; die Meldung ist fuer den Betreiber."""


# --- Schema ------------------------------------------------------------------


@dataclass(frozen=True)
class TableInfo:
    """Eine Tabelle des Schemas, wie Export und Import sie sehen."""

    name: str
    columns: tuple[str, ...]
    generated: tuple[str, ...]
    has_identity: bool
    mode: str  # "import" | "export_only" | "skip"

    @property
    def has_workspace(self) -> bool:
        return "workspace_id" in self.columns

    @property
    def has_org(self) -> bool:
        return "org_id" in self.columns


@dataclass(frozen=True)
class ForeignKey:
    table: str
    ref_table: str
    columns: tuple[str, ...]
    ref_columns: tuple[str, ...]


@dataclass(frozen=True)
class Schema:
    tables: dict[str, TableInfo]
    foreign_keys: tuple[ForeignKey, ...]

    def import_order(self) -> list[str]:
        """Importierbare Tabellen in Fremdschluessel-Reihenfolge (Eltern zuerst)."""
        names = {n for n, t in self.tables.items() if t.mode == "import"}
        deps: dict[str, set[str]] = {n: set() for n in names}
        for fk in self.foreign_keys:
            if fk.table in names and fk.ref_table in names and fk.table != fk.ref_table:
                deps[fk.table].add(fk.ref_table)
        for table, parents in _EXTRA_DEPENDENCIES.items():
            if table in names:
                deps[table].update(p for p in parents if p in names)
        order: list[str] = []
        ready = sorted(n for n, d in deps.items() if not d)
        while ready:
            current = ready.pop(0)
            order.append(current)
            for name in sorted(names):
                if current in deps[name]:
                    deps[name].discard(current)
                    if not deps[name] and name not in order and name not in ready:
                        ready.append(name)
            ready.sort()
        if len(order) != len(names):
            cyclic = sorted(names - set(order))
            raise OrgTransferError(f"Zyklische Fremdschluessel, keine Import-Reihenfolge: {cyclic}")
        return order


def _classify(name: str, columns: Sequence[str]) -> str:
    if name in GLOBAL_TABLES or name in CREDENTIAL_TABLES:
        return "skip"
    if name in EXPORT_ONLY_TABLES:
        return "export_only"
    if name == "organization" or "workspace_id" in columns or "org_id" in columns:
        return "import"
    # Fail-closed: eine neue Tabelle ohne Mandantenspalte ist weder sicher
    # global noch sicher Teil der Org. Wer sie anlegt, entscheidet hier.
    raise OrgTransferError(
        f"Tabelle {name!r} hat weder workspace_id noch org_id und keine Klasse in "
        "core/org_transfer.py — dort als global, Zugangsdaten oder Org-Tabelle eintragen."
    )


async def load_schema(conn: asyncpg.Connection) -> Schema:
    """Liest Tabellen und Fremdschluessel des aktuellen Schemas (`search_path`)."""
    columns: dict[str, list[str]] = {}
    generated: dict[str, list[str]] = {}
    identity: dict[str, bool] = {}
    for row in await conn.fetch(_COLUMNS_SQL):
        table = row["table_name"]
        columns.setdefault(table, [])
        generated.setdefault(table, [])
        identity.setdefault(table, False)
        if row["is_generated"]:
            generated[table].append(row["column_name"])
        else:
            columns[table].append(row["column_name"])
        identity[table] = identity[table] or bool(row["is_identity"])
    tables = {
        name: TableInfo(
            name=name,
            columns=tuple(cols),
            generated=tuple(generated[name]),
            has_identity=identity[name],
            mode=_classify(name, cols),
        )
        for name, cols in columns.items()
    }
    fks = tuple(
        ForeignKey(
            table=row["table_name"],
            ref_table=row["ref_table"],
            columns=tuple(row["columns"]),
            ref_columns=tuple(row["ref_columns"]),
        )
        for row in await conn.fetch(_FOREIGN_KEYS_SQL)
    )
    return Schema(tables=tables, foreign_keys=fks)


async def applied_migrations(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    return [row["version"] for row in rows]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _scope(table: TableInfo) -> tuple[str, bool, bool]:
    """WHERE-Klausel der Org-Zeilen; dazu, ob `$1` (Org) bzw. `$2` (Workspaces) vorkommt."""
    if table.name == "organization":
        return "id = $1", True, False
    if table.name == "workspace":
        return "org_id = $1", True, False
    if table.has_org and table.has_workspace:
        return "(org_id = $1 OR workspace_id = ANY($2::uuid[]))", True, True
    if table.has_workspace:
        return "workspace_id = ANY($1::uuid[])", False, True
    return "org_id = $1", True, False


def _digest_lines(lines: Iterable[str]) -> bytes:
    """Kanonische Bytes einer Tabelle: Zeilen byteweise sortiert, je mit `\\n`."""
    ordered = sorted(lines, key=lambda line: line.encode("utf-8"))
    return "".join(f"{line}\n" for line in ordered).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sqlite_content_digest(path: Path) -> str:
    """Pruefsumme des INHALTS einer SQLite-Datei, unabhaengig vom Seitenlayout.

    Die Datei-Bytes taugen dafuer nicht: `VACUUM INTO` zaehlt den Schema-Cookie
    im Header hoch, derselbe Inhalt ergibt nach einem Round-Trip andere Bytes.
    Der sortierte SQL-Dump ist dagegen eine Funktion des Inhalts.
    """
    connection = sqlite3.connect(str(path))
    try:
        lines = list(connection.iterdump())
    finally:
        connection.close()
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)
    return _sha256(_digest_lines(lines))


# --- Export ------------------------------------------------------------------


@dataclass
class ExportResult:
    manifest: dict[str, Any]

    @property
    def row_count(self) -> int:
        return sum(int(t["rows"]) for t in self.manifest["tables"].values())


def _add(tar: tarfile.TarFile, name: str, data: bytes, mtime: float) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    info.mtime = mtime
    tar.addfile(info, io.BytesIO(data))


async def export_org(
    conn: asyncpg.Connection,
    org_id: UUID,
    sink: IO[bytes],
    *,
    blob_store: BlobStorePort | None,
    table_store: TableStore,
    now: datetime | None = None,
) -> ExportResult:
    """Schreibt das Archiv der Org als tar-Stream nach `sink`.

    `sink` bekommt Klartext; das CLI haengt dort `gpg --encrypt` an.
    """
    moment = now or datetime.now(UTC)
    mtime = moment.timestamp()
    await conn.execute("SET TIME ZONE 'UTC'")
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        exists = await conn.fetchval("SELECT 1 FROM organization WHERE id = $1", org_id)
        if exists is None:
            raise OrgTransferError(f"Organisation {org_id} existiert nicht.")
        schema = await load_schema(conn)
        migrations = await applied_migrations(conn)
        workspace_ids = [
            row["id"]
            for row in await conn.fetch(
                "SELECT id FROM workspace WHERE org_id = $1 ORDER BY id", org_id
            )
        ]
        table_files: dict[str, bytes] = {}
        tables_manifest: dict[str, Any] = {}
        for name in sorted(schema.tables):
            table = schema.tables[name]
            if table.mode == "skip":
                continue
            where, uses_org, uses_ws = _scope(table)
            params: list[object] = []
            if uses_org:
                params.append(org_id)
            if uses_ws:
                params.append(workspace_ids)
            sql = (
                f"SELECT (to_jsonb(t) - ${len(params) + 1}::text[])::text AS line "
                f"FROM {_quote(name)} t WHERE {where}"
            )
            rows = await conn.fetch(sql, *params, list(table.generated))
            data = _digest_lines(row["line"] for row in rows)
            table_files[name] = data
            tables_manifest[name] = {
                "mode": table.mode,
                "rows": len(rows),
                "columns": list(table.columns),
                "sha256": _sha256(data),
            }
        areas = [
            (row["workspace_id"], row["id"])
            for row in await conn.fetch(
                "SELECT workspace_id, id FROM work_area WHERE workspace_id = ANY($1::uuid[]) "
                "ORDER BY workspace_id, id",
                workspace_ids,
            )
        ]
        blob_rows = await conn.fetch(
            "SELECT workspace_id, sha256 FROM wa_blob WHERE workspace_id = ANY($1::uuid[]) "
            "ORDER BY workspace_id, sha256",
            workspace_ids,
        )

    if blob_rows and blob_store is None:
        raise OrgTransferError(
            f"Die Org hat {len(blob_rows)} Blob(s), aber kein BlobStore ist konfiguriert "
            "(WHO2BE_BLOBSTORE_*) — ein Export ohne die Objekte waere unvollstaendig."
        )

    manifest: dict[str, Any] = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "created_at": moment.isoformat(),
        "org_id": str(org_id),
        "workspace_ids": [str(ws) for ws in workspace_ids],
        "migrations": migrations,
        "excluded_tables": sorted(CREDENTIAL_TABLES),
        "tables": tables_manifest,
        "tablestores": {},
        "blobs": {},
        "missing_blobs": [],
    }

    tar = tarfile.open(fileobj=sink, mode="w|", format=tarfile.PAX_FORMAT)
    try:
        for name, data in table_files.items():
            _add(tar, f"postgres/{name}.jsonl", data, mtime)

        with tempfile.TemporaryDirectory(prefix="who2be-org-export-") as tmp:
            for ws, area in areas:
                if not table_store.db_path(ws, area).is_file():
                    continue
                target = Path(tmp) / f"{area}.sqlite"
                await table_store.snapshot_to(ws, area, target)
                content_sha = _sqlite_content_digest(target)
                data = target.read_bytes()
                target.unlink()
                member = f"tablestore/{ws}/{area}.sqlite"
                _add(tar, member, data, mtime)
                manifest["tablestores"][member] = {
                    "sha256": _sha256(data),
                    "content_sha256": content_sha,
                    "bytes": len(data),
                }

        if blob_store is not None:
            for ws in workspace_ids:
                for key in await blob_store.list_keys(workspace_prefix(ws)):
                    try:
                        data = await blob_store.get(key)
                    except BlobNotFoundError:
                        continue
                    _add(tar, key, data, mtime)
                    manifest["blobs"][key] = {"sha256": _sha256(data), "bytes": len(data)}
            for row in blob_rows:
                key = blob_key(row["workspace_id"], row["sha256"])
                if key not in manifest["blobs"]:
                    manifest["missing_blobs"].append(key)

        _add(tar, MANIFEST_NAME, _manifest_bytes(manifest), mtime)
    finally:
        tar.close()
    return ExportResult(manifest=manifest)


def _manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


# --- Archiv lesen und pruefen ------------------------------------------------


@dataclass
class Archive:
    manifest: dict[str, Any]
    members: dict[str, bytes]

    @property
    def org_id(self) -> str:
        return str(self.manifest["org_id"])


def read_archive(data: bytes) -> Archive:
    """Liest ein entschluesseltes Archiv vollstaendig ein und prueft seine Pruefsummen."""
    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            for info in tar:
                if not info.isfile():
                    raise OrgTransferError(
                        f"Archiv enthaelt einen Nicht-Datei-Eintrag: {info.name}"
                    )
                if info.name in members:
                    raise OrgTransferError(f"Archiv enthaelt {info.name} doppelt.")
                extracted = tar.extractfile(info)
                if extracted is None:  # pragma: no cover - isfile() schliesst das aus
                    raise OrgTransferError(f"Archiv-Eintrag {info.name} nicht lesbar.")
                members[info.name] = extracted.read()
    except tarfile.TarError as exc:
        raise OrgTransferError(
            f"Kein lesbares Archiv ({exc}). Ist es noch verschluesselt? "
            "Erst `gpg --decrypt`, dann importieren."
        ) from exc

    raw = members.pop(MANIFEST_NAME, None)
    if raw is None:
        raise OrgTransferError("Archiv ohne manifest.json.")
    manifest = json.loads(raw)
    if manifest.get("format") != FORMAT_NAME:
        raise OrgTransferError("Kein Who2Be-Org-Archiv (format).")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise OrgTransferError(
            f"Archiv-Format {manifest.get('format_version')} wird nicht unterstuetzt "
            f"(erwartet {FORMAT_VERSION})."
        )

    expected: dict[str, str] = {}
    for name, entry in manifest["tables"].items():
        expected[f"postgres/{name}.jsonl"] = entry["sha256"]
    for section in ("tablestores", "blobs"):
        for member, entry in manifest[section].items():
            expected[member] = entry["sha256"]
    unexpected = sorted(set(members) - set(expected))
    missing = sorted(set(expected) - set(members))
    if unexpected or missing:
        raise OrgTransferError(
            f"Archiv passt nicht zum Manifest: fehlend {missing}, unerwartet {unexpected}."
        )
    for member, sha in expected.items():
        if _sha256(members[member]) != sha:
            raise OrgTransferError(f"Pruefsumme von {member} stimmt nicht — Archiv beschaedigt.")
    return Archive(manifest=manifest, members=members)


def _parse_rows(archive: Archive, table: str) -> list[dict[str, Any]]:
    data = archive.members[f"postgres/{table}.jsonl"].decode("utf-8")
    return [json.loads(line) for line in data.splitlines() if line]


def _check_tenancy(
    table: TableInfo,
    rows: Sequence[Mapping[str, Any]],
    org_id: str,
    workspace_ids: set[str],
) -> None:
    """Jede Zeile gehoert zur Archiv-Org — sonst schriebe der Import in einen fremden Mandanten."""
    expected_columns = set(table.columns)
    for row in rows:
        if set(row) != expected_columns:
            raise OrgTransferError(
                f"{table.name}: Spalten im Archiv weichen vom Schema ab "
                f"({sorted(set(row) ^ expected_columns)})."
            )
        if table.name == "organization":
            ok = row["id"] == org_id
        elif table.name == "workspace":
            ok = row["org_id"] == org_id and row["id"] in workspace_ids
        else:
            ws = row.get("workspace_id") if table.has_workspace else None
            org = row.get("org_id") if table.has_org else None
            ws_ok = ws in workspace_ids
            org_ok = org == org_id
            if table.has_workspace and table.has_org:
                # Eine der beiden Spalten darf leer sein (org-weite Zeile ohne
                # Workspace); die gesetzte muss zur Archiv-Org gehoeren, und
                # mindestens eine muss gesetzt sein.
                ok = (ws_ok or ws is None) and (org_ok or org is None) and (ws_ok or org_ok)
            elif table.has_workspace:
                ok = ws_ok
            else:
                ok = org_ok
        if not ok:
            raise OrgTransferError(
                f"{table.name}: Zeile gehoert nicht zur Org {org_id} — Import abgebrochen "
                "(Mandantentrennung)."
            )


def _check_references(schema: Schema, rows: Mapping[str, list[dict[str, Any]]]) -> None:
    """Jeder Fremdschluessel zwischen Org-Tabellen zeigt auf eine Zeile des Archivs.

    Ohne diese Pruefung koennte ein manipuliertes Archiv eine Zeile der Org an
    ein Objekt eines anderen Mandanten haengen, das im Ziel schon existiert —
    der Fremdschluessel waere erfuellt, die Grenze nicht.
    """
    keys: dict[tuple[str, tuple[str, ...]], set[tuple[Any, ...]]] = {}
    for fk in schema.foreign_keys:
        if fk.table not in rows:
            continue
        ref = schema.tables.get(fk.ref_table)
        if ref is None or ref.mode != "import":
            # Verweise auf globale Tabellen (z. B. oauth_client) bzw. nicht
            # importierte Tabellen prueft der Fremdschluessel der DB.
            continue
        index = (fk.ref_table, fk.ref_columns)
        if index not in keys:
            # Fail-closed: fehlt die Elterntabelle im Archiv, gilt sie als leer —
            # sonst haengte eine Zeile an einem Objekt, das schon im Ziel liegt.
            keys[index] = {tuple(r[c] for c in fk.ref_columns) for r in rows.get(fk.ref_table, [])}
        for row in rows[fk.table]:
            value = tuple(row[c] for c in fk.columns)
            if any(v is None for v in value):
                continue
            if value not in keys[index]:
                raise OrgTransferError(
                    f"{fk.table}.{','.join(fk.columns)} verweist auf {fk.ref_table} "
                    "ausserhalb des Archivs — Import abgebrochen (Mandantentrennung)."
                )


# --- Import ------------------------------------------------------------------


@dataclass
class ImportResult:
    org_id: str
    rows: dict[str, int] = field(default_factory=dict)
    skipped_tables: list[str] = field(default_factory=list)
    tablestores: int = 0
    blobs: int = 0

    @property
    def row_count(self) -> int:
        return sum(self.rows.values())


def _member_ids(member: str, prefix: str, suffix: str) -> tuple[str, str]:
    rest = member.removeprefix(prefix).removesuffix(suffix)
    parts = rest.split("/")
    if len(parts) != 2:
        raise OrgTransferError(f"Unerwarteter Pfad im Archiv: {member}")
    try:
        return str(UUID(parts[0])), parts[1]
    except ValueError as exc:
        raise OrgTransferError(f"Unerwarteter Pfad im Archiv: {member}") from exc


async def import_org(
    conn: asyncpg.Connection,
    data: bytes,
    *,
    blob_store: BlobStorePort | None,
    table_store: TableStore,
) -> ImportResult:
    """Setzt eine Org aus einem entschluesselten Archiv ein (fail-closed)."""
    archive = read_archive(data)
    manifest = archive.manifest
    org_id = archive.org_id
    workspace_ids = set(manifest["workspace_ids"])

    await conn.execute("SET TIME ZONE 'UTC'")
    target_migrations = await applied_migrations(conn)
    if sorted(manifest["migrations"]) != target_migrations:
        only_archive = sorted(set(manifest["migrations"]) - set(target_migrations))
        only_target = sorted(set(target_migrations) - set(manifest["migrations"]))
        raise OrgTransferError(
            "Migrationsstand von Archiv und Ziel weicht ab — Ziel erst migrieren bzw. "
            f"passende Version verwenden (nur Archiv: {only_archive}, nur Ziel: {only_target})."
        )

    schema = await load_schema(conn)
    order = schema.import_order()
    unknown = sorted(set(manifest["tables"]) - set(schema.tables))
    if unknown:
        raise OrgTransferError(f"Archiv enthaelt unbekannte Tabellen: {unknown}")
    leaked = sorted(set(manifest["tables"]) & CREDENTIAL_TABLES)
    if leaked:
        raise OrgTransferError(f"Archiv enthaelt Zugangsdaten-Tabellen: {leaked}")
    # Der Export schreibt jede importierbare Tabelle, auch leer, und der
    # Migrationsstand ist identisch. Fehlt eine, ist das Archiv manipuliert —
    # eine fehlende Elterntabelle wuerde sonst die Referenzpruefung aushebeln.
    missing = sorted(set(order) - set(manifest["tables"]))
    if missing:
        raise OrgTransferError(
            f"Archiv unvollstaendig, es fehlen Org-Tabellen: {missing} — Import abgebrochen."
        )

    rows: dict[str, list[dict[str, Any]]] = {}
    for name in order:
        table_rows = _parse_rows(archive, name)
        _check_tenancy(schema.tables[name], table_rows, org_id, workspace_ids)
        rows[name] = table_rows
    if [r["id"] for r in rows.get("organization", [])] != [org_id]:
        raise OrgTransferError("Archiv enthaelt die Organisation nicht genau einmal.")
    if {r["id"] for r in rows.get("workspace", [])} != workspace_ids:
        raise OrgTransferError("Workspaces im Archiv passen nicht zum Manifest.")
    _check_references(schema, rows)

    areas = {(r["workspace_id"], r["id"]) for r in rows.get("work_area", [])}
    stores: list[tuple[UUID, UUID, bytes, str]] = []
    for member, entry in sorted(manifest["tablestores"].items()):
        ws, file_name = _member_ids(member, "tablestore/", "")
        area = file_name.removesuffix(".sqlite")
        if not file_name.endswith(".sqlite") or (ws, area) not in areas:
            raise OrgTransferError(f"{member} gehoert zu keiner WorkArea des Archivs.")
        target = table_store.db_path(UUID(ws), UUID(area))
        if target.exists():
            raise OrgTransferError(f"Tabellen-Store existiert im Ziel bereits: {target}")
        stores.append((UUID(ws), UUID(area), archive.members[member], entry["content_sha256"]))

    blobs: list[tuple[str, bytes, str]] = []
    media_types = {
        (r["workspace_id"], r["sha256"]): r["media_type"] for r in rows.get("wa_blob", [])
    }
    for member in sorted(manifest["blobs"]):
        ws, sha = _member_ids(member, "blobs/", "")
        if ws not in workspace_ids or not _SHA256_HEX.fullmatch(sha):
            raise OrgTransferError(f"Blob {member} gehoert zu keinem Workspace des Archivs.")
        content = archive.members[member]
        if _sha256(content) != sha:
            raise OrgTransferError(f"Blob {member}: Inhalt passt nicht zum Namen.")
        media_type = media_types.get((ws, sha), "application/octet-stream")
        blobs.append((blob_key(ws, sha), content, media_type))
    if blobs and blob_store is None:
        raise OrgTransferError(
            f"Archiv enthaelt {len(blobs)} Blob(s), im Ziel ist kein BlobStore konfiguriert."
        )

    # Was importiert wird, entscheidet das Schema des Ziels, nicht das Manifest:
    # `rows` enthaelt nur Tabellen der Klasse "import" (`import_order`).
    result = ImportResult(
        org_id=org_id,
        skipped_tables=sorted(
            n
            for n, e in manifest["tables"].items()
            if schema.tables[n].mode != "import" and e["rows"]
        ),
    )
    written_files: list[Path] = []
    written_blobs: list[str] = []
    try:
        async with conn.transaction():
            for name in order:
                if name not in rows:
                    continue
                result.rows[name] = await _insert_table(
                    conn, schema.tables[name], rows[name], manifest["tables"][name]["sha256"]
                )
            for ws_id, area_id, content, content_sha in stores:
                written_files.append(
                    _write_store(table_store, ws_id, area_id, content, content_sha)
                )
            result.tablestores = len(written_files)
            if blob_store is not None:
                for key, content, media_type in blobs:
                    if await blob_store.exists(key):
                        continue
                    await blob_store.put(key, content, media_type)
                    written_blobs.append(key)
            result.blobs = len(blobs)
    except BaseException:
        for path in written_files:
            for suffix in ("", "-wal", "-shm"):
                Path(f"{path}{suffix}").unlink(missing_ok=True)
        if blob_store is not None:
            for key in written_blobs:
                await blob_store.delete(key)
        raise
    return result


async def _insert_table(
    conn: asyncpg.Connection,
    table: TableInfo,
    rows: Sequence[Mapping[str, Any]],
    expected_sha: str,
) -> int:
    if not rows:
        return 0
    cols = ", ".join(_quote(c) for c in table.columns)
    overriding = " OVERRIDING SYSTEM VALUE" if table.has_identity else ""
    sql = (
        f"INSERT INTO {_quote(table.name)} AS t ({cols}){overriding} "
        f"SELECT {cols} FROM jsonb_populate_recordset(NULL::{_quote(table.name)}, $1::jsonb) "
        "RETURNING (to_jsonb(t) - $2::text[])::text AS line"
    )
    try:
        inserted = await conn.fetch(sql, json.dumps(list(rows)), list(table.generated))
    except asyncpg.UniqueViolationError as exc:
        raise OrgTransferError(
            f"{table.name}: Datensatz existiert im Ziel bereits ({exc.constraint_name}) — "
            "IDs werden nicht umgeschrieben. Bestehende Org erst purgen."
        ) from exc
    except asyncpg.ForeignKeyViolationError as exc:
        raise OrgTransferError(
            f"{table.name}: Fremdschluessel nicht erfuellt ({exc.constraint_name})."
        ) from exc
    # Was in der Tabelle ankommt, muss Byte fuer Byte dem Export entsprechen —
    # ein Trigger oder Typ, der still etwas aendert, faellt hier auf.
    if _sha256(_digest_lines(r["line"] for r in inserted)) != expected_sha:
        raise OrgTransferError(f"{table.name}: importierte Zeilen weichen vom Archiv ab.")
    return len(inserted)


def _write_store(
    table_store: TableStore, ws: UUID, area: UUID, content: bytes, content_sha: str
) -> Path:
    target = table_store.db_path(ws, area)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.import")
    staging.write_bytes(content)
    try:
        if _sqlite_content_digest(staging) != content_sha:
            raise OrgTransferError(f"Tabellen-Store {area}: Inhalt weicht vom Archiv ab.")
        if target.exists():
            raise OrgTransferError(f"Tabellen-Store existiert im Ziel bereits: {target}")
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)
    return target


# --- CLI ---------------------------------------------------------------------


async def _connect() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc


def _run_export(org_id: UUID, recipient: str, output: str) -> ExportResult:
    """Export durch `gpg --encrypt`: der Klartext verlaesst den Prozess nur als Pipe."""
    out_path: Path | None = None
    command = ["gpg", "--batch", "--yes", "--trust-model", "always", "--encrypt"]
    command += ["--recipient", recipient]
    stdout: Any = None
    if output == "-":
        stdout = sys.stdout.buffer
    else:
        out_path = Path(output)
        if out_path.exists():
            raise OrgTransferError(f"{out_path} existiert bereits — wird nicht ueberschrieben.")
        command += ["--output", str(out_path)]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout)
    except FileNotFoundError as exc:
        raise OrgTransferError("gpg ist nicht installiert — Export abgebrochen.") from exc
    assert process.stdin is not None

    async def _export() -> ExportResult:
        conn = await _connect()
        try:
            assert process.stdin is not None
            return await export_org(
                conn,
                org_id,
                process.stdin,
                blob_store=build_blob_store(),
                table_store=get_table_store(),
            )
        finally:
            await conn.close()

    failure: BaseException | None = None
    result: ExportResult | None = None
    try:
        result = asyncio.run(_export())
    except BrokenPipeError:
        failure = OrgTransferError("gpg hat die Eingabe abgebrochen.")
    except BaseException as exc:
        failure = exc
    finally:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
        code = process.wait()
    if failure is None and code != 0:
        failure = OrgTransferError(
            f"gpg ist mit Code {code} fehlgeschlagen (Empfaenger {recipient!r}?)."
        )
    if failure is not None:
        if out_path is not None:
            out_path.unlink(missing_ok=True)
        raise failure
    if out_path is not None:
        out_path.chmod(0o600)
    assert result is not None
    return result


def _run_import(source: str) -> ImportResult:
    data = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()

    async def _import() -> ImportResult:
        conn = await _connect()
        try:
            return await import_org(
                conn, data, blob_store=build_blob_store(), table_store=get_table_store()
            )
        finally:
            await conn.close()

    return asyncio.run(_import())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="who2be-org-transfer",
        description="Organisation exportieren (gpg-verschluesselt) oder importieren.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="Org als verschluesseltes Archiv exportieren")
    export.add_argument("--org-id", required=True, type=UUID)
    export.add_argument(
        "--recipient", required=True, help="gpg-Empfaenger (Key-ID, Fingerprint oder E-Mail)"
    )
    export.add_argument("--output", required=True, help="Zieldatei oder - fuer stdout")
    imp = sub.add_parser("import", help="entschluesseltes Archiv importieren")
    imp.add_argument("--input", default="-", help="Archivdatei oder - fuer stdin (Default)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "export":
            exported = _run_export(args.org_id, args.recipient, args.output)
            manifest = exported.manifest
            print(
                f"Export Org {manifest['org_id']}: {exported.row_count} Zeile(n) in "
                f"{len(manifest['tables'])} Tabelle(n), {len(manifest['tablestores'])} "
                f"Tabellen-Store(s), {len(manifest['blobs'])} Blob(s); "
                f"{len(manifest['missing_blobs'])} Blob(s) fehlten im Store.",
                file=sys.stderr,
            )
        else:
            imported = _run_import(args.input)
            skipped = ", ".join(imported.skipped_tables) or "keine"
            print(
                f"Import Org {imported.org_id}: {imported.row_count} Zeile(n), "
                f"{imported.tablestores} Tabellen-Store(s), {imported.blobs} Blob(s). "
                f"Nicht importiert (nur Export): {skipped}. Zugangsdaten neu ausstellen.",
                file=sys.stderr,
            )
    except OrgTransferError as exc:
        print(f"Abgebrochen: {exc}", file=sys.stderr)
        return 1
    return 0


def cli() -> None:
    """Console-Entrypoint fuer `who2be-org-transfer`."""
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
