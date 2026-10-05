"""Tests fuer die Markdown-Darstellung der lesenden Werkzeuge (ADR-0056, Paket 1).

`text_view` rendert nur; die Werkzeuge nutzen es erst ab Paket 3. Die Tests
treiben die Renderer deshalb direkt mit validierten Modellen, so wie die API
sie liefert.

Jeder Test fuehrt seine Rot-Probe mit: zuerst wird belegt, dass das
`full`-Modell desselben Fixtures Editor-JSON traegt (Block-Struktur bzw.
stringifiziertes BlockNote-JSON). Erst dann wird geprueft, dass der Text
davon nichts mehr enthaelt, den Inhalt aber lesbar zeigt. Faellt die
Umwandlung weg, schlaegt `_assert_no_editor_json` an.
"""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from who2be_mcp import text_view
from who2be_mcp.text_view import FULL_FORMAT_HINT
from who2be_models import (
    AgentWithRenderedPrompt,
    ExternalToolRead,
    PersonaRead,
    PersonaVersionRead,
    PlaybookRead,
    PlaybookVersionRead,
    ResourceBlockAnchor,
    ResourceLinkRead,
    ResourceRead,
    ResourceVersionRead,
    SubResourceRead,
    SystemPromptTemplateRead,
    SystemPromptTemplateVersionRead,
    VersionDiff,
)

_WS = uuid4()
_NOW = "2026-10-05T12:00:00Z"
# Diese Marker stehen nur in Editor-JSON, nie im lesbaren Inhalt der Fixtures.
_EDITOR_MARKERS = ('"type"', '"props"', '"styles"', '"children"', "textAlignment", '\\"')


def _para(text: str, block_id: str | None = None) -> dict[str, object]:
    return {
        "id": block_id or f"b-{uuid4().hex[:8]}",
        "type": "paragraph",
        "props": {"textAlignment": "left", "textColor": "default"},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _heading(text: str, block_id: str) -> dict[str, object]:
    block = _para(text, block_id)
    block["type"] = "heading"
    block["props"] = {"level": 2}
    return block


def _pill_para(prefix: str, kind: str, target: str) -> dict[str, object]:
    block = _para(prefix)
    block["content"] = [
        {"type": "text", "text": prefix, "styles": {}},
        {"type": "placeholder", "props": {"kind": kind, "target_id": target}},
    ]
    return block


def _body(*blocks: dict[str, object]) -> str:
    return json.dumps(list(blocks), ensure_ascii=False)


def _base(name: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WS),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 3,
        "current_status": "active",
        "locale": "de",
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _persona_content() -> dict[str, object]:
    return {
        "description": "Autonomer Code-Agent",
        "traits": ["methodisch"],
        "tags": ["code"],
        "content": {"description": "", "blocks": [_para('Profil mit "Zitat" / Slash')]},
        "modes": [
            {
                "name": "Refiner",
                "trigger": "issue veredeln",
                "is_default": False,
                "identity_add": [_para("Veredelungs-Haltung")],
                "output_style_override": [_para("Kein Plan")],
                "anti_patterns": [_para("Raten")],
            }
        ],
    }


def _persona() -> PersonaRead:
    return PersonaRead.model_validate({**_base("Coder"), "content": _persona_content()})


def _playbook(name: str = "Code-Task-Flow") -> PlaybookRead:
    return PlaybookRead.model_validate(
        {
            **_base(name),
            "type": "workflow",
            "tags": ["workflow"],
            "triggers": "arbeite Task ab",
            "content": {
                "description": f"Beschreibung {name}",
                "body": _body(_heading("Schritt 1", "h1"), _para(f"Prozedur von {name}")),
                "type": "workflow",
            },
        }
    )


def _resource(name: str = "Norm") -> ResourceRead:
    return ResourceRead.model_validate(
        {
            **_base(name),
            "slug": name.lower(),
            "content": {
                "description": f"Beschreibung {name}",
                "blocks": [_pill_para("Siehe ", "playbook", "p-1"), _para(f"Inhalt {name}")],
                "tags": ["norm"],
            },
        }
    )


def _template() -> SystemPromptTemplateRead:
    return SystemPromptTemplateRead.model_validate(
        {
            **_base("Standard"),
            "slug": "standard",
            "agent_count": 2,
            "content": {
                "description": "Basis-Template",
                "body": _body(_pill_para("Persona: ", "persona-field", "profile")),
            },
        }
    )


def _external_tool() -> ExternalToolRead:
    return ExternalToolRead.model_validate(
        {
            **_base("Todoist"),
            "alias": "todo",
            "content": {
                "display_name": "Todoist",
                "mcp_server_name": "todoist",
                "tool_names": ["add_task"],
                "usage_notes": _body(_para('Aufgaben mit "add_task" anlegen')),
                "fallback_note": "Ohne Tool: im Chat notieren",
                "tags": ["tasks"],
            },
        }
    )


def _assert_no_editor_json(full: str, text: str) -> None:
    """Rot-Probe + Pruefung: der full-Dump traegt Editor-JSON, der Text nicht."""
    assert any(marker in full for marker in _EDITOR_MARKERS), "Fixture ohne Editor-JSON"
    for marker in _EDITOR_MARKERS:
        assert marker not in text, f"Editor-JSON im Text: {marker}"
    # Ein Markdown-Dokument, kein JSON-Objekt.
    assert not text.lstrip().startswith(("{", "["))
    assert FULL_FORMAT_HINT in text
    assert text.endswith("\n")


def test_persona_text_shows_profile_modes_and_catalog_without_blocks() -> None:
    persona = _persona()
    playbook = _playbook()
    full = persona.model_dump_json() + playbook.model_dump_json()

    text = text_view.persona_text(
        persona,
        body_rendered='Profil mit "Zitat" / Slash',
        playbooks=[playbook],
        mode="Refiner",
    )

    _assert_no_editor_json(full, text)
    assert text.startswith("# Persona: Coder\n")
    assert f"- id: {persona.id}" in text
    assert "- aktiver Modus: Refiner" in text
    assert 'Profil mit "Zitat" / Slash' in text
    assert "### Refiner" in text
    assert "**Trigger:** issue veredeln" in text
    assert "**Identitaet ergaenzt:** Veredelungs-Haltung" in text
    assert "**Anti-Patterns:** Raten" in text
    assert f"- Code-Task-Flow (`{playbook.id}`) — Trigger: arbeite Task ab" in text
    # Der Playbook-Body gehoert nicht in den Katalog.
    assert "Prozedur von" not in text


def test_agent_text_carries_rendered_prompt_and_mode_fields() -> None:
    agent = AgentWithRenderedPrompt.model_validate(
        {
            "id": str(uuid4()),
            "name": "Coder-Agent",
            "persona": _persona().model_dump(mode="json"),
            "system_prompt_rendered": "Du bist Coder.\n\nAntworte auf Deutsch.",
            "system_prompt_template_id": str(uuid4()),
            "unresolved_placeholders": ["playbook:weg"],
            "locale": "de",
        }
    )

    text = text_view.agent_text(agent)

    _assert_no_editor_json(agent.model_dump_json(), text)
    assert "## System-Prompt\n\nDu bist Coder.\n\nAntworte auf Deutsch." in text
    assert "- ungeloeste Platzhalter: playbook:weg" in text
    assert "**Output-Stil ersetzt:** Kein Plan" in text


def test_playbook_list_text_has_head_and_description_but_no_body() -> None:
    playbooks = [_playbook("A"), _playbook("B")]
    full = "".join(p.model_dump_json() for p in playbooks)

    text = text_view.playbook_list_text(playbooks)

    _assert_no_editor_json(full, text)
    assert text.startswith("# Playbooks (2)\n")
    assert "## A" in text and "## B" in text
    assert "- trigger: arbeite Task ab" in text
    assert "Beschreibung A" in text
    assert "Prozedur von A" not in text


def test_playbook_text_renders_nested_bodies_as_text() -> None:
    """Die Luecke aus ADR-0056 §1.2: auch Kinder und Inline-Resources als Text."""
    playbook = _playbook()
    child = _playbook("Kind")
    resource = _resource("Eingebettet")
    link = ResourceLinkRead(
        resource_id=resource.id,
        resource_name=resource.name,
        block_id="h9",
        position=0,
        available=True,
        link_scope="block",
    )
    full = playbook.model_dump_json() + child.model_dump_json() + resource.model_dump_json()

    text = text_view.playbook_text(
        playbook,
        body_rendered="Schritt 1\n\nProzedur von Code-Task-Flow",
        sections=[ResourceBlockAnchor(block_id="h1", level=2, text="Schritt 1")],
        linked_blocks=[link],
        linked_resources=[resource],
        composed_playbooks=[child],
    )

    _assert_no_editor_json(full, text)
    assert "- Schritt 1 (`h1`)" in text
    assert "## Prozedur\n\nSchritt 1\n\nProzedur von Code-Task-Flow" in text
    assert f"- Eingebettet (`{resource.id}`), Block `h9` [lazy]" in text
    assert "Inhalt Eingebettet" in text
    assert "Siehe {{playbook:p-1}}" in text
    assert f"### Kind (`{child.id}`)" in text
    assert "Prozedur von Kind" in text


def test_playbook_text_outline_has_sections_but_no_procedure() -> None:
    text = text_view.playbook_text(
        _playbook(),
        body_rendered=None,
        sections=[ResourceBlockAnchor(block_id="h1", level=1, text="Start")],
    )
    assert "- Start (`h1`)" in text
    assert "## Prozedur" not in text


def test_resource_text_shows_blocks_subs_and_inline_children() -> None:
    resource = _resource()
    child = _resource("Kind")
    resource.sub_resources = [
        SubResourceRead(id=child.id, name="Kind", embedding_mode="inline"),
        SubResourceRead(id=uuid4(), name="Lazy", link_scope="block", block_id="h2"),
    ]
    resource.inline_sub_resources = [child]

    text = text_view.resource_text(resource)

    _assert_no_editor_json(resource.model_dump_json(), text)
    assert text.startswith("# Resource: Norm\n")
    assert "- slug: norm" in text
    assert "Siehe {{playbook:p-1}}\n\nInhalt Norm" in text
    assert f"- Kind [resource, inline]: `fetch_resource('{child.id}')`" in text
    assert "- Lazy [block, lazy], Block `h2`" in text
    assert "Inhalt Kind" in text


def test_system_prompt_text_unwraps_stringified_body() -> None:
    template = _template()
    full = template.model_dump_json()
    # Rot-Probe: im full-Dump steht der Body als escapter JSON-String.
    assert '\\"placeholder\\"' in full

    text = text_view.system_prompt_text(template)

    _assert_no_editor_json(full, text)
    assert "Persona: {{persona-field:profile}}" in text
    assert "- agenten: 2" in text


def test_system_prompt_list_text_leaves_bodies_out() -> None:
    templates = [_template(), _template()]
    text = text_view.system_prompt_list_text(templates)
    _assert_no_editor_json("".join(t.model_dump_json() for t in templates), text)
    assert text.startswith("# System-Prompts (2)\n")
    assert "Basis-Template" in text
    assert "{{persona-field:profile}}" not in text


def test_external_tool_texts_unwrap_usage_notes() -> None:
    tool = _external_tool()
    full = tool.model_dump_json()

    detail = text_view.external_tool_text(tool)
    listing = text_view.external_tool_list_text([tool])

    _assert_no_editor_json(full, detail)
    _assert_no_editor_json(full, listing)
    assert 'Aufgaben mit "add_task" anlegen' in detail
    assert "- alias: todo" in detail
    assert "## Fallback\n\nOhne Tool: im Chat notieren" in detail
    assert "- Tools: add_task" in listing
    assert "Aufgaben mit" not in listing


def _version_payload(content: dict[str, object], version: int = 2) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "version": version,
        "status": "draft",
        "locale": "de",
        "content": content,
        "created_by": str(uuid4()),
        "created_at": _NOW,
    }


@pytest.mark.parametrize(
    ("model", "content", "expected"),
    [
        (PersonaVersionRead, _persona_content(), 'Profil mit "Zitat" / Slash'),
        (
            PlaybookVersionRead,
            {"description": "D", "body": _body(_para("Body-Text"))},
            "Body-Text",
        ),
        (ResourceVersionRead, {"description": "D", "blocks": [_para("Block-Text")]}, "Block-Text"),
        (
            SystemPromptTemplateVersionRead,
            {"description": "D", "body": _body(_para("Template-Text"))},
            "Template-Text",
        ),
    ],
)
def test_version_text_serialises_every_snapshot_type(
    model: type[PersonaVersionRead], content: dict[str, object], expected: str
) -> None:
    version = model.model_validate(_version_payload(content))
    text = text_view.version_text("playbook", "e-1", version)
    _assert_no_editor_json(version.model_dump_json(), text)
    assert "- status: draft" in text
    assert expected in text


def test_version_text_handles_external_tool_snapshot() -> None:
    from who2be_models import ExternalToolVersionRead

    version = ExternalToolVersionRead.model_validate(
        _version_payload({"usage_notes": _body(_para("Notiz-Text")), "tool_names": ["x"]})
    )
    text = text_view.version_text("external_tool", "e-1", version)
    _assert_no_editor_json(version.model_dump_json(), text)
    assert "Notiz-Text" in text


def test_version_list_text_lists_heads_only() -> None:
    versions = [
        ResourceVersionRead.model_validate(
            _version_payload({"blocks": [_para(f"Inhalt {n}")]}, version=n)
        )
        for n in (1, 2)
    ]
    text = text_view.version_list_text("resource", "r-1", versions)
    _assert_no_editor_json("".join(v.model_dump_json() for v in versions), text)
    assert "## Version 1" in text and "## Version 2" in text
    assert "Inhalt 1" not in text


def test_diff_text_drops_raw_values_and_keeps_readable_compare() -> None:
    diff = VersionDiff.model_validate(
        {
            "version": 3,
            "against": "active",
            "against_version": 2,
            "identical": False,
            "changes": [
                {
                    "path": "content.blocks[b1]",
                    "op": "changed",
                    "before": _para("alt"),
                    "after": _para("neu"),
                },
            ],
            "before_text": "alt",
            "after_text": "neu",
        }
    )

    text = text_view.diff_text("resource", "r-1", diff)

    _assert_no_editor_json(diff.model_dump_json(), text)
    assert "- gegen: active (Version 2)" in text
    assert "- changed `content.blocks[b1]`" in text
    assert "## Vorher\n\nalt" in text
    assert "## Nachher\n\nneu" in text


def test_text_is_unescaped_when_serialised_as_tool_result() -> None:
    """Der Kern der Owner-Beschwerde: ein String-Ergebnis kommt ohne Escaping an.

    Rot-Probe: dasselbe Feld in einem JSON-Objekt traegt `\\n` und `\\"`.
    """
    text = text_view.resource_text(_resource())
    wrapped = json.dumps({"body": text})
    assert "\\n" in wrapped
    assert "\\n" not in text and '\\"' not in text


def test_uuid_and_timestamps_render_as_plain_values() -> None:
    version = ResourceVersionRead(
        id=UUID(int=1),
        version=1,
        content={"blocks": []},  # type: ignore[arg-type]
        created_by=UUID(int=2),
        created_at=datetime(2026, 10, 5, tzinfo=UTC),
    )
    text = text_view.version_list_text("resource", "r-1", [version])
    assert "- erstellt: 2026-10-05T00:00:00+00:00" in text
    assert f"- von: {UUID(int=2)}" in text
