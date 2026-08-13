"""MinIO-/S3-Adapter (ADR-0048) — spricht das S3-API ueber das minio-SDK.

Das SDK ist synchron (urllib3); jede Operation laeuft deshalb via
`asyncio.to_thread`, damit Netz-I/O den Event-Loop nicht anhaelt — Ingest ist
ein Laufzeit-Call eines Agenten, ein blockierter Loop waere unmittelbar
spuerbar.

Der Konstruktor macht bewusst KEINEN Netzwerk-Call: `Minio(...)` baut nur den
Client. Den Bucket legt der Compose-One-Shot `minio-bootstrap` (Dev) bzw. die
Provisionierung (Prod) an — nie die App. So bleibt `build_blob_store` beim
Start billig, und ein nicht erreichbarer Store faellt erst am tatsaechlichen
Zugriff auf, wo die Aufrufer den Fehler behandeln.

Lizenz-Grenze (ADR-0048): der MinIO-SERVER ist AGPL und laeuft ausschliesslich
als Container (wie Postgres); das hier importierte SDK `minio` ist Apache-2.0
und darf Kern-Dependency sein.
"""

from __future__ import annotations

import asyncio
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from who2be_api.blobstore.port import BlobNotFoundError

# S3-Fehlercode fuer „Objekt existiert nicht" — die einzige S3Error-Variante,
# die zum Port-Contract gehoert (`exists` → False, `get` → BlobNotFoundError).
# Alles andere (NoSuchBucket, AccessDenied, …) ist ein Betriebsfehler und
# propagiert unveraendert.
_NOT_FOUND_CODE = "NoSuchKey"


class MinioBlobStore:
    """Adapter auf einen MinIO-/S3-kompatiblen Endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
    ) -> None:
        # `endpoint` ist host:port OHNE Schema — `secure` entscheidet
        # http/https. Kein Netzwerk-Call: Minio() konstruiert nur den Client.
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._endpoint = endpoint
        self._bucket = bucket
        self._secure = secure

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def secure(self) -> bool:
        return self._secure

    def _put_sync(self, key: str, data: bytes, media_type: str) -> None:
        self._client.put_object(
            self._bucket,
            key,
            BytesIO(data),
            length=len(data),
            content_type=media_type,
        )

    async def put(self, key: str, data: bytes, media_type: str) -> None:
        await asyncio.to_thread(self._put_sync, key, data, media_type)

    def _get_sync(self, key: str) -> bytes:
        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == _NOT_FOUND_CODE:
                raise BlobNotFoundError(key) from exc
            raise
        try:
            data: bytes = response.read()
        finally:
            # urllib3-Konvention des SDK: Response schliessen UND die
            # Connection in den Pool zurueckgeben, sonst leakt der Pool.
            response.close()
            response.release_conn()
        return data

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, key)

    def _exists_sync(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
        except S3Error as exc:
            if exc.code == _NOT_FOUND_CODE:
                return False
            raise
        return True

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._exists_sync, key)

    async def delete(self, key: str) -> None:
        # S3-Semantik: DELETE auf einen fehlenden Key ist bereits ein No-op —
        # genau der Port-Contract, kein Zusatz-Check noetig.
        await asyncio.to_thread(self._client.remove_object, self._bucket, key)

    def _list_sync(self, prefix: str) -> list[str]:
        objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        return sorted(str(obj.object_name) for obj in objects)

    async def list_keys(self, prefix: str) -> list[str]:
        return await asyncio.to_thread(self._list_sync, prefix)
