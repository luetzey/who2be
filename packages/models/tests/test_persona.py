from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    PersonaContent,
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
    VersionStatus,
)


def _content() -> PersonaContent:
    return PersonaContent(description="Tester", system_prompt="Be helpful.")


def test_content_defaults_traits_to_empty_list() -> None:
    assert _content().traits == []


def test_create_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        PersonaCreate(name="", content=_content())


def test_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PersonaCreate(name="QA", content=_content(), owner_id=uuid4())  # type: ignore[call-arg]


def test_update_name_is_optional() -> None:
    update = PersonaUpdate(content=_content())
    assert update.name is None


def test_read_round_trip_preserves_nested_content() -> None:
    persona = PersonaRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="QA",
        current_version=2,
        content=_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    restored = PersonaRead.model_validate(persona.model_dump())
    assert restored == persona


def test_content_rejects_oversized_strings() -> None:
    with pytest.raises(ValidationError):
        PersonaContent(description="x" * 2_001, system_prompt="s")
    with pytest.raises(ValidationError):
        PersonaContent(description="d", system_prompt="x" * 20_001)


def test_content_rejects_too_many_traits() -> None:
    with pytest.raises(ValidationError):
        PersonaContent(description="d", system_prompt="s", traits=["t"] * 51)


def test_content_rejects_oversized_trait_entry() -> None:
    with pytest.raises(ValidationError):
        PersonaContent(description="d", system_prompt="s", traits=["x" * 201])


def test_version_read_carries_creator_and_version() -> None:
    version = PersonaVersionRead(
        version=3,
        content=_content(),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert version.version == 3


def test_read_defaults_status_fields_for_back_compat() -> None:
    persona = PersonaRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="QA",
        current_version=1,
        content=_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert persona.current_status is VersionStatus.inactive
    assert persona.has_pending_draft is False


def test_version_read_defaults_status_to_inactive() -> None:
    version = PersonaVersionRead(
        version=1,
        content=_content(),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert version.status is VersionStatus.inactive
