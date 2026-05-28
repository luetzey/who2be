from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)


def _content() -> PlaybookContent:
    return PlaybookContent(
        description="Onboarding flow",
        body="1. Greet.",
        type="workflow",
        tags=["onboarding"],
    )


def test_content_requires_non_empty_type() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="b", type="")


def test_content_defaults_tags_and_triggers() -> None:
    content = PlaybookContent(description="d", body="b", type="workflow")
    assert content.tags == []
    assert content.triggers is None


def test_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PlaybookCreate(name="PB", content=_content(), tags=["x"])  # type: ignore[call-arg]


def test_update_name_is_optional() -> None:
    assert PlaybookUpdate(content=_content()).name is None


def test_read_round_trip_preserves_denormalised_fields() -> None:
    playbook = PlaybookRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="PB",
        current_version=1,
        type="workflow",
        tags=["onboarding"],
        triggers="new user",
        content=_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    restored = PlaybookRead.model_validate(playbook.model_dump())
    assert restored == playbook


def test_content_rejects_oversized_body() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="x" * 50_001, type="workflow")


def test_content_rejects_oversized_description_or_triggers() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(description="x" * 2_001, body="b", type="workflow")
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="b", type="workflow", triggers="x" * 2_001)


def test_content_rejects_too_many_or_too_long_tags() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="b", type="workflow", tags=["t"] * 51)
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="b", type="workflow", tags=["x" * 101])


def test_content_rejects_oversized_type() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(description="d", body="b", type="x" * 101)


def test_version_read_carries_version() -> None:
    version = PlaybookVersionRead(
        version=5,
        content=_content(),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert version.version == 5
