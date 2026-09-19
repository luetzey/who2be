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

from minio import Minio
from minio.error import S3Error

# S3-Codes fuer „Bucket gibt es schon". `bucket_exists` + `make_bucket` ist
# nicht atomar, deshalb reicht die Vorab-Pruefung allein nicht: bei parallelen
# Laeufen gewinnt einer, der andere sieht diesen Fehler.
_ALREADY_EXISTS = frozenset({"BucketAlreadyOwnedByYou", "BucketAlreadyExists"})


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

    if client.bucket_exists(bucket):
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
