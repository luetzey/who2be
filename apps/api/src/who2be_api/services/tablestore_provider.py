"""App-weiter TableStore-Provider (ADR-0049, WP13) — analog `blobstore/service.py`.

`get_table_store` ist der einzige Ort, an dem der `TableStore` gebaut wird:
EINMAL pro Prozess, gecacht im Modul. Das ist kein Performance-Detail, sondern
Korrektheit — die per-Area-`asyncio.Lock`s der Instanz binden sich an die
Event-Loop des ersten Awaits (WP12); ein Store pro Request wuerde die
Write-Serialisierung pro Area-Datei aushebeln. Im API-Prozess gehoert die
Instanz damit der einen Uvicorn-Loop.

Anders als der BlobStore (ADR-0048, `None` = unkonfiguriert) ist der
TableStore IMMER verfuegbar: er braucht nur ein lokales Verzeichnis
(`settings.tablestore_dir`, Default fuer Dev; Compose mountet
`WHO2BE_TABLESTORE_DIR`) — es gibt keinen 503-Degradationspfad.

`set_table_store`/`reset_table_store` existieren fuer Tests (Blobstore-Muster
`set_blob_store`/`reset_blob_store`): jede Testfunktion setzt eine frische
Instanz auf ein `tmp_path`, damit die Locks in der Loop des jeweiligen
`TestClient`-Blocks leben und keine Zustaende zwischen Tests wandern.
"""

from __future__ import annotations

from pathlib import Path

from who2be_api.core.config import Settings, get_settings
from who2be_api.tablestore import TableStore

_cached_store: TableStore | None = None


def get_table_store(settings: Settings | None = None) -> TableStore:
    """Liefert den prozessweiten TableStore (lazy gebaut, dann gecacht)."""
    global _cached_store
    if _cached_store is None:
        resolved = settings or get_settings()
        _cached_store = TableStore(base_dir=Path(resolved.tablestore_dir))
    return _cached_store


def set_table_store(store: TableStore) -> None:
    """Setzt den Store direkt — fuer Tests (frische Instanz je Test-Loop)."""
    global _cached_store
    _cached_store = store


def reset_table_store() -> None:
    """Verwirft den Prozess-Cache (Tests, Konfig-Wechsel)."""
    global _cached_store
    _cached_store = None
