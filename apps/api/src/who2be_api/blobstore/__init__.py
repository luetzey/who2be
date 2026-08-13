"""Content-addressed Blob-Storage hinter einem Port (ADR-0048).

Der Kern importiert NIE einen konkreten Adapter — nur `build_blob_store`.
"""

from who2be_api.blobstore.port import (
    BlobNotFoundError,
    BlobStorePort,
    blob_key,
    workspace_prefix,
)
from who2be_api.blobstore.service import build_blob_store, reset_blob_store, set_blob_store

__all__ = [
    "BlobNotFoundError",
    "BlobStorePort",
    "blob_key",
    "build_blob_store",
    "reset_blob_store",
    "set_blob_store",
    "workspace_prefix",
]
