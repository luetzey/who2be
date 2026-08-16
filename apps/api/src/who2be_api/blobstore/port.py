"""`BlobStorePort` — die Grenze zwischen Kern und Objekt-Storage (ADR-0048).

Hexagonal (Ports & Adapters), analog `embeddings/port.py`: der Kern kennt nur
`put`/`get`/`exists`/`delete`/`list_keys` auf Objekt-Keys. Ob dahinter MinIO,
ein anderer S3-kompatibler Dienst oder der In-Memory-Store der Tests steht,
ist Adapter-Sache und fuer die Ingest-/Blob-Pfade unsichtbar. Der Port
existiert fuer Testbarkeit und Austauschbarkeit — NICHT fuer Optionalitaet
des SDKs (`minio` ist Kern-Dependency, Apache-2.0).

Key-Konvention (ADR-0048): `blobs/{workspace_id}/{sha256}` — content-addressed
ueber den SHA-256 des Inhalts. Das Workspace-Praefix ist die Tenancy-Grenze im
Storage: GDPR-Purge und -Export sind damit ein Praefix-Listing, kein
Tabellen-Join. Bewusst KEIN Cross-Workspace-Dedup — gleicher Inhalt in zwei
Workspaces liegt zweimal im Store (Tenancy schlaegt Speicherersparnis).

`None` als Store ist der NORMALFALL, kein Fehler (siehe `service.py`): ohne
Konfiguration liefern nur Ingest und Blob-Reads 503 `blobstore_unconfigured`,
alles andere laeuft unveraendert.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

# 64 Hex-Zeichen = ein SHA-256-Hexdigest. `blob_key` normalisiert auf
# Kleinbuchstaben: content-addressed heisst EINE kanonische Schreibweise pro
# Inhalt — sonst wuerde derselbe Blob unter zwei Keys landen und der
# Dedup-Lookup (`wa_blob`) ins Leere greifen.
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def blob_key(workspace_id: UUID | str, sha256: str) -> str:
    """Kanonischer Objekt-Key `blobs/{workspace_id}/{sha256}` (ADR-0048).

    Wirft `ValueError`, wenn `sha256` kein SHA-256-Hexdigest ist — ein
    Programmierfehler des Aufrufers, keine Laufzeit-Degradation.
    """
    normalized = sha256.strip().lower()
    if not _SHA256_HEX.fullmatch(normalized):
        raise ValueError(f"Kein SHA-256-Hexdigest: {sha256!r}")
    return f"{workspace_prefix(workspace_id)}{normalized}"


def workspace_prefix(workspace_id: UUID | str) -> str:
    """Listing-Praefix aller Blobs eines Workspace (GDPR-Purge/-Export)."""
    return f"blobs/{workspace_id}/"


class BlobNotFoundError(LookupError):
    """`get` auf einen Key, den der Store nicht kennt.

    Domain-Exception statt SDK-Fehler (S3Error/KeyError), damit Aufrufer sie
    einheitlich behandeln koennen — Fehler-Mapping gehoert in die Router-Ebene
    (Interims-Leitplanke: keine HTTPException unterhalb davon).
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"Blob nicht im Store: {key}")
        self.key = key


class BlobStorePort(Protocol):
    """Content-addressed Objekt-Storage — Herkunft ist Adapter-Sache.

    Contract (Referenz-Implementierung: `adapters/memory.py`):
    idempotentes `put`/`delete`, `BlobNotFoundError` bei `get` auf fehlende
    Keys, Praefix-Listing lexikographisch aufsteigend.
    """

    async def put(self, key: str, data: bytes, media_type: str) -> None:
        """Legt `data` unter `key` ab.

        Ueberschreiben ist erlaubt und harmlos: Keys sind content-addressed,
        ein Doppel-PUT schreibt denselben Inhalt (Ingest-Schritt 6).
        """
        ...

    async def get(self, key: str) -> bytes:
        """Inhalt zu `key`; fehlt er, `BlobNotFoundError`."""
        ...

    async def exists(self, key: str) -> bool:
        """True, wenn `key` im Store liegt."""
        ...

    async def delete(self, key: str) -> None:
        """Entfernt `key`; fehlt er, ist das ein No-op (S3-Semantik)."""
        ...

    async def list_keys(self, prefix: str) -> list[str]:
        """Alle Keys unter `prefix`, lexikographisch aufsteigend."""
        ...


@runtime_checkable
class BlobAgeSource(Protocol):
    """OPTIONALE Zusatzfaehigkeit: Alter eines Objekts (Purge, ADR-0048).

    Bewusst NICHT Teil von `BlobStorePort` — Lesen und Schreiben von Blobs
    braucht kein Alter, nur der Orphan-Sweep in `core/purge.py` braucht es.
    Der Sweep muss zwei ununterscheidbare Zustaende trennen: ein Objekt ohne
    `wa_blob`-Zeile ist ENTWEDER Muell aus einer gescheiterten Ingest-
    Transaktion ODER ein Blob, dessen Ingest gerade laeuft — der PUT liegt
    VOR der Transaktion (`services/wa_ingest.py`, Pipeline-Schritt 6). Ohne
    Alter waere die Loeschung des zweiten Falls ein Datenverlust, deshalb
    loescht der Sweep Objekte NUR ueber einen Store, der diese Faehigkeit
    mitbringt; sonst meldet er sie bloss (`core/purge.py`).

    `runtime_checkable`, weil der Sweep zur Laufzeit entscheidet — ein
    Adapter ohne Zeitquelle ist zulaessig, nur eben nicht sweep-faehig.
    """

    async def last_modified(self, key: str) -> datetime | None:
        """Zeitpunkt des letzten Schreibens (aware, UTC); `None` = unbekannt.

        `None` steht auch fuer „Key existiert nicht" — der Aufrufer behandelt
        beide Faelle gleich: kein Alter, keine Loeschung.
        """
        ...
