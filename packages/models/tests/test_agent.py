"""Unit-Tests fuer das Agent-Aggregat (Track H — leere Huelle + Copy)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    AgentCopy,
    AgentCreate,
    AgentRead,
    AgentStatus,
)


def _read(
    *, persona_id: object, template_id: object, persona_active: bool = False
) -> AgentRead:
    now = datetime.now(UTC)
    return AgentRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="Carla",
        description="",
        persona_id=persona_id,  # type: ignore[arg-type]
        system_prompt_template_id=template_id,  # type: ignore[arg-type]
        status=AgentStatus.enabled,
        persona_active=persona_active,
        created_at=now,
        updated_at=now,
    )


def test_create_allows_empty_shell() -> None:
    agent = AgentCreate(name="Huelle")
    assert agent.persona_id is None
    assert agent.system_prompt_template_id is None
    # Default disabled: eine frische Huelle ist noch nicht aktivierbar.
    assert agent.status is AgentStatus.disabled


def test_create_accepts_full_refs() -> None:
    persona = uuid4()
    template = uuid4()
    agent = AgentCreate(name="Voll", persona_id=persona, system_prompt_template_id=template)
    assert agent.persona_id == persona
    assert agent.system_prompt_template_id == template


def test_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        AgentCreate(name="")


def test_is_shell_true_when_any_ref_missing() -> None:
    assert _read(persona_id=None, template_id=uuid4()).is_shell is True
    assert _read(persona_id=uuid4(), template_id=None).is_shell is True
    assert _read(persona_id=None, template_id=None).is_shell is True


def test_is_shell_false_when_complete() -> None:
    assert _read(persona_id=uuid4(), template_id=uuid4()).is_shell is False


def test_missing_lists_all_gaps_for_empty_shell() -> None:
    read = _read(persona_id=None, template_id=None, persona_active=False)
    assert read.missing == ["persona", "template", "persona_active"]
    assert read.activatable is False


def test_missing_reports_persona_active_when_persona_set_but_inactive() -> None:
    read = _read(persona_id=uuid4(), template_id=uuid4(), persona_active=False)
    assert read.missing == ["persona_active"]
    assert read.activatable is False


def test_missing_reports_template_only_when_persona_active() -> None:
    read = _read(persona_id=uuid4(), template_id=None, persona_active=True)
    assert read.missing == ["template"]
    assert read.activatable is False


def test_activatable_true_when_complete_and_persona_active() -> None:
    read = _read(persona_id=uuid4(), template_id=uuid4(), persona_active=True)
    assert read.missing == []
    assert read.activatable is True


def test_missing_and_activatable_serialized() -> None:
    """`missing`/`activatable` sind computed_fields → muessen im Dump erscheinen."""
    dumped = _read(persona_id=None, template_id=None).model_dump()
    assert dumped["activatable"] is False
    assert dumped["missing"] == ["persona", "template", "persona_active"]


def test_copy_name_optional() -> None:
    assert AgentCopy().name is None
    assert AgentCopy(name="Kopie").name == "Kopie"


def test_copy_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        AgentCopy(name="")
