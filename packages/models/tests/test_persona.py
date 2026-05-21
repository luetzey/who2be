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
        owner_id=uuid4(),
        name="QA",
        current_version=2,
        content=_content(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    restored = PersonaRead.model_validate(persona.model_dump())
    assert restored == persona


def test_version_read_carries_creator_and_version() -> None:
    version = PersonaVersionRead(
        version=3,
        content=_content(),
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )
    assert version.version == 3
