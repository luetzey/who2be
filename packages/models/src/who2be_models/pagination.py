"""Helpers fuer Keyset-Pagination.

Cursor codiert `(created_at, id)` als base64url-String. Wir tragen den
Cursor im `X-Next-Cursor`-Response-Header statt in einem Wrapper-Model,
damit bestehende Clients (Web-UI Hook `useListData`) ohne Aenderung
weiter `list[T]` parsen koennen. Limit ist auf `MAX_LIMIT` (200) hart
begrenzt, der Default folgt dem Wert aus `docs/security-findings.md`
F-09.
"""

import base64
import binascii
from datetime import datetime
from uuid import UUID

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "decode_cursor",
    "encode_cursor",
]


DEFAULT_LIMIT = 100
MAX_LIMIT = 200


def encode_cursor(created_at: datetime, item_id: UUID) -> str:
    """Codiert `(created_at, id)` als base64url ohne Padding."""
    raw = f"{created_at.isoformat()}|{item_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(raw: str) -> tuple[datetime, UUID] | None:
    """Decodes einen Cursor; gibt `None` bei jeder Form von Fehl-Eingabe.

    Bewusst tolerant: der Router uebersetzt `None` in ein 422, sodass jede
    malformed Eingabe denselben Fehlerpfad nimmt — keine internen
    Exception-Leaks ueber Stacktrace o. Aenl.
    """
    padding = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode((raw + padding).encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    iso, sep, uuid_str = decoded.partition("|")
    if not sep:
        return None
    try:
        return datetime.fromisoformat(iso), UUID(uuid_str)
    except ValueError:
        return None
