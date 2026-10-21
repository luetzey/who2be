#!/usr/bin/env python
"""Legt den Blob-Bucket idempotent an (ADR-0048) — One-Shot, terminiert danach.

Laeuft gegen den Compose-Dienst `seaweedfs` (SeaweedFS, Apache-2.0), der MinIO
abgeloest hat (#525): MinIOs Community-Edition ist eingestellt und AGPL faellt
unter die Deny-Liste aus ADR-0033. Am Skript aendert das nichts Inhaltliches —
das Apache-2.0-SDK `minio` spricht S3, nicht MinIO-Protokoll, und SeaweedFS
unterstuetzt `CreateBucket`/`HeadBucket`. Es ist ohnehin Kern-Dependency der
API (ADR-0048), weshalb dieser One-Shot im bereits gebauten API-Image faehrt
und kein eigenes braucht.

Bewusst ein eigener One-Shot und NICHT der API-Start: „Den Bucket legt der
Compose-One-Shot (Dev) bzw. die Provisionierung (Prod) an — nie die App"
(ADR-0048). Diese Trennung bleibt; gewechselt hat nur der Server dahinter.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable

from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import MaxRetryError, NewConnectionError, ProtocolError

# S3-Codes fuer „Bucket gibt es schon". `bucket_exists` + `make_bucket` ist
# nicht atomar, deshalb reicht die Vorab-Pruefung allein nicht: bei parallelen
# Laeufen gewinnt einer, der andere sieht diesen Fehler.
_ALREADY_EXISTS = frozenset({"BucketAlreadyOwnedByYou", "BucketAlreadyExists"})

# „S3 hoert (noch) nicht zu" — und NUR das. Ein `S3Error` (403, falsche Keys)
# ist eine Antwort des Servers und faellt bewusst NICHT hierunter: der darf
# sofort scheitern. `MaxRetryError` wirft das SDK nach seinen eigenen ~6 s
# Verbindungs-Retries, die nackten Typen kommen bei abgeschalteten Retries.
_NOT_LISTENING = (MaxRetryError, NewConnectionError, ProtocolError, ConnectionError)

# Gesamtbudget fuer den ersten Kontakt. Nach dem Wechsel auf SeaweedFS 4.48
# war der Master-Port gesund, waehrend S3 (8333) noch `Connection refused`
# lieferte — der erste Deploy brach ab, der zweite lief durch. Der
# Healthcheck prueft S3 inzwischen mit; das hier ist die zweite Leine.
_WAIT_SECONDS = 60.0
_MAX_BACKOFF = 8.0


def _first_contact(
    client: Minio,
    bucket: str,
    *,
    budget: float = _WAIT_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """`bucket_exists` mit Backoff, solange S3 noch nicht zuhoert.

    Wiederholt NUR bei Verbindungsfehlern (1, 2, 4, 8, 8 … s), bis `budget`
    verbraucht ist; dann geht der letzte Fehler an den Aufrufer.
    """
    deadline = clock() + budget
    delay = 1.0
    attempt = 1
    while True:
        try:
            return bool(client.bucket_exists(bucket))
        except _NOT_LISTENING as exc:
            remaining = deadline - clock()
            if remaining <= 0:
                raise
            wait = min(delay, remaining)
            print(
                f"blobstore-bootstrap: S3 noch nicht erreichbar (Versuch {attempt}, "
                f"{type(exc).__name__}) — neuer Versuch in {wait:.0f} s.",
                file=sys.stderr,
            )
            sleep(wait)
            delay = min(delay * 2, _MAX_BACKOFF)
            attempt += 1


def main() -> int:
    # Endpoint ist host:port OHNE Schema — `secure` entscheidet http/https,
    # gleiche Konvention wie `MinioBlobStore`. SeaweedFS' S3-Gateway hoert im
    # All-in-One-Modus auf 8333 (MinIO frueher: 9000).
    endpoint = os.environ.get("BLOBSTORE_ENDPOINT", "seaweedfs:8333")
    bucket = os.environ.get("BLOBSTORE_BUCKET", "who2be-blobs")
    # Muessen zur gemounteten Identitaet in scripts/seaweedfs-s3.json passen —
    # ohne gueltige Credentials weist SeaweedFS den Aufruf mit 403 ab.
    access_key = os.environ.get("BLOBSTORE_ACCESS_KEY", "who2be-dev")
    secret_key = os.environ.get("BLOBSTORE_SECRET_KEY", "who2be-dev-secret")
    secure = os.environ.get("BLOBSTORE_SECURE", "false").lower() == "true"

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    try:
        exists = _first_contact(client, bucket)
    except _NOT_LISTENING as exc:
        # Klarer Abbruch statt Traceback: Exit 1 haelt `api` an
        # (`service_completed_successfully`), die Ursache steht im Log.
        print(
            f"blobstore-bootstrap: S3 unter '{endpoint}' nach {_WAIT_SECONDS:.0f} s "
            f"nicht erreichbar — Abbruch. Letzter Fehler: {type(exc).__name__}. "
            "Pruefen: `logs seaweedfs`.",
            file=sys.stderr,
        )
        return 1

    if exists:
        print(f"blobstore-bootstrap: Bucket '{bucket}' existiert bereits — nichts zu tun.")
        return 0

    try:
        client.make_bucket(bucket)
    except S3Error as exc:
        if exc.code in _ALREADY_EXISTS:
            print(f"blobstore-bootstrap: Bucket '{bucket}' parallel angelegt — in Ordnung.")
            return 0
        raise

    print(f"blobstore-bootstrap: Bucket '{bucket}' angelegt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
