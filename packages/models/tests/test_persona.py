from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    PersonaContent,
    PersonaCreate,
    PersonaMode,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionContent,
    PersonaVersionRead,
    ResourceBlock,
    VersionStatus,
)


def _content() -> PersonaVersionContent:
    return PersonaVersionContent(description="Tester", system_prompt="Be helpful.")


def test_content_defaults_traits_to_empty_list() -> None:
    assert _content().traits == []


def test_content_defaults_tags_to_empty_list() -> None:
    assert _content().tags == []


def test_content_defaults_blocknote_content_to_none() -> None:
    assert _content().content is None


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
        PersonaVersionContent(description="x" * 2_001, system_prompt="s")
    with pytest.raises(ValidationError):
        PersonaVersionContent(description="d", system_prompt="x" * 20_001)


def test_content_rejects_too_many_traits() -> None:
    with pytest.raises(ValidationError):
        PersonaVersionContent(description="d", system_prompt="s", traits=["t"] * 51)


def test_content_rejects_oversized_trait_entry() -> None:
    with pytest.raises(ValidationError):
        PersonaVersionContent(description="d", system_prompt="s", traits=["x" * 201])


def test_content_rejects_too_many_or_too_long_tags() -> None:
    with pytest.raises(ValidationError):
        PersonaVersionContent(description="d", system_prompt="s", tags=["t"] * 51)
    with pytest.raises(ValidationError):
        PersonaVersionContent(description="d", system_prompt="s", tags=["x" * 101])


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


def test_persona_content_defaults_to_empty_blocknote() -> None:
    profile = PersonaContent()
    assert profile.description == ""
    assert profile.blocks == []


def test_persona_content_round_trips_through_version_content() -> None:
    profile = PersonaContent(
        description="Rolle, Tonfall, Beispiele",
        blocks=[ResourceBlock(id="b1", type="heading")],
    )
    container = PersonaVersionContent(description="d", system_prompt="s", content=profile)
    restored = PersonaVersionContent.model_validate(container.model_dump())
    assert restored.content == profile


def test_persona_content_rejects_too_many_blocks() -> None:
    blocks = [ResourceBlock(id=f"b{i}", type="paragraph") for i in range(2_001)]
    with pytest.raises(ValidationError):
        PersonaContent(blocks=blocks)


def test_persona_content_rejects_oversized_description() -> None:
    with pytest.raises(ValidationError):
        PersonaContent(description="x" * 2_001)


# ---------------------------------------------------------------------------
# PersonaMode + modes-Validator (C1 / C6)
# ---------------------------------------------------------------------------


def test_persona_mode_defaults() -> None:
    """PersonaMode legt sinnvolle Defaults fest."""
    mode = PersonaMode(name="Standard")
    assert mode.trigger is None
    assert mode.is_default is False
    assert mode.identity_add == ""
    assert mode.output_style_override == ""


def test_persona_mode_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PersonaMode(name="X", foo="bar")  # type: ignore[call-arg]


def test_persona_mode_name_min_length() -> None:
    with pytest.raises(ValidationError):
        PersonaMode(name="")


def test_modes_default_empty_list() -> None:
    """modes fehlt -> leere Liste (Backward-Compat)."""
    content = PersonaVersionContent(description="d")
    assert content.modes == []


def test_modes_single_default_ok() -> None:
    modes = [
        PersonaMode(name="Default-Modus", is_default=True),
        PersonaMode(name="Debug-Modus", is_default=False),
    ]
    content = PersonaVersionContent(description="d", modes=modes)
    assert len(content.modes) == 2


def test_modes_two_defaults_raises() -> None:
    """Hoechstens ein is_default=True erlaubt."""
    with pytest.raises(ValidationError, match="is_default"):
        PersonaVersionContent(
            description="d",
            modes=[
                PersonaMode(name="A", is_default=True),
                PersonaMode(name="B", is_default=True),
            ],
        )


def test_modes_duplicate_name_raises() -> None:
    """Modus-Namen case-insensitiv eindeutig."""
    with pytest.raises(ValidationError, match="case-insensitiv"):
        PersonaVersionContent(
            description="d",
            modes=[
                PersonaMode(name="Fokus"),
                PersonaMode(name="fokus"),  # Duplikat case-insensitiv
            ],
        )


def test_modes_empty_list_ok() -> None:
    """Leere modes-Liste ist gueltig."""
    content = PersonaVersionContent(description="d", modes=[])
    assert content.modes == []


def test_modes_round_trip_via_model_dump() -> None:
    """modes werden durch model_dump/model_validate korrekt erhalten."""
    original = PersonaVersionContent(
        description="d",
        modes=[
            PersonaMode(
                name="Erklaerer",
                trigger="erklaer,wie,warum",
                is_default=False,
                identity_add="Du bist ein Lehrer.",
                output_style_override="Schreibe einfach und verstaendlich.",
            ),
            PersonaMode(name="Standard", is_default=True),
        ],
    )
    restored = PersonaVersionContent.model_validate(original.model_dump())
    assert restored.modes == original.modes


def test_modes_max_length_enforced() -> None:
    """Mehr als 20 Modi werden abgelehnt."""
    with pytest.raises(ValidationError):
        PersonaVersionContent(
            description="d",
            modes=[PersonaMode(name=f"Modus-{i}") for i in range(21)],
        )
