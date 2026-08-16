"""Store-Auswahl fuer den BlobStore (ADR-0048), analog `embeddings/service.py`.

`build_blob_store` ist der einzige Ort, an dem entschieden wird, OB und WOMIT
Objekte gespeichert werden. Alle Aufrufer sehen nur `BlobStorePort | None`.

`None` ist der NORMALFALL einer Installation ohne Objekt-Storage und KEIN
Fehler: dann liefern ausschliesslich Ingest und Blob-Reads 503
`blobstore_unconfigured` — diese Entscheidung faellt beim Aufrufer, hier wird
nichts geworfen. Fail-soft ist Absicht: WorkArea-Docs, Tabellen, KB und Suche
haengen nicht am Storage und sollen ohne ihn unveraendert laufen.

Der Store wird prozessweit einmal gebaut und gecacht: der Minio-Client haelt
einen urllib3-Connection-Pool, den pro Request neu aufzubauen unsinnig waere.
"""

from __future__ import annotations

import logging

from who2be_api.blobstore.port import BlobStorePort
from who2be_api.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_cached_store: BlobStorePort | None = None
_resolved = False


def build_blob_store(settings: Settings | None = None) -> BlobStorePort | None:
    """Liefert den BlobStore — oder `None`, wenn keiner konfiguriert ist.

    `None` ist der Normalfall einer Installation ohne
    `WHO2BE_BLOBSTORE_*`-Konfiguration und KEIN Fehlerzustand.
    """
    global _cached_store, _resolved
    if _resolved:
        return _cached_store

    resolved_settings = settings or get_settings()
    _resolved = True
    configured = (
        resolved_settings.blobstore_endpoint
        and resolved_settings.blobstore_access_key
        and resolved_settings.blobstore_secret_key
        and resolved_settings.blobstore_bucket
    )
    if not configured:
        logger.info(
            "BlobStore nicht konfiguriert (WHO2BE_BLOBSTORE_*) — Ingest/Blob-Reads "
            "liefern 503, alles andere laeuft unveraendert."
        )
        _cached_store = None
        return None

    try:
        from who2be_api.blobstore.adapters.minio import MinioBlobStore

        _cached_store = MinioBlobStore(
            endpoint=resolved_settings.blobstore_endpoint,
            access_key=resolved_settings.blobstore_access_key,
            secret_key=resolved_settings.blobstore_secret_key,
            bucket=resolved_settings.blobstore_bucket,
            secure=resolved_settings.blobstore_secure,
        )
    except Exception as exc:  # noqa: BLE001 - fail-soft ist hier Absicht (siehe Modul-Docstring)
        # Z.B. ein Endpoint MIT Schema (`http://…`), den Minio() ablehnt.
        # Degradation statt Startabbruch. BEWUSST ohne Traceback (Security-
        # Review 2026-08-13 L4): der Konstruktor-Frame truege die Credentials
        # in argument-repr-Naehe — nur Fehlerklasse + Endpoint ins Log.
        logger.warning(
            "BlobStore-Adapter nicht konstruierbar (%s; WHO2BE_BLOBSTORE_ENDPOINT=%r "
            "pruefen: host:port OHNE Schema) — Ingest/Blob-Reads liefern 503, "
            "alles andere laeuft.",
            exc.__class__.__name__,
            resolved_settings.blobstore_endpoint,
        )
        _cached_store = None
        return None

    return _cached_store


def reset_blob_store() -> None:
    """Verwirft den Prozess-Cache (Tests, Konfig-Wechsel)."""
    global _cached_store, _resolved
    _cached_store = None
    _resolved = False


def set_blob_store(store: BlobStorePort | None) -> None:
    """Setzt den Store direkt — fuer Tests und Aufrufer, die ihn selbst bauen."""
    global _cached_store, _resolved
    _cached_store = store
    _resolved = True
