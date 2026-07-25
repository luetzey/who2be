"""Tests fuer das Content-Locale-Modell (ADR-0027 / Plan „Ein Element, eine
Sprache", 2026-07-24)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    DEFAULT_LOCALE,
    AgentWithRenderedPrompt,
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionContent,
    PlaybookCreate,
    ResourceCreate,
    SearchHit,
    SystemPromptTemplateContent,
    SystemPromptTemplateCreate,
    WorkspaceCreate,
    WorkspaceRead,
)
from who2be_models.locale import normalize_locale, validate_supported_locale


def test_default_locale_is_de() -> None:
    assert DEFAULT_LOCALE == "de"


def test_normalize_locale_trims_and_lowercases() -> None:
    assert normalize_locale("  EN ") == "en"
    assert normalize_locale("de-AT") == "de-at"


def test_normalize_locale_rejects_malformed() -> None:
    for bad in ("", "x", "deutsch!", "12", "en_US"):
        with pytest.raises(ValueError):
            normalize_locale(bad)


def test_validate_supported_locale_normalizes_and_accepts_supported() -> None:
    assert validate_supported_locale(" DE ") == "de"
    assert validate_supported_locale("EN") == "en"


def test_validate_supported_locale_rejects_unsupported() -> None:
    with pytest.raises(ValueError):
        validate_supported_locale("fr")


def test_workspace_create_defaults_content_locale_to_de() -> None:
    create = WorkspaceCreate(name="Acme", slug="acme")
    assert create.content_locale == "de"


def test_workspace_create_normalizes_content_locale() -> None:
    create = WorkspaceCreate(name="Acme", slug="acme", content_locale=" EN ")
    assert create.content_locale == "en"


def test_workspace_create_rejects_unsupported_content_locale() -> None:
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="Acme", slug="acme", content_locale="fr")


def test_workspace_read_defaults_content_locale_to_de() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    read = WorkspaceRead(
        id=uuid4(),
        org_id=uuid4(),
        name="Acme",
        slug="acme",
        created_at=datetime.now(UTC),
    )
    assert read.content_locale == "de"


def test_persona_create_locale_defaults_to_none() -> None:
    create = PersonaCreate(name="QA")
    assert create.locale is None


def test_persona_create_normalizes_and_accepts_supported_locale() -> None:
    create = PersonaCreate.model_validate({"name": "QA", "locale": " EN "})
    assert create.locale == "en"


def test_persona_create_rejects_unsupported_locale() -> None:
    with pytest.raises(ValidationError):
        PersonaCreate.model_validate({"name": "QA", "locale": "fr"})


def test_persona_update_allows_locale_switch() -> None:
    update = PersonaUpdate(
        content=PersonaVersionContent(description="Tester"),
        locale="en",
    )
    assert update.locale == "en"


def test_persona_update_rejects_unsupported_locale() -> None:
    with pytest.raises(ValidationError):
        PersonaUpdate(content=PersonaVersionContent(description="Tester"), locale="fr")


def test_playbook_and_resource_create_share_locale_contract() -> None:
    pb = PlaybookCreate.model_validate({"name": "PB", "locale": "en"})
    rsc = ResourceCreate.model_validate({"name": "R", "locale": "EN"})
    assert pb.locale == "en"
    assert rsc.locale == "en"


def test_system_prompt_template_create_accepts_locale() -> None:
    create = SystemPromptTemplateCreate(
        name="Builder",
        content=SystemPromptTemplateContent(body="Du bist hilfreich."),
        locale="en",
    )
    assert create.locale == "en"


def test_system_prompt_template_create_rejects_unsupported_locale() -> None:
    with pytest.raises(ValidationError):
        SystemPromptTemplateCreate(
            name="Builder",
            content=SystemPromptTemplateContent(body="Du bist hilfreich."),
            locale="fr",
        )


def _persona_read() -> PersonaRead:
    now = datetime.now(UTC)
    return PersonaRead(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
        name="Coach Carla",
        current_version=1,
        content=PersonaVersionContent(description="Senior Coach"),
        created_at=now,
        updated_at=now,
    )


def test_agent_with_rendered_prompt_locale_defaults_to_de() -> None:
    """WP5 (ADR-0045): fehlt `locale` (Alt-Client/Fixture), greift `DEFAULT_LOCALE`."""
    agent = AgentWithRenderedPrompt(
        id=uuid4(),
        name="Carla Bot",
        persona=_persona_read(),
        system_prompt_rendered="Du bist Coach Carla.\n\nAntworte auf Deutsch.",
        system_prompt_template_id=uuid4(),
    )
    assert agent.locale == DEFAULT_LOCALE


def test_agent_with_rendered_prompt_carries_explicit_locale() -> None:
    agent = AgentWithRenderedPrompt(
        id=uuid4(),
        name="Carla Bot",
        persona=_persona_read(),
        system_prompt_rendered="You are Coach Carla.\n\nRespond in English.",
        system_prompt_template_id=uuid4(),
        locale="en",
    )
    assert agent.locale == "en"


def test_search_hit_locale_defaults_to_de() -> None:
    """WP5 (ADR-0045): fehlt `locale` (Alt-Client/Fixture), greift `DEFAULT_LOCALE`."""
    hit = SearchHit(type="playbook", id=uuid4(), name="Reklamation", score=0.9)
    assert hit.locale == DEFAULT_LOCALE


def test_search_hit_carries_explicit_locale() -> None:
    hit = SearchHit(type="resource", id=uuid4(), name="Doc", score=0.3, locale="en")
    assert hit.locale == "en"
