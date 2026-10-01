"""Export und Import einer Organisation (`core/org_transfer.py`, ADR-0055 §4.6/R6).

Belegt die Akzeptanzkriterien der Karte t_18cb3e8b:

* **Round-Trip:** Org exportieren, in eine leere Datenbank (frisch migriertes
  Schema) importieren, erneut exportieren — Zeilen-, Blob- und
  SQLite-Pruefsummen sind identisch.
* **Isolation:** Import in eine Instanz, in der eine fremde Org lebt. Deren
  Zeilen bleiben unveraendert (Fingerabdruck), und der REST-Isolationslauf aus
  `test_tenant_isolation_api.py` findet zwischen importierter und fremder Org
  in beide Richtungen keinen Befund.
* **Fail-closed:** Kollision, Migrationsstand, Pruefsumme, fremde Zeile,
  fremde Referenz und fehlende Org-Tabelle brechen ab, ohne im Ziel etwas zu
  hinterlassen.
* **CLI:** Export nur verschluesselt (gpg), Import von Datei oder stdin.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient
from test_tenant_isolation_api import run_isolation  # type: ignore[import-not-found]

from who2be_api.blobstore import blob_key, build_blob_store, set_blob_store
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core import org_transfer
from who2be_api.core.config import get_settings
from who2be_api.core.org_transfer import (
    CREDENTIAL_TABLES,
    EXPORT_ONLY_TABLES,
    MANIFEST_NAME,
    OrgTransferError,
    export_org,
    import_org,
    read_archive,
)
from who2be_api.main import app
from who2be_api.services.tablestore_provider import get_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.testing.tenant_pair import (
    Tenant,
    fingerprint,
    ghost_of,
    isolation_stores,
    seed_tenant,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces

pytestmark = pytest.mark.integration

_BLOB_CONTENT = b"Org-Transfer Blob: Kontoauszug 2026-08."


def _db(fn: Callable[[asyncpg.Connection], Any]) -> Any:
    """Fuehrt `fn` auf einer Owner-Verbindung zur aktuellen `database_url` aus."""

    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await fn(conn)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _export(org_id: UUID) -> tuple[bytes, dict[str, Any]]:
    sink = io.BytesIO()

    async def _run(conn: asyncpg.Connection) -> dict[str, Any]:
        result = await export_org(
            conn, org_id, sink, blob_store=build_blob_store(), table_store=get_table_store()
        )
        return result.manifest

    manifest = _db(_run)
    return sink.getvalue(), manifest


def _import(data: bytes) -> org_transfer.ImportResult:
    async def _run(conn: asyncpg.Connection) -> org_transfer.ImportResult:
        return await import_org(
            conn, data, blob_store=build_blob_store(), table_store=get_table_store()
        )

    result: org_transfer.ImportResult = _db(_run)
    return result


def _seed_with_blob(client: TestClient, label: str, secret: str) -> Tenant:
    """Mandant aus `seed_tenant` plus ein ingestierter Blob (ADR-0048)."""
    t = seed_tenant(client, label, secret)
    response = client.post(
        f"{t.prefix}/work-areas/{t.ids['area_id']}/ingest",
        json={"file_b64": base64.b64encode(_BLOB_CONTENT).decode(), "filename": "auszug.txt"},
        headers=t.human,
    )
    assert response.status_code == 201, response.text
    return t


def _rebuild(data: bytes, edit: Callable[[dict[str, Any], dict[str, bytes]], None]) -> bytes:
    """Archiv entpacken, `edit` anwenden, Pruefsummen im Manifest nachziehen, neu packen.

    So entsteht ein manipuliertes, aber in sich stimmiges Archiv — die Probe
    trifft die inhaltlichen Pruefungen, nicht die Pruefsummen.
    """
    members: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        for info in tar:
            extracted = tar.extractfile(info)
            assert extracted is not None
            members[info.name] = extracted.read()
    manifest = json.loads(members.pop(MANIFEST_NAME))
    edit(manifest, members)
    for name, entry in manifest["tables"].items():
        entry["sha256"] = hashlib.sha256(members[f"postgres/{name}.jsonl"]).hexdigest()
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:", format=tarfile.PAX_FORMAT) as tar:
        for name, content in [*members.items(), (MANIFEST_NAME, json.dumps(manifest).encode())]:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return out.getvalue()


def _edit_rows(
    members: dict[str, bytes], table: str, change: Callable[[dict[str, Any]], None]
) -> None:
    lines = members[f"postgres/{table}.jsonl"].decode().splitlines()
    rows = [json.loads(line) for line in lines]
    change(rows[0])
    members[f"postgres/{table}.jsonl"] = "".join(json.dumps(r) + "\n" for r in rows).encode()


def _comparable(manifest: dict[str, Any]) -> dict[str, Any]:
    """Was ein Round-Trip unveraendert lassen muss: Zeilen, SQLite-Inhalt, Blobs."""
    return {
        "tables": {
            name: (entry["rows"], entry["sha256"])
            for name, entry in manifest["tables"].items()
            if entry["mode"] == "import"
        },
        "tablestores": {k: v["content_sha256"] for k, v in manifest["tablestores"].items()},
        "blobs": {k: v["sha256"] for k, v in manifest["blobs"].items()},
    }


@pytest.fixture
def stores(tmp_path: Path) -> Iterator[Path]:
    with isolation_stores(tmp_path / "source"):
        yield tmp_path


@pytest.fixture
def source(stores: Path, patched_jwt_secret: str) -> Iterator[tuple[Tenant, bytes, dict[str, Any]]]:
    """Mandant A im geteilten Schema, exportiert. Raeumt A am Ende ab."""
    users: list[UUID] = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            a = _seed_with_blob(client, "A", patched_jwt_secret)
            users.append(a.user_id)
        data, manifest = _export(a.org_id)
        yield a, data, manifest
    finally:
        cleanup_workspaces(users)


def _switch_stores(base: Path) -> MemoryBlobStore:
    """Ziel-Instanz: eigener Tabellen-Store-Ordner, eigener BlobStore."""
    target = MemoryBlobStore()
    set_blob_store(target)
    set_table_store(TableStore(base_dir=base))
    return target


@pytest.mark.usefixtures("migrated_db")
def test_round_trip_into_empty_database_is_identical(
    source: tuple[Tenant, bytes, dict[str, Any]], stores: Path
) -> None:
    a, data, manifest = source
    # Der Bestand ist nicht trivial: jede Speicherart ist belegt.
    assert manifest["tables"]["persona"]["rows"] >= 1
    assert manifest["tables"]["wa_blob"]["rows"] == 1
    assert len(manifest["tablestores"]) == 1
    assert len(manifest["blobs"]) == 1
    assert manifest["missing_blobs"] == []
    # W3: keine Zugangsdaten im Archiv — weder als Datei noch im Manifest.
    assert not CREDENTIAL_TABLES & set(manifest["tables"])
    names = tarfile.open(fileobj=io.BytesIO(data), mode="r:").getnames()
    assert not [n for n in names if n.split("/")[-1].removesuffix(".jsonl") in CREDENTIAL_TABLES]
    assert names[-1] == MANIFEST_NAME

    blobs = _switch_stores(stores / "empty")
    with isolated_schema("orgxfer_rt"):
        result = _import(data)
        assert result.row_count == sum(
            e["rows"] for e in manifest["tables"].values() if e["mode"] == "import"
        )
        assert result.tablestores == 1
        assert result.blobs == 1
        _, again = _export(a.org_id)
        # W1: Entitlement-Tabellen kommen im Ziel nicht an.
        for table in EXPORT_ONLY_TABLES:
            assert again["tables"][table]["rows"] == 0

    assert _comparable(again) == _comparable(manifest)
    key = blob_key(a.workspace_id, hashlib.sha256(_BLOB_CONTENT).hexdigest())
    assert asyncio.run(blobs.get(key)) == _BLOB_CONTENT


@pytest.mark.usefixtures("migrated_db")
def test_import_next_to_foreign_org_keeps_tenants_apart(
    source: tuple[Tenant, bytes, dict[str, Any]], stores: Path, patched_jwt_secret: str
) -> None:
    a, data, _ = source
    _switch_stores(stores / "target")
    with isolated_schema("orgxfer_iso"):
        users: list[UUID] = []
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                b = seed_tenant(client, "B", patched_jwt_secret)
                users.append(b.user_id)
                before = fingerprint(b)
                _import(data)
                users.append(a.user_id)
                assert fingerprint(b) == before

                _reissue_credentials(client, a)
                # Die importierte Org ist benutzbar ...
                response = client.get(f"{a.prefix}/personas/{a.ids['persona_id']}", headers=a.human)
                assert response.status_code == 200, response.text
                # ... und die fremde Org erreicht sie nicht: B ruft jede Route mit
                # A-IDs auf, die Gegenprobe laeuft als A mit den importierten IDs.
                # Eine Richtung genuegt und geht nicht anders — die loeschenden
                # Gegenproben verbrauchen den Bestand der Gegenseite.
                report = run_isolation(client, b, a, ghost_of(a))
                assert not report.findings, "\n".join(report.findings)
                assert report.counts.get("V1", 0) >= 170, report.counts
                assert report.counts.get("V3", 0) >= 20, report.counts
                assert report.counts.get("control", 0) >= 175, report.counts
        finally:
            cleanup_workspaces(users)


def _reissue_credentials(client: TestClient, t: Tenant) -> None:
    """Was nach einem Import neu ausgestellt wird (W3): Tokens und Einladungen."""
    p, h = t.prefix, t.human
    token = client.post(
        f"{p}/tokens", json={"name": "neu", "agent_id": t.ids["agent_id"]}, headers=h
    )
    assert token.status_code == 201, token.text
    t.agent = {"Authorization": f"Bearer {token.json()['token']}"}
    spare = client.post(
        f"{p}/tokens", json={"name": "rot", "agent_id": t.ids["agent_id"]}, headers=h
    )
    t.ids["token_id"] = spare.json()["id"]
    invitation = client.post(
        f"{p}/invitations",
        json={"email": f"neu-{t.marker.lower()}@example.com", "role": "viewer"},
        headers=h,
    )
    assert invitation.status_code == 201, invitation.text
    t.ids["invitation_id"] = invitation.json()["id"]
    email = f"{t.marker.lower()}@example.com"
    own = client.post(f"{p}/invitations", json={"email": email, "role": "viewer"}, headers=h)
    assert own.status_code == 201, own.text
    t.ids["invite_token"] = own.json()["token"]


@pytest.mark.usefixtures("migrated_db")
def test_collision_aborts_without_leaving_anything(
    source: tuple[Tenant, bytes, dict[str, Any]], stores: Path
) -> None:
    a, data, _ = source
    before = fingerprint(a)
    blobs = _switch_stores(stores / "collide")
    with pytest.raises(OrgTransferError, match="existiert im Ziel bereits"):
        _import(data)
    assert fingerprint(a) == before
    assert not (stores / "collide").exists() or not any((stores / "collide").rglob("*"))
    assert asyncio.run(blobs.list_keys("blobs/")) == []


class _FailingBlobStore(MemoryBlobStore):
    async def put(self, key: str, data: bytes, media_type: str) -> None:
        raise OSError("Objekt-Storage nicht erreichbar")


@pytest.mark.usefixtures("migrated_db")
def test_failure_after_rows_rolls_back_rows_and_files(
    source: tuple[Tenant, bytes, dict[str, Any]], stores: Path
) -> None:
    a, data, _ = source
    set_blob_store(_FailingBlobStore())
    set_table_store(TableStore(base_dir=stores / "rollback"))
    with isolated_schema("orgxfer_rb"):
        with pytest.raises(OSError, match="nicht erreichbar"):
            _import(data)
        count = _db(
            lambda c: c.fetchval("SELECT count(*) FROM organization WHERE id = $1", a.org_id)
        )
        assert count == 0
    assert not any(p.is_file() for p in (stores / "rollback").rglob("*"))


@pytest.mark.usefixtures("migrated_db")
@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("foreign_row", "gehoert nicht zur Org"),
        ("foreign_reference", "ausserhalb des Archivs"),
        ("migrations", "Migrationsstand"),
        ("checksum", "Pruefsumme"),
        ("credentials", "Zugangsdaten"),
    ],
)
def test_tampered_archive_is_rejected(
    source: tuple[Tenant, bytes, dict[str, Any]],
    stores: Path,
    patched_jwt_secret: str,
    case: str,
    message: str,
) -> None:
    a, data, _ = source
    with TestClient(app, raise_server_exceptions=False) as client:
        b = seed_tenant(client, "B", patched_jwt_secret)
    try:
        before = fingerprint(b)

        def edit(manifest: dict[str, Any], members: dict[str, bytes]) -> None:
            if case == "foreign_row":
                # Eine Persona im Archiv, die im Workspace von B landen wuerde.
                _edit_rows(members, "persona", lambda r: r.update(workspace_id=str(b.workspace_id)))
            elif case == "foreign_reference":
                # Eigene Zeile, aber angehaengt an ein Playbook von B.
                _edit_rows(
                    members,
                    "persona_playbook",
                    lambda r: r.update(playbook_id=b.ids["playbook_id"]),
                )
            elif case == "migrations":
                manifest["migrations"].append("9999_future.sql")
            elif case == "credentials":
                manifest["tables"]["api_token"] = {"mode": "import", "rows": 0, "columns": []}
                members["postgres/api_token.jsonl"] = b""

        if case == "foreign_reference":
            _ensure_persona_playbook(a)
            data, _ = _export(a.org_id)
        if case == "checksum":
            tampered = data.replace(a.marker.encode(), b"X" * len(a.marker), 1)
        else:
            tampered = _rebuild(data, edit)
        _switch_stores(stores / f"t-{case}")
        with isolated_schema("orgxfer_bad"), pytest.raises(OrgTransferError, match=message):
            _import(tampered)
        assert fingerprint(b) == before
    finally:
        cleanup_workspaces([b.user_id])


@pytest.mark.usefixtures("migrated_db")
def test_archive_without_parent_table_cannot_attach_to_foreign_object(
    source: tuple[Tenant, bytes, dict[str, Any]], stores: Path, patched_jwt_secret: str
) -> None:
    """Archiv nur mit organization, workspace und wa_table; die Tabelle haengt an B.

    Ohne `work_area` im Archiv galt der Verweis frueher als "nicht pruefbar",
    und der Fremdschluessel der DB war erfuellt — B lebt ja im Ziel. Der Import
    muss abbrechen, und an der WorkArea von B darf nichts haengen.
    """
    a, data, _ = source
    _switch_stores(stores / "t-missing-parent")
    with isolated_schema("orgxfer_gap"):
        users: list[UUID] = []
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                b = seed_tenant(client, "B", patched_jwt_secret)
            users.append(b.user_id)
            before = fingerprint(b)
            keep = {"organization", "workspace", "wa_table"}

            def edit(manifest: dict[str, Any], members: dict[str, bytes]) -> None:
                for name in set(manifest["tables"]) - keep:
                    del manifest["tables"][name]
                    del members[f"postgres/{name}.jsonl"]
                manifest["tablestores"] = {}
                manifest["blobs"] = {}
                for member in [m for m in members if not m.startswith("postgres/")]:
                    del members[member]
                lines = members["postgres/wa_table.jsonl"].decode().splitlines()[:1]
                members["postgres/wa_table.jsonl"] = (lines[0] + "\n").encode()
                manifest["tables"]["wa_table"]["rows"] = 1
                _edit_rows(members, "wa_table", lambda r: r.update(area_id=b.ids["area_id"]))

            tampered = _rebuild(data, edit)
            try:
                with pytest.raises(OrgTransferError, match="Archiv unvollstaendig"):
                    _import(tampered)
            finally:
                users.append(a.user_id)
            assert fingerprint(b) == before
            attached = _db(
                lambda c: c.fetchval(
                    "SELECT count(*) FROM wa_table WHERE area_id = $1 AND workspace_id <> $2",
                    UUID(b.ids["area_id"]),
                    b.workspace_id,
                )
            )
            assert attached == 0
        finally:
            cleanup_workspaces(users)


def _ensure_persona_playbook(a: Tenant) -> None:
    """Verknuepft Persona und Playbook von A, damit `persona_playbook` eine Zeile hat."""
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.put(
            f"{a.prefix}/personas/{a.ids['persona_id']}/playbooks",
            json={"playbook_ids": [a.ids["playbook_id"]]},
            headers=a.human,
        )
        assert response.status_code < 300, response.text


# --- CLI ---------------------------------------------------------------------


@pytest.fixture
def gpg_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Wegwerf-Schluesselbund mit einem Empfaenger ohne Passphrase."""
    if shutil.which("gpg") is None:
        pytest.fail("gpg fehlt — der Export setzt es voraus (Runtime-Image installiert gnupg).")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(home))
    subprocess.run(
        ["gpg", "--batch", "--passphrase", "", "--quick-gen-key", "Org Transfer <ot@example.com>"]
        + ["future-default", "default", "never"],
        check=True,
        capture_output=True,
    )
    return "ot@example.com"


@pytest.mark.usefixtures("migrated_db")
def test_cli_exports_only_encrypted_and_imports_from_stdin(
    source: tuple[Tenant, bytes, dict[str, Any]],
    stores: Path,
    gpg_home: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    a, _, manifest = source
    out = stores / "org.tar.gpg"
    code = org_transfer.main(
        ["export", "--org-id", str(a.org_id), "--recipient", gpg_home, "--output", str(out)]
    )
    assert code == 0, capsys.readouterr().err
    assert out.stat().st_mode & 0o777 == 0o600
    raw = out.read_bytes()
    assert a.marker.encode() not in raw  # kein Klartext auf der Platte
    plain = subprocess.run(["gpg", "--batch", "--decrypt"], input=raw, capture_output=True)
    assert plain.returncode == 0, plain.stderr
    assert _comparable(read_archive(plain.stdout).manifest) == _comparable(manifest)

    # Ein zweiter Export ueberschreibt nicht; ein unbekannter Empfaenger
    # hinterlaesst keine Datei.
    assert (
        org_transfer.main(
            ["export", "--org-id", str(a.org_id), "--recipient", gpg_home, "--output", str(out)]
        )
        == 1
    )
    missing = stores / "nobody.gpg"
    assert (
        org_transfer.main(
            [
                "export",
                "--org-id",
                str(a.org_id),
                "--recipient",
                "x@invalid",
                "--output",
                str(missing),
            ]
        )
        == 1
    )
    assert not missing.exists()
    with pytest.raises(SystemExit):
        org_transfer.main(["export", "--org-id", str(a.org_id), "--output", str(missing)])

    # Import ueber stdin: A existiert noch -> Kollision, Code 1, Meldung.
    monkeypatch.setattr("sys.stdin", _Stdin(plain.stdout))
    _switch_stores(stores / "cli")
    assert org_transfer.main(["import"]) == 1
    assert "existiert im Ziel bereits" in capsys.readouterr().err
    # Verschluesselt importiert: verstaendliche Meldung statt Traceback.
    enc = stores / "enc.gpg"
    enc.write_bytes(raw)
    assert org_transfer.main(["import", "--input", str(enc)]) == 1
    assert "gpg --decrypt" in capsys.readouterr().err

    with isolated_schema("orgxfer_cli"):
        monkeypatch.setattr("sys.stdin", _Stdin(plain.stdout))
        assert org_transfer.main(["import"]) == 0
    assert "Zugangsdaten neu ausstellen" in capsys.readouterr().err


class _Stdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def test_new_table_without_tenant_column_is_rejected() -> None:
    """Fail-closed: eine Tabelle ohne Mandantenspalte und ohne Klasse stoppt den Export."""
    with pytest.raises(OrgTransferError, match="weder workspace_id noch org_id"):
        org_transfer._classify("new_global_thing", ["id", "name"])
    assert org_transfer._classify("oauth_client", ["client_id"]) == "skip"
    assert org_transfer._classify("api_token", ["id", "workspace_id"]) == "skip"
    assert org_transfer._classify("mcp_usage", ["org_id"]) == "export_only"
    assert org_transfer._classify("persona", ["id", "workspace_id"]) == "import"


def test_unreadable_archive_is_rejected() -> None:
    with pytest.raises(OrgTransferError, match="Kein lesbares Archiv"):
        read_archive(b"-----BEGIN PGP MESSAGE-----")


def test_reference_to_missing_parent_table_is_rejected() -> None:
    """Fehlt die Elterntabelle, gilt sie als leer — der Verweis zeigt nach aussen."""

    def table(name: str, mode: str = "import") -> org_transfer.TableInfo:
        return org_transfer.TableInfo(name, ("id", "workspace_id"), (), False, mode)

    schema = org_transfer.Schema(
        tables={
            "work_area": table("work_area"),
            "wa_table": table("wa_table"),
            "oauth_client": table("oauth_client", "skip"),
        },
        foreign_keys=(
            org_transfer.ForeignKey("wa_table", "work_area", ("area_id",), ("id",)),
            org_transfer.ForeignKey("wa_table", "oauth_client", ("client_id",), ("id",)),
        ),
    )
    child = {"id": "t1", "area_id": "fremd", "client_id": "c1"}
    with pytest.raises(OrgTransferError, match="ausserhalb des Archivs"):
        org_transfer._check_references(schema, {"wa_table": [child]})
    # Verweise auf nicht importierte Tabellen prueft der Fremdschluessel der DB.
    org_transfer._check_references(schema, {"wa_table": [child], "work_area": [{"id": "fremd"}]})
