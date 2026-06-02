from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookType,
    PlaybookUpdate,
    PlaybookUsage,
    PlaybookVersionRead,
    VersionStatus,
)


def _content() -> PlaybookContent:
    return PlaybookContent(
        description="Onboarding flow",
        body="1. Greet.",
        type="workflow",
        tags=["onboarding"],
    )


def test_content_allows_empty_type_for_draft() -> None:
    # Welle 4: type="" ist erlaubt fuer Draft-Create.
    # Promote-Validation prueft spaeter, ob type befuellt ist.
    content = PlaybookContent(description="d", body="b", type="")
    assert content.type == ""


def test_content_defaults_tags_and_triggers() -> None:
    content = PlaybookContent(description="d", body="b", type="workflow")
    assert content.tags == []
    assert content.triggers is None


def test_content_body_is_plain_string_field() -> None:
    # Track B (Nur-BlockNote): `body` ist immer ein (stringifizierter BlockNote-)
    # String; es gibt keinen `body_format`-Schalter mehr.
    content = PlaybookContent(description="d", body="[]", type="workflow")
    assert content.body == "[]"


def test_content_rejects_body_format_key() -> None:
    # `extra="forbid"`: ein verbliebener body_format-Key (Alt-Client) wird
    # abgelehnt — Migration 0030 entfernt ihn aus allen Snapshots.
    with pytest.raises(ValidationError):
        PlaybookContent.model_validate(
            {"description": "d", "body": "b", "type": "workflow", "body_format": "blocknote"}
        )


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


def test_read_defaults_status_fields_for_back_compat() -> None:
    playbook = PlaybookRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="PB",
        current_version=1,
        type="workflow",
        tags=[],
        triggers=None,
        content=_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert playbook.current_status is VersionStatus.inactive
    assert playbook.has_pending_draft is False


def test_version_read_defaults_status_to_inactive() -> None:
    version = PlaybookVersionRead(
        version=1,
        content=_content(),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert version.status is VersionStatus.inactive


def test_playbook_type_enum_covers_curated_set() -> None:
    assert {member.value for member in PlaybookType} == {
        "prompt",
        "instructions",
        "snippet",
        "workflow",
        "checklist",
        "faq",
    }


def test_playbook_type_is_str_compatible() -> None:
    # StrEnum-Werte muessen sich direkt mit PlaybookContent.type vergleichen
    # lassen — das nutzt die UI fuer "selected"-Vergleiche und der MCP-Filter.
    content = PlaybookContent(description="d", body="b", type=PlaybookType.workflow.value)
    assert content.type == "workflow"
    assert PlaybookType("workflow") is PlaybookType.workflow


def test_playbook_usage_round_trip() -> None:
    usage = PlaybookUsage(persona_id=uuid4(), persona_name="QA Persona")
    assert PlaybookUsage.model_validate(usage.model_dump()) == usage
