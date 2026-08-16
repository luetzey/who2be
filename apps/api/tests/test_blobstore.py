"""BlobStore (ADR-0048, WP3) — Port-Contract, Key-Konvention, Store-Auswahl.

DB- und netzlos: der Memory-Adapter ist die Referenz-Implementierung des
Port-Contracts (put/get/exists/delete/list_keys). Fuer den MinIO-Adapter wird
ausschliesslich Konstruktion + Konfig-Mapping geprueft — dass dabei KEIN
Netzwerk noetig ist, ist selbst Teil des Contracts (kein Netzwerk-Call im
Konstruktor, siehe adapters/minio.py).
"""

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest

from who2be_api.blobstore import (
    BlobNotFoundError,
    blob_key,
    build_blob_store,
    reset_blob_store,
    set_blob_store,
    workspace_prefix,
)
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.blobstore.adapters.minio import MinioBlobStore
from who2be_api.core.config import Settings

_WS_A = UUID("00000000-0000-0000-0000-00000000000a")
_WS_B = UUID("00000000-0000-0000-0000-00000000000b")
_SHA_1 = "1" * 64
_SHA_2 = "2" * 64

_BLOBSTORE_ENV = (
    "WHO2BE_BLOBSTORE_ENDPOINT",
    "WHO2BE_BLOBSTORE_ACCESS_KEY",
    "WHO2BE_BLOBSTORE_SECRET_KEY",
    "WHO2BE_BLOBSTORE_BUCKET",
    "WHO2BE_BLOBSTORE_SECURE",
)


@pytest.fixture(autouse=True)
def _isolated_blob_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ambiente WHO2BE_BLOBSTORE_*-Env raushalten + Prozess-Cache zuruecksetzen."""
    for name in _BLOBSTORE_ENV:
        monkeypatch.delenv(name, raising=False)
    reset_blob_store()
    yield
    reset_blob_store()


def _settings(**overrides: Any) -> Settings:
    """Settings ohne .env-Datei — Env-Vars (monkeypatch) plus direkte Overrides."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


# --- Memory-Adapter: Referenz-Implementierung des Port-Contracts -------------


def test_memory_put_get_roundtrip() -> None:
    store = MemoryBlobStore()
    key = blob_key(_WS_A, _SHA_1)
    asyncio.run(store.put(key, b"inhalt", "application/pdf"))
    assert asyncio.run(store.get(key)) == b"inhalt"
    assert store.media_type(key) == "application/pdf"


def test_memory_get_missing_raises_blob_not_found() -> None:
    store = MemoryBlobStore()
    key = blob_key(_WS_A, _SHA_1)
    with pytest.raises(BlobNotFoundError) as excinfo:
        asyncio.run(store.get(key))
    assert excinfo.value.key == key


def test_memory_exists() -> None:
    store = MemoryBlobStore()
    key = blob_key(_WS_A, _SHA_1)
    assert asyncio.run(store.exists(key)) is False
    asyncio.run(store.put(key, b"x", "text/plain"))
    assert asyncio.run(store.exists(key)) is True


def test_memory_put_overwrites_idempotent() -> None:
    # Content-addressed: ein Doppel-PUT auf denselben Key ist harmlos.
    store = MemoryBlobStore()
    key = blob_key(_WS_A, _SHA_1)
    asyncio.run(store.put(key, b"gleicher inhalt", "text/plain"))
    asyncio.run(store.put(key, b"gleicher inhalt", "text/plain"))
    assert asyncio.run(store.get(key)) == b"gleicher inhalt"
    assert asyncio.run(store.list_keys(workspace_prefix(_WS_A))) == [key]


def test_memory_delete_removes_and_is_idempotent() -> None:
    store = MemoryBlobStore()
    key = blob_key(_WS_A, _SHA_1)
    asyncio.run(store.put(key, b"x", "text/plain"))
    asyncio.run(store.delete(key))
    assert asyncio.run(store.exists(key)) is False
    # S3-Semantik: DELETE auf fehlende Keys ist ein No-op, kein Fehler.
    asyncio.run(store.delete(key))


def test_memory_list_keys_filters_by_workspace_prefix() -> None:
    # Das Workspace-Praefix ist die Tenancy-Grenze im Storage (GDPR-Purge/-Export):
    # ein Listing unter blobs/{ws}/ darf NIE Keys eines anderen Workspace liefern.
    store = MemoryBlobStore()
    key_a1 = blob_key(_WS_A, _SHA_1)
    key_a2 = blob_key(_WS_A, _SHA_2)
    key_b = blob_key(_WS_B, _SHA_1)
    asyncio.run(store.put(key_a2, b"2", "text/plain"))
    asyncio.run(store.put(key_a1, b"1", "text/plain"))
    asyncio.run(store.put(key_b, b"b", "text/plain"))
    # Lexikographisch aufsteigend, nur der eigene Workspace.
    assert asyncio.run(store.list_keys(workspace_prefix(_WS_A))) == [key_a1, key_a2]
    assert asyncio.run(store.list_keys(workspace_prefix(_WS_B))) == [key_b]
    assert asyncio.run(store.list_keys("blobs/")) == sorted([key_a1, key_a2, key_b])


# --- Key-Konvention (ADR-0048) ----------------------------------------------


def test_blob_key_format() -> None:
    assert blob_key(_WS_A, _SHA_1) == f"blobs/{_WS_A}/{_SHA_1}"


def test_blob_key_normalizes_to_lowercase() -> None:
    # EINE kanonische Schreibweise pro Inhalt, sonst greift der Dedup nicht.
    mixed = "AbCdEf0123456789" * 4
    assert blob_key(_WS_A, mixed) == f"blobs/{_WS_A}/{mixed.lower()}"
    assert blob_key(_WS_A, f"  {_SHA_1}  ") == blob_key(_WS_A, _SHA_1)


@pytest.mark.parametrize(
    "bad",
    ["", "abc", "g" * 64, "1" * 63, "1" * 65, "sha256:" + "1" * 64],
)
def test_blob_key_rejects_non_sha256(bad: str) -> None:
    with pytest.raises(ValueError):
        blob_key(_WS_A, bad)


def test_workspace_prefix_matches_blob_key() -> None:
    assert blob_key(_WS_A, _SHA_1).startswith(workspace_prefix(_WS_A))
    assert not blob_key(_WS_B, _SHA_1).startswith(workspace_prefix(_WS_A))


# --- build_blob_store: Auswahl + Konfig-Mapping (kein Netzwerkzugriff) -------


def test_build_without_config_returns_none() -> None:
    # Der 503-Pfad beginnt hier: `None` ist der Normalfall, kein Fehler —
    # die 503-Antwort selbst entscheidet der Aufrufer (Ingest/Blob-Read).
    assert build_blob_store(_settings()) is None


def test_build_with_partial_config_returns_none() -> None:
    settings = _settings(
        blobstore_endpoint="localhost:9000",
        blobstore_access_key="minioadmin",
        # secret fehlt → Kern-Config unvollstaendig.
    )
    assert build_blob_store(settings) is None


def test_build_with_config_returns_minio_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ueber echte Env-Vars, damit auch das pydantic-Parsing (inkl. secure-Bool)
    # mitgeprueft ist — nicht nur die Feld-Zuweisung.
    monkeypatch.setenv("WHO2BE_BLOBSTORE_ENDPOINT", "minio.example:9000")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_ACCESS_KEY", "ak")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_SECRET_KEY", "sk")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_SECURE", "true")
    store = build_blob_store(_settings())
    assert isinstance(store, MinioBlobStore)
    assert store.endpoint == "minio.example:9000"
    # Bucket-Default passt zum Compose-Bootstrap (`who2be-blobs`).
    assert store.bucket == "who2be-blobs"
    assert store.secure is True


def test_build_secure_flag_parses_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_BLOBSTORE_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_ACCESS_KEY", "ak")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_SECRET_KEY", "sk")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_BUCKET", "eigener-bucket")
    monkeypatch.setenv("WHO2BE_BLOBSTORE_SECURE", "false")
    store = build_blob_store(_settings())
    assert isinstance(store, MinioBlobStore)
    assert store.bucket == "eigener-bucket"
    assert store.secure is False


def test_build_caches_store_per_process() -> None:
    settings = _settings(
        blobstore_endpoint="localhost:9000",
        blobstore_access_key="ak",
        blobstore_secret_key="sk",
    )
    first = build_blob_store(settings)
    assert first is not None
    # Zweiter Aufruf: Cache, KEIN Neubau — auch ohne Settings-Argument.
    assert build_blob_store() is first
    reset_blob_store()
    rebuilt = build_blob_store(settings)
    assert rebuilt is not None
    assert rebuilt is not first


def test_set_blob_store_overrides_resolution() -> None:
    memory = MemoryBlobStore()
    set_blob_store(memory)
    assert build_blob_store(_settings()) is memory
    set_blob_store(None)
    assert build_blob_store(_settings()) is None
