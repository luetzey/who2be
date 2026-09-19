#!/usr/bin/env python
"""Legt den Blob-Bucket idempotent an (ADR-0048) — One-Shot, terminiert danach.

Ersetzt den frueheren `minio/mc`-Container. Das Image dazu ist von Docker Hub
verschwunden (`object not found`), und es zog ein komplettes CLI-Image nur
fuer einen einzigen Aufruf in die Lieferkette. Das Apache-2.0-SDK `minio` ist
ohnehin Kern-Dependency der API (ADR-0048, Lizenz-Grenze: der AGPL-SERVER
laeuft als Container, im Code liegt nur das SDK) — dieses Skript laeuft
deshalb im bereits gebauten API-Image und braucht gar kein eigenes.

Bewusst ein eigener One-Shot und NICHT der API-Start: „Den Bucket legt der
Compose-One-Shot `minio-bootstrap` (Dev) bzw. die Provisionierung (Prod) an —
nie die App" (ADR-0048). Diese Trennung bleibt; nur das Image hat gewechselt.
"""

from __future__ import annotations

import os
import sys

from minio import Minio
from minio.error import S3Error

# S3-Codes fuer „Bucket gibt es schon". `bucket_exists` + `make_bucket` ist
# nicht atomar, deshalb reicht die Vorab-Pruefung allein nicht: bei parallelen
# Laeufen gewinnt einer, der andere sieht diesen Fehler. Genau das meinte das
# fruehere `mc mb --ignore-existing`.
_ALREADY_EXISTS = frozenset({"BucketAlreadyOwnedByYou", "BucketAlreadyExists"})


def main() -> int:
    # Endpoint ist host:port OHNE Schema — `secure` entscheidet http/https,
    # gleiche Konvention wie `MinioBlobStore`.
    endpoint = os.environ.get("BLOBSTORE_ENDPOINT", "minio:9000")
    bucket = os.environ.get("BLOBSTORE_BUCKET", "who2be-blobs")
    access_key = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    secure = os.environ.get("BLOBSTORE_SECURE", "false").lower() == "true"

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    if client.bucket_exists(bucket):
        print(f"minio-bootstrap: Bucket '{bucket}' existiert bereits — nichts zu tun.")
        return 0

    try:
        client.make_bucket(bucket)
    except S3Error as exc:
        if exc.code in _ALREADY_EXISTS:
            print(f"minio-bootstrap: Bucket '{bucket}' parallel angelegt — in Ordnung.")
            return 0
        raise

    print(f"minio-bootstrap: Bucket '{bucket}' angelegt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
