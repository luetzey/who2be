"""Unit-Tests fuer den Hard-Purge-Job (`core/purge.py`).

Ohne DB: ein Fake-Purge-Repo zaehlt die Aufrufe, `delete_auth_user` ist
monkeypatcht. Belegt: faellige Orgs werden geloescht; ein Account wird nur
finalisiert (`purged_at`), wenn die GoTrue-Identitaet erfolgreich entfernt ist —
sonst bleibt er pending fuer den naechsten Lauf (DSGVO-Erasure-Retry).

Dazu die **Karenzfrist des Area-Store-Sweeps** (`AREA_STORE_GRACE`, ADR-0049):
ebenfalls DB-los ueber eine Fake-Connection, die Zeit wird per `os.utime`
gestellt statt erschlafen.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from who2be_api.core import purge as purge_module
from who2be_api.core.purge import (
    AREA_STORE_GRACE,
    cleanup_deleted_area_stores,
    purge_expired,
)
from who2be_api.tablestore import TableStore

_NOW = datetime(2026, 9, 26, 3, 30, tzinfo=UTC)


class FakePurgeRepo:
    def __init__(
        self,
        org_ids: list[UUID],
        user_ids: list[UUID],
        anonymize_count: int = 0,
        cleanup_count: int = 0,
        oauth_cleanup_count: int = 0,
    ) -> None:
        self._org_ids = org_ids
        self._user_ids = user_ids
        self._anonymize_count = anonymize_count
        self._cleanup_count = cleanup_count
        self._oauth_cleanup_count = oauth_cleanup_count
        self.purged_orgs: list[UUID] = []
        self.purged_data: list[UUID] = []
        self.marked: list[UUID] = []
        self.cleanup_calls = 0
        self.oauth_cleanup_calls = 0

    async def expired_organizations(self, _now: datetime) -> list[UUID]:
        return self._org_ids

    async def purge_organization(self, org_id: UUID) -> None:
        self.purged_orgs.append(org_id)

    async def expired_accounts(self, _now: datetime) -> list[UUID]:
        return self._user_ids

    async def purge_account_data(self, user_id: UUID) -> int:
        self.purged_data.append(user_id)
        return self._anonymize_count

    async def cleanup_expired_invitations(self, _now: datetime) -> int:
        self.cleanup_calls += 1
        return self._cleanup_count

    async def cleanup_expired_oauth(self, _now: datetime) -> int:
        self.oauth_cleanup_calls += 1
        return self._oauth_cleanup_count

    async def mark_account_purged(self, user_id: UUID) -> None:
        self.marked.append(user_id)


def test_purge_deletes_orgs_and_finalizes_accounts_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(purge_module, "delete_auth_user", _const(True))
    org, user = uuid4(), uuid4()
    repo = FakePurgeRepo([org], [user], anonymize_count=2, cleanup_count=3, oauth_cleanup_count=4)

    result = asyncio.run(purge_expired(repo, now=datetime.now(UTC)))

    assert repo.purged_orgs == [org]
    assert repo.purged_data == [user]
    assert repo.marked == [user]
    assert repo.cleanup_calls == 1
    assert repo.oauth_cleanup_calls == 1
    assert result.organizations == 1
    assert result.accounts == 1
    assert result.anonymized_audit_rows == 2
    assert result.cleaned_invitations == 3
    assert result.cleaned_oauth_rows == 4


def test_account_not_finalized_when_gotrue_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(purge_module, "delete_auth_user", _const(False))
    user = uuid4()
    repo = FakePurgeRepo([], [user])

    result = asyncio.run(purge_expired(repo, now=datetime.now(UTC)))

    # Daten weg, aber NICHT finalisiert ⇒ naechster Lauf versucht erneut.
    assert repo.purged_data == [user]
    assert repo.marked == []
    assert result.accounts == 0


def _const(value: bool):  # type: ignore[no-untyped-def]
    async def _fn(_user_id: UUID) -> bool:
        return value

    return _fn


# --- Karenzfrist im Area-Store-Sweep (ADR-0049) -------------------------------


class FakeStoreConn:
    """Minimale asyncpg-Attrappe fuer `cleanup_deleted_area_stores`.

    Der Sweep stellt genau zwei Fragen: „existiert dieser Workspace?" und
    „welche Areas hat er?". Beides hier hart verdrahtet — damit laufen diese
    Tests ohne Postgres, wie die uebrigen in dieser Datei.
    """

    def __init__(self, workspace_id: UUID, known_areas: set[UUID] | None = None) -> None:
        self._workspace_id = workspace_id
        self._known_areas = known_areas or set()

    async def fetchval(self, _sql: str, workspace_id: UUID) -> int | None:
        return 1 if workspace_id == self._workspace_id else None

    async def fetch(self, _sql: str, _workspace_id: UUID) -> list[dict[str, UUID]]:
        return [{"id": area_id} for area_id in self._known_areas]


def _age_files(path: Path, age: timedelta, *, suffixes: tuple[str, ...]) -> None:
    """Setzt `mtime` der genannten Seitendateien auf `_NOW - age`."""
    stamp = (_NOW - age).timestamp()
    for suffix in suffixes:
        target = Path(f"{path}{suffix}")
        if target.exists():
            os.utime(target, (stamp, stamp))


def _prepare_dangling_store(tmp_path: Path) -> tuple[TableStore, FakeStoreConn, UUID, Path]:
    """Eine Area-Datei mit WAL/SHM, deren `work_area`-Zeile fehlt."""
    store = TableStore(base_dir=tmp_path)
    workspace_id, area_id = uuid4(), uuid4()
    path = store.db_path(workspace_id, area_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{path}{suffix}").write_bytes(b"")
    return store, FakeStoreConn(workspace_id), workspace_id, path


def test_area_store_sweep_removes_file_beyond_grace(tmp_path: Path) -> None:
    """Regression: ohne frische Schreibspur faellt die Datei wie bisher."""
    store, conn, _workspace_id, path = _prepare_dangling_store(tmp_path)
    _age_files(path, AREA_STORE_GRACE + timedelta(hours=1), suffixes=("", "-wal", "-shm"))

    removed, unknown_dirs = asyncio.run(cleanup_deleted_area_stores(conn, store, _NOW))

    assert (removed, unknown_dirs) == (1, 0)
    assert not path.exists()


def test_area_store_sweep_keeps_file_within_grace(tmp_path: Path) -> None:
    """Frische Schreibspur ⇒ die Datei bleibt liegen, ohne Zaehler-Alarm."""
    store, conn, _workspace_id, path = _prepare_dangling_store(tmp_path)
    _age_files(path, timedelta(minutes=5), suffixes=("", "-wal", "-shm"))

    removed, unknown_dirs = asyncio.run(cleanup_deleted_area_stores(conn, store, _NOW))

    # `unknown_store_dirs` heisst „manuell pruefen" — eine Datei in Karenz ist
    # kein Rueckstand und darf diesen Zaehler nicht bewegen.
    assert (removed, unknown_dirs) == (0, 0)
    assert path.is_file()


def test_area_store_sweep_honours_wal_mtime_alone(tmp_path: Path) -> None:
    """Die eigentliche Ursache: nur das `-wal` ist frisch, die `.sqlite` alt.

    Genau dieser Fall entsteht beim Schreiben im WAL-Modus. Verkuerzte man das
    Frische-Mass auf die Haupt-Datei, greift die Karenzfrist hier NICHT und der
    Test wird rot — waehrend die beiden anderen gruen bleiben.
    """
    store, conn, _workspace_id, path = _prepare_dangling_store(tmp_path)
    _age_files(path, AREA_STORE_GRACE + timedelta(hours=1), suffixes=("", "-shm"))
    _age_files(path, timedelta(minutes=5), suffixes=("-wal",))

    removed, unknown_dirs = asyncio.run(cleanup_deleted_area_stores(conn, store, _NOW))

    assert (removed, unknown_dirs) == (0, 0)
    assert path.is_file()
