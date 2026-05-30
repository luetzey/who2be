"""Unit-Tests fuer den Placeholder-Renderer (`AgentRenderService._substitute`).

Sieben Standard-Placeholders + Unknown-Fall, ohne DB. Wir testen die
private `_substitute`-Funktion direkt — Integrations-Pfad gegen den
Endpoint deckt `test_agents.py` ab.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from who2be_api.services.agent_render_service import (
    _AgentRenderContext,
    _substitute,
)
from who2be_models import PlaybookContent, PlaybookRead


def _ctx(**overrides: object) -> _AgentRenderContext:
    defaults: dict[str, object] = {
        "persona_name": "Coach Carla",
        "persona_description": "Senior Customer-Support-Coach",
        "persona_profile_text": "Empathisch, präzise, lösungsorientiert.",
        "persona_tags": ["support", "coaching"],
        "playbooks": [],
        "triggers": [],
        "resource_snippets": [],
    }
    defaults.update(overrides)
    return _AgentRenderContext(**defaults)  # type: ignore[arg-type]


def _playbook(name: str, body: str, triggers: str | None = None) -> PlaybookRead:
    return PlaybookRead(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("00000000-0000-0000-0000-000000000002"),
        owner_id=UUID("00000000-0000-0000-0000-000000000003"),
        name=name,
        current_version=1,
        type="prompt",
        tags=[],
        triggers=triggers,
        content=PlaybookContent(
            description=f"{name} description",
            body=body,
            type="prompt",
            tags=[],
            triggers=triggers,
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def test_resolves_persona_name() -> None:
    out, unresolved = _substitute("Hallo {{ persona.name }}!", _ctx(), "plain")
    assert out == "Hallo Coach Carla!"
    assert unresolved == []


def test_resolves_persona_description() -> None:
    out, _ = _substitute("{{ persona.description }}", _ctx(), "plain")
    assert out == "Senior Customer-Support-Coach"


def test_resolves_persona_profile() -> None:
    out, _ = _substitute("Profil: {{ persona.profile }}", _ctx(), "plain")
    assert "Empathisch" in out


def test_resolves_persona_tags_comma_separated() -> None:
    out, _ = _substitute("Tags: {{ persona.tags }}", _ctx(), "plain")
    assert out == "Tags: support, coaching"


def test_resolves_playbooks_with_block_layout_plain() -> None:
    ctx = _ctx(
        playbooks=[
            _playbook("Reset-Mail beantworten", "Schritt 1: ..."),
            _playbook("Eskalation", "Schritt 1: ..."),
        ],
    )
    out, _ = _substitute("{{ playbooks }}", ctx, "plain")
    assert "### Reset-Mail beantworten" in out
    assert "### Eskalation" in out


def test_resolves_triggers_dedup_comma_separated() -> None:
    ctx = _ctx(triggers=["passwort", "reset", "passwort"])
    out, _ = _substitute("{{ triggers }}", ctx, "plain")
    # `_dedup_in_order` laeuft im Service vor dem Substitute; hier reicht es,
    # dass die uebergebene Reihenfolge erhalten bleibt.
    assert out.startswith("passwort, reset, passwort")


def test_resolves_resources_snippets() -> None:
    ctx = _ctx(resource_snippets=["#### Tone-Guide\nSei knapp."])
    out, _ = _substitute("{{ resources }}", ctx, "plain")
    assert "Tone-Guide" in out
    assert "Sei knapp." in out


def test_unknown_placeholder_marked_and_reported() -> None:
    out, unresolved = _substitute("Hallo {{ persona.name }}, {{ unknown_field }}!", _ctx(), "plain")
    assert "⚠ {{ unknown_field }}" in out
    assert unresolved == ["unknown_field"]


def test_unknown_placeholder_dedup() -> None:
    _, unresolved = _substitute("{{ a }} {{ b }} {{ a }}", _ctx(), "plain")
    assert unresolved == ["a", "b"]


def test_empty_profile_renders_empty_string() -> None:
    out, unresolved = _substitute(
        "X={{ persona.profile }}Y", _ctx(persona_profile_text=""), "plain"
    )
    assert out == "X=Y"
    assert unresolved == []


def test_empty_triggers_renders_empty_string() -> None:
    out, _ = _substitute("Triggers: {{ triggers }}!", _ctx(triggers=[]), "plain")
    assert out == "Triggers: !"


def test_markdown_playbooks_use_h2_headers() -> None:
    ctx = _ctx(playbooks=[_playbook("Reset-Mail", "Schritt 1")])
    out, _ = _substitute("{{ playbooks }}", ctx, "markdown")
    assert out.startswith("## Reset-Mail")


def test_markdown_triggers_as_bullet_list() -> None:
    ctx = _ctx(triggers=["a", "b"])
    out, _ = _substitute("{{ triggers }}", ctx, "markdown")
    assert "- a" in out
    assert "- b" in out


def test_html_renders_h2_via_markdown_it() -> None:
    ctx = _ctx(playbooks=[_playbook("Reset-Mail", "Schritt 1")])
    out, _ = _substitute("# Header\n\n{{ playbooks }}", ctx, "html")
    assert "<h2>Reset-Mail</h2>" in out


def test_persona_system_prompt_is_not_a_known_placeholder() -> None:
    """Track 3 deprecated den `persona.system_prompt`-Placeholder."""
    out, unresolved = _substitute("X={{ persona.system_prompt }}", _ctx(), "plain")
    assert "⚠ {{ persona.system_prompt }}" in out
    assert unresolved == ["persona.system_prompt"]


def test_placeholder_whitespace_is_tolerated() -> None:
    out, _ = _substitute("{{persona.name}}", _ctx(), "plain")
    assert out == "Coach Carla"


@pytest.mark.parametrize("output_format", ["plain", "markdown", "html"])
def test_format_is_carried_through(output_format: str) -> None:
    out, _ = _substitute("static", _ctx(), output_format)  # type: ignore[arg-type]
    assert "static" in out
