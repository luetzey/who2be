"""Integrationstests der WorkArea-/KB-Retention (WP20, ADR-0047/0048/0049).

Belegt auf der echten DB (Owner-Verbindung — wie der `who2be-purge`-Cron):

- **`retention_days`-Sweep:** Artifacts einer Area mit Frist verschwinden samt
  ihrer `wa_chunk`-Passagen, sobald `created_at` aelter als die Frist ist.
  Frische Artifacts derselben Area und beliebig alte Artifacts einer Area OHNE
  Frist (`retention_days IS NULL` = Default = unbegrenzt) bleiben.
- **Orphan-Blobs:** eine `wa_blob`-Zeile ohne referenzierendes Artifact und
  aelter als 24 h faellt samt Objekt aus dem Store; eine frische Zeile und eine
  referenzierte Zeile bleiben. Dazu der zweite Sweep: ein Objekt OHNE
  Katalog-Zeile faellt nur, wenn der Store sein Alter kennt (`BlobAgeSource`).
- **Tabellen-Store:** die SQLite-Datei einer geloeschten Area wird entfernt,
  die einer lebenden nicht — und ein Verzeichnis, dessen Workspace es nicht
  (mehr) gibt, bleibt defensiv unberuehrt.
- **GDPR-Export:** das Art.-20-Buendel traegt Areas, Artifacts,
  Blob-Metadaten, Tabellen-Zeilen, KB und Zugriffslog.

Laeuft gegen die zentral migrierte Test-DB (conftest: ``migrated_db``); Seeds
ueber ``who2be_api.testing.workspace_setup``.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.blobstore import blob_key
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.purge import (
    PurgeResult,
    cleanup_deleted_area_stores,
    cleanup_expired_artifacts,
    cleanup_orphan_blobs,
    run_retention_sweeps,
)
from who2be_api.main import app
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import ColumnSpec, ColumnType, TableStore
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

_T = TypeVar("_T")

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
_OCCURRED_AT = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

# 64 Hex-Zeichen — `blob_key` akzeptiert nur echte SHA-256-Hexdigests.
_SHA_ORPHAN = "a" * 64
_SHA_FRESH = "b" * 64
_SHA_LINKED = "c" * 64
_SHA_OBJECT_ONLY = "d" * 64


def _with_seed(body: Callable[[asyncpg.Connection, UUID, UUID], Awaitable[_T]]) -> _T:
    """Fuehrt ``body(conn, workspace_id, agent_id)`` gegen die migrierte DB aus.

    ``setup_workspace``/``cleanup_workspaces`` rufen intern ``asyncio.run``
    auf und muessen deshalb AUSSERHALB der Coroutine laufen (Muster
    test_workarea_migrations.py). Das Zugriffslog haengt seit 0080 nicht mehr
    am Agent-CASCADE und wird explizit abgeraeumt.
    """
    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)

    async def _run() -> _T:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID = await conn.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'retention-agent') RETURNING id",
                workspace_id,
                owner,
            )
            try:
                return await body(conn, workspace_id, agent_id)
            finally:
                await conn.execute(
                    "DELETE FROM agent_access_log WHERE workspace_id = $1", workspace_id
                )
                # `wa_blob` traegt KEINEN FK auf `workspace` (0075) und
                # ueberlebt das Org-CASCADE — sonst blieben die Zeilen als
                # Fremd-Muell fuer nachfolgende Sweeps in der Test-DB liegen.
                await conn.execute("DELETE FROM wa_blob WHERE workspace_id = $1", workspace_id)
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])


async def _insert_area(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    *,
    name: str,
    retention_days: int | None,
) -> UUID:
    area_id: UUID = await conn.fetchval(
        "INSERT INTO work_area (workspace_id, scope, owner_agent_id, name, retention_days) "
        "VALUES ($1, 'shared', NULL, $2, $3) RETURNING id",
        workspace_id,
        name,
        retention_days,
    )
    return area_id


async def _insert_artifact(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    area_id: UUID,
    *,
    title: str,
    created_at: datetime,
    content_ref: str | None = None,
) -> UUID:
    """Artifact mit EXPLIZITEM `created_at` — der Sweep rechnet genau darauf."""
    artifact_id: UUID = await conn.fetchval(
        "INSERT INTO wa_artifact "
        "(workspace_id, area_id, type, title, occurred_at, occurred_precision, "
        " content, content_ref, created_at) "
        "VALUES ($1, $2, 'doc', $3, $4, 'day', $5::jsonb, $6, $7) RETURNING id",
        workspace_id,
        area_id,
        title,
        _OCCURRED_AT,
        '{"blocks": []}',
        content_ref,
        created_at,
    )
    return artifact_id


async def _insert_chunk(
    conn: asyncpg.Connection, workspace_id: UUID, area_id: UUID, artifact_id: UUID
) -> None:
    await conn.execute(
        "INSERT INTO wa_chunk (workspace_id, artifact_id, area_id, block_id, ord, text, locale) "
        "VALUES ($1, $2, $3, 'b1', 0, 'Passage zur Aufbewahrung', 'de')",
        workspace_id,
        artifact_id,
        area_id,
    )


async def _insert_blob(
    conn: asyncpg.Connection, workspace_id: UUID, sha256: str, *, created_at: datetime
) -> None:
    await conn.execute(
        "INSERT INTO wa_blob "
        "(workspace_id, sha256, size_bytes, media_type, storage_key, created_at) "
        "VALUES ($1, $2, 12, 'application/pdf', $3, $4)",
        workspace_id,
        sha256,
        blob_key(workspace_id, sha256),
        created_at,
    )


# --- retention_days-Sweep ----------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_retention_sweep_deletes_expired_artifacts_and_chunks() -> None:
    """Abgelaufene Artifacts fallen samt Chunks; frische + fristlose bleiben."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        expiring = await _insert_area(conn, workspace_id, name="mit-frist", retention_days=7)
        forever = await _insert_area(conn, workspace_id, name="ohne-frist", retention_days=None)

        expired = await _insert_artifact(
            conn, workspace_id, expiring, title="alt", created_at=_NOW - timedelta(days=10)
        )
        await _insert_chunk(conn, workspace_id, expiring, expired)
        fresh = await _insert_artifact(
            conn, workspace_id, expiring, title="frisch", created_at=_NOW - timedelta(days=1)
        )
        # Ohne Frist ist auch ein uraltes Artifact unantastbar (Default null).
        ancient = await _insert_artifact(
            conn, workspace_id, forever, title="uralt", created_at=_NOW - timedelta(days=400)
        )

        deleted = await cleanup_expired_artifacts(conn, _NOW)

        # Der Sweep ist DB-weit (ein Cron-Lauf kennt keine Workspaces) — in der
        # geteilten Test-DB kann er fremde Altlasten mitnehmen. Bewiesen wird
        # deshalb der Effekt IM eigenen Workspace, nicht die globale Zahl.
        assert deleted >= 1
        surviving = {
            row["id"]
            for row in await conn.fetch(
                "SELECT id FROM wa_artifact WHERE workspace_id = $1", workspace_id
            )
        }
        assert surviving == {fresh, ancient}
        # CASCADE (0076): die Passage des geloeschten Artifacts ist mit weg.
        chunk_count = await conn.fetchval(
            "SELECT count(*) FROM wa_chunk WHERE artifact_id = $1", expired
        )
        assert chunk_count == 0

        # Idempotenz: der zweite Lauf findet nichts mehr.
        assert await cleanup_expired_artifacts(conn, _NOW) == 0

    _with_seed(_run)


# --- Orphan-Blobs ------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_orphan_blob_sweep_removes_row_and_object() -> None:
    """Verwaiste, alte `wa_blob`-Zeile faellt samt Objekt; Rest bleibt."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        area = await _insert_area(conn, workspace_id, name="blobs", retention_days=None)
        store = MemoryBlobStore()

        # (a) verwaist + alt → faellt.  (b) verwaist, aber frisch → bleibt
        # (Ingest laeuft vielleicht gerade).  (c) referenziert → bleibt.
        await _insert_blob(conn, workspace_id, _SHA_ORPHAN, created_at=_NOW - timedelta(days=2))
        await _insert_blob(conn, workspace_id, _SHA_FRESH, created_at=_NOW - timedelta(hours=1))
        await _insert_blob(conn, workspace_id, _SHA_LINKED, created_at=_NOW - timedelta(days=2))
        await _insert_artifact(
            conn,
            workspace_id,
            area,
            title="referenziert",
            created_at=_NOW - timedelta(days=2),
            content_ref=_SHA_LINKED,
        )
        for sha in (_SHA_ORPHAN, _SHA_FRESH, _SHA_LINKED):
            await store.put(blob_key(workspace_id, sha), b"payload", "application/pdf")

        rows, objects, skipped = await cleanup_orphan_blobs(conn, store, _NOW)

        # DB-weiter Sweep (s. o.): Zahlen sind untere Schranken, der Beweis
        # liegt im Zustand des eigenen Workspace und des eigenen Stores.
        assert (rows >= 1, skipped) == (True, False)
        remaining = {
            row["sha256"]
            for row in await conn.fetch(
                "SELECT sha256 FROM wa_blob WHERE workspace_id = $1", workspace_id
            )
        }
        assert remaining == {_SHA_FRESH, _SHA_LINKED}
        assert objects >= 1
        assert not await store.exists(blob_key(workspace_id, _SHA_ORPHAN))
        assert await store.exists(blob_key(workspace_id, _SHA_FRESH))
        assert await store.exists(blob_key(workspace_id, _SHA_LINKED))

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_orphan_object_sweep_needs_age_and_respects_it() -> None:
    """Objekt ohne Katalog-Zeile: alt → geloescht, frisch → unberuehrt.

    Der frische Fall ist der wichtige: zwischen Blob-PUT und COMMIT der
    Ingest-Transaktion existiert ein Objekt ohne Zeile voellig regulaer — es
    zu loeschen waere Datenverlust.
    """

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        store = MemoryBlobStore()
        # Eine Katalog-Zeile haelt den Workspace im Sweep-Scope.
        await _insert_blob(conn, workspace_id, _SHA_LINKED, created_at=_NOW - timedelta(days=2))
        await _insert_artifact(
            conn,
            workspace_id,
            await _insert_area(conn, workspace_id, name="objekte", retention_days=None),
            title="haelt-die-zeile",
            created_at=_NOW - timedelta(days=2),
            content_ref=_SHA_LINKED,
        )
        await store.put(blob_key(workspace_id, _SHA_LINKED), b"payload", "application/pdf")

        stale_key = blob_key(workspace_id, _SHA_OBJECT_ONLY)
        inflight_key = blob_key(workspace_id, _SHA_ORPHAN)
        await store.put(stale_key, b"muell", "application/pdf")
        await store.put(inflight_key, b"laeuft-gerade", "application/pdf")
        store.set_last_modified(stale_key, _NOW - timedelta(days=3))
        store.set_last_modified(inflight_key, _NOW - timedelta(minutes=2))

        _rows, objects, skipped = await cleanup_orphan_blobs(conn, store, _NOW)

        assert (objects >= 1, skipped) == (True, False)
        assert not await store.exists(stale_key)
        assert await store.exists(inflight_key)
        assert await store.exists(blob_key(workspace_id, _SHA_LINKED))

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_orphan_blob_sweep_without_store_reports_skip() -> None:
    """Ohne BlobStore (ADR-0048: Normalfall) faellt nur die Katalog-Zeile."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        await _insert_blob(conn, workspace_id, _SHA_ORPHAN, created_at=_NOW - timedelta(days=2))

        rows, objects, skipped = await cleanup_orphan_blobs(conn, None, _NOW)

        assert (rows >= 1, objects, skipped) == (True, 0, True)
        gone = await conn.fetchval(
            "SELECT count(*) FROM wa_blob WHERE workspace_id = $1", workspace_id
        )
        assert gone == 0

    _with_seed(_run)


# --- Tabellen-Store ----------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_area_store_sweep_removes_only_dangling_files(tmp_path: Path) -> None:
    """Datei ohne `work_area`-Zeile faellt; lebende Area + fremdes
    Verzeichnis bleiben unberuehrt."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        store = TableStore(base_dir=tmp_path)
        live_area = await _insert_area(conn, workspace_id, name="lebt", retention_days=None)
        dangling_area = uuid4()
        columns = [ColumnSpec(name="wert", type=ColumnType.TEXT)]
        await store.create_table(workspace_id, live_area, "lebendig", columns)
        await store.create_table(workspace_id, dangling_area, "verwaist", columns)

        # Verzeichnis eines Workspace, den es nicht gibt — defensiv tabu.
        foreign_workspace = uuid4()
        await store.create_table(foreign_workspace, uuid4(), "fremd", columns)
        foreign_files = sorted((tmp_path / str(foreign_workspace)).glob("*.sqlite"))
        # Und ein Verzeichnis, dessen Name gar keine UUID ist.
        (tmp_path / "nicht-eine-uuid").mkdir()

        removed, unknown_dirs = await cleanup_deleted_area_stores(conn, store)

        assert removed == 1
        assert unknown_dirs == 2
        assert store.db_path(workspace_id, live_area).is_file()
        assert not store.db_path(workspace_id, dangling_area).exists()
        assert all(path.is_file() for path in foreign_files)

        # Idempotenz: ein zweiter Lauf findet nichts mehr zu loeschen.
        assert (await cleanup_deleted_area_stores(conn, store))[0] == 0

    _with_seed(_run)


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_run_retention_sweeps_fills_all_counters(tmp_path: Path) -> None:
    """Die Cron-Verdrahtung haengt alle drei Sweeps an ein Purge-Ergebnis."""

    async def _run(conn: asyncpg.Connection, workspace_id: UUID, _agent_id: UUID) -> None:
        set_table_store(TableStore(base_dir=tmp_path))
        area = await _insert_area(conn, workspace_id, name="cron", retention_days=7)
        await _insert_artifact(
            conn, workspace_id, area, title="alt", created_at=_NOW - timedelta(days=10)
        )
        await _insert_blob(conn, workspace_id, _SHA_ORPHAN, created_at=_NOW - timedelta(days=2))

        before = PurgeResult(organizations=0, accounts=0)
        result = await run_retention_sweeps(conn, before, _NOW)

        # Die Account-/Org-Zaehler des Eingangs-Ergebnisses bleiben erhalten.
        assert (result.organizations, result.accounts) == (0, 0)
        assert result.expired_artifacts >= 1
        assert result.orphan_blob_rows >= 1
        # Ohne WHO2BE_BLOBSTORE_*-Env ist der Store None — der dokumentierte
        # Normalfall, kein Fehler.
        assert result.blobstore_skipped is True

    try:
        _with_seed(_run)
    finally:
        reset_table_store()


# --- GDPR-Export -------------------------------------------------------------


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_export_fixture(workspace_id: UUID, agent_id: UUID, base_dir: Path) -> None:
    """Legt Area + Artifact + Blob + Tabelle + KB + Zugriffslog an.

    Der TableStore hier ist eine EIGENE Instanz auf demselben Verzeichnis: die
    Write-Locks binden sich an die Loop des ersten Awaits, und der Export
    laeuft spaeter in der Loop des `TestClient`.
    """

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            area_id = await _insert_area(conn, workspace_id, name="export", retention_days=30)
            artifact_id = await _insert_artifact(
                conn,
                workspace_id,
                area_id,
                title="Export-Artifact",
                created_at=_NOW - timedelta(days=1),
            )
            await _insert_blob(conn, workspace_id, _SHA_LINKED, created_at=_NOW)
            table_id = await conn.fetchval(
                "INSERT INTO wa_table (workspace_id, area_id, name, schema_json) "
                "VALUES ($1, $2, 'umsaetze', $3::jsonb) RETURNING id",
                workspace_id,
                area_id,
                '{"columns": [{"name": "wert", "type": "text"}]}',
            )
            assert table_id is not None
            node_id = await conn.fetchval(
                "INSERT INTO kb_node "
                "(workspace_id, tier, content, source_ref, source_ref_kind, "
                " occurred_at, occurred_precision, created_by) "
                "VALUES ($1, 'hypothesis', 'Behauptung fuer den Export', "
                " 'url:https://example.com', 'url', $2, 'day', $3) RETURNING id",
                workspace_id,
                _OCCURRED_AT,
                uuid4(),
            )
            await conn.execute(
                "INSERT INTO kb_edge "
                "(workspace_id, type, from_anchor, to_anchor, from_node_id, created_by) "
                "VALUES ($1, 'supports', 'a', 'b', $2, $3)",
                workspace_id,
                node_id,
                uuid4(),
            )
            await conn.execute(
                "INSERT INTO agent_access_log "
                "(workspace_id, agent_id, ref_kind, ref_id, operation, "
                " sensitivity_at_access, access_date) "
                "VALUES ($1, $2, 'artifact', $3, 'read', 'general', $4)",
                workspace_id,
                agent_id,
                str(artifact_id),
                _NOW.date(),
            )

            store = TableStore(base_dir=base_dir)
            await store.create_table(
                workspace_id, area_id, "umsaetze", [ColumnSpec(name="wert", type=ColumnType.TEXT)]
            )
            await store.insert_rows(
                workspace_id,
                area_id,
                "umsaetze",
                ["wert"],
                [{"wert": "Zeile-A"}, {"wert": "Zeile-B"}],
                dedupe_hash_fn=lambda row: str(row["wert"]),
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _cleanup_export_fixture(workspace_id: UUID) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute("DELETE FROM agent_access_log WHERE workspace_id = $1", workspace_id)
            await conn.execute("DELETE FROM kb_edge WHERE workspace_id = $1", workspace_id)
            await conn.execute("DELETE FROM kb_node WHERE workspace_id = $1", workspace_id)
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db")
def test_gdpr_export_contains_workarea_kb_and_access_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Das Art.-20-Buendel traegt Areas, Artifacts, Blob-Metadaten,
    Tabellen-Zeilen, KB und Zugriffslog — Blob-Bytes bewusst nicht."""
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    workspace_id = setup_workspace(owner)
    seed_auth_user(owner, "retention-export@example.com", name=None)

    async def _agent() -> UUID:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id: UUID = await conn.fetchval(
                "INSERT INTO agent (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'export-agent') RETURNING id",
                workspace_id,
                owner,
            )
            return agent_id
        finally:
            await conn.close()

    agent_id = asyncio.run(_agent())
    _seed_export_fixture(workspace_id, agent_id, tmp_path)
    set_table_store(TableStore(base_dir=tmp_path))
    try:
        with TestClient(app) as client:
            export = client.get("/v1/gdpr/export", headers=_auth(owner))
            assert export.status_code == 200
            bundle = export.json()

        workspaces = [w for o in bundle["organizations"] for w in o["workspaces"]]
        target = next(w for w in workspaces if w["id"] == str(workspace_id))

        area = next(a for a in target["work_areas"] if a["name"] == "export")
        assert area["retention_days"] == 30
        assert [artifact["title"] for artifact in area["artifacts"]] == ["Export-Artifact"]
        # doc-Blockliste ist Nutzdatum und bleibt im Buendel.
        assert "blocks" in area["artifacts"][0]["content"]

        # Blob: Metadaten ja, Bytes nein.
        blob = next(b for b in target["wa_blobs"]["items"] if b["sha256"] == _SHA_LINKED)
        assert blob["storage_key"] == blob_key(workspace_id, _SHA_LINKED)
        assert blob["media_type"] == "application/pdf"
        assert "content" not in blob and "data" not in blob
        assert "storage_key" in target["wa_blobs"]["note"]

        # Tabellen-Katalog + Zeilen-Dump aus der SQLite-Datei.
        table = next(t for t in target["wa_tables"] if t["name"] == "umsaetze")
        assert table["rows"]["truncated"] is False
        values = {row[table["rows"]["columns"].index("wert")] for row in table["rows"]["rows"]}
        assert values == {"Zeile-A", "Zeile-B"}

        knowledge_base = target["knowledge_base"]
        assert [node["content"] for node in knowledge_base["nodes"]] == [
            "Behauptung fuer den Export"
        ]
        assert len(knowledge_base["edges"]) == 1
        # Generierte tsvector-Spalte ist Index-Material, kein Nutzdatum.
        assert "search" not in knowledge_base["nodes"][0]

        assert [entry["ref_kind"] for entry in target["agent_access_log"]] == ["artifact"]
    finally:
        reset_table_store()
        _cleanup_export_fixture(workspace_id)
        cleanup_workspaces([owner])
