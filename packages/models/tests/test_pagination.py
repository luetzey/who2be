from datetime import UTC, datetime
from uuid import UUID, uuid4

from who2be_models import DEFAULT_LIMIT, MAX_LIMIT, decode_cursor, encode_cursor


def test_constants() -> None:
    assert DEFAULT_LIMIT == 100
    assert MAX_LIMIT == 200


def test_cursor_round_trip_preserves_timestamp_and_id() -> None:
    created_at = datetime(2026, 5, 26, 12, 34, 56, 123456, tzinfo=UTC)
    item_id = uuid4()
    decoded = decode_cursor(encode_cursor(created_at, item_id))
    assert decoded is not None
    assert decoded == (created_at, item_id)


def test_cursor_decode_returns_none_for_invalid_base64() -> None:
    assert decode_cursor("not-base64!@#$") is None


def test_cursor_decode_returns_none_for_missing_separator() -> None:
    # base64url("nopipehere") ohne `|`-Separator.
    raw = "bm9waXBlaGVyZQ"
    assert decode_cursor(raw) is None


def test_cursor_decode_returns_none_for_malformed_uuid() -> None:
    # base64url("2026-05-26T00:00:00+00:00|not-a-uuid")
    raw = encode_cursor(datetime(2026, 5, 26, tzinfo=UTC), uuid4())
    # Tausche den UUID-Teil aus -- bewusst kaputt gegen `_` damit base64 ok bleibt.
    broken = raw[: len(raw) // 2] + "_" * (len(raw) - len(raw) // 2)
    assert decode_cursor(broken) is None


def test_cursor_decode_handles_padding_variants() -> None:
    # Selbst codieren mit beibehaltenem `=` muss weiterhin decodieren.
    import base64

    raw = f"{datetime(2026, 1, 1, tzinfo=UTC).isoformat()}|{UUID(int=0)}".encode()
    padded = base64.urlsafe_b64encode(raw).decode("ascii")
    assert padded.endswith("=") or len(padded) % 4 == 0
    decoded = decode_cursor(padded)
    assert decoded is not None
    assert decoded[1] == UUID(int=0)
