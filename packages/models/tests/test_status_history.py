from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import StatusHistoryEntry, VersionStatus


def _entry(**overrides: object) -> StatusHistoryEntry:
    payload: dict[str, object] = {
        "id": uuid4(),
        "entity_type": "persona",
        "entity_id": uuid4(),
        "from_status": VersionStatus.draft,
        "to_status": VersionStatus.review,
        "changed_by": uuid4(),
        "changed_at": datetime.now(UTC),
        "note": None,
    }
    payload.update(overrides)
    return StatusHistoryEntry.model_validate(payload)


def test_round_trip_preserves_fields() -> None:
    entry = _entry(note="LGTM")
    restored = StatusHistoryEntry.model_validate(entry.model_dump())
    assert restored == entry


def test_from_status_may_be_none_for_initial_draft() -> None:
    entry = _entry(from_status=None, to_status=VersionStatus.draft)
    assert entry.from_status is None


def test_rejects_unknown_entity_type() -> None:
    with pytest.raises(ValidationError):
        _entry(entity_type="workspace")


def test_rejects_unknown_status_value() -> None:
    with pytest.raises(ValidationError):
        _entry(to_status="archived")


def test_rejects_oversized_note() -> None:
    with pytest.raises(ValidationError):
        _entry(note="x" * 2_001)


def test_resource_is_accepted_as_entity_type() -> None:
    # 0012_status_history.sql laesst 'resource' schon zu (Vorgriff 2.2).
    entry = _entry(entity_type="resource")
    assert entry.entity_type == "resource"
