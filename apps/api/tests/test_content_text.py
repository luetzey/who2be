"""Unit-Tests fuer die kanonische Klartext-Serialisierung (WP-C, Versions-Diff).

Kein DB-Zugriff: prueft die reine Serialisierung der vier Versions-Content-
Formen (Persona/Playbook/Resource/System-Prompt) zu deterministischem
Markdown-/Klartext fuer die git-artige Diff-Ansicht.
"""

import json

from who2be_api.services.content_text import (
    blocknote_body_text,
    persona_content_text,
    playbook_content_text,
    resource_content_text,
    system_prompt_content_text,
)


def _block(block_id: str, text: str, **props: object) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": dict(props),
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _pill_block(block_id: str, kind: str, target_id: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [
            {"type": "text", "text": "Nutze ", "styles": {}},
            {"type": "placeholder", "props": {"kind": kind, "target_id": target_id}},
        ],
    }


# --- blocknote_body_text (stringifiziertes BlockNote-JSON) ---


def test_blocknote_body_text_renders_top_level_array() -> None:
    body = json.dumps([_block("b1", "Erster Absatz"), _block("b2", "Zweiter Absatz")])
    assert blocknote_body_text(body) == "Erster Absatz\n\nZweiter Absatz"


def test_blocknote_body_text_renders_wrapper_object() -> None:
    body = json.dumps({"content": [_block("b1", "Hallo")]})
    assert blocknote_body_text(body) == "Hallo"


def test_blocknote_body_text_renders_placeholder_pills_as_tokens() -> None:
    body = json.dumps([_pill_block("b1", "playbook", "abc-123")])
    assert blocknote_body_text(body) == "Nutze {{playbook:abc-123}}"


def test_blocknote_body_text_falls_back_to_raw_on_invalid_json() -> None:
    assert blocknote_body_text("kein json, nur text") == "kein json, nur text"


def test_blocknote_body_text_empty_body_is_empty() -> None:
    assert blocknote_body_text("") == ""
    assert blocknote_body_text("[]") == ""


def test_blocknote_body_text_nested_children() -> None:
    parent: dict[str, object] = _block("b1", "Eltern")
    parent["children"] = [_block("b2", "Kind")]
    assert blocknote_body_text(json.dumps([parent])) == "Eltern\nKind"


# --- Entity-Serialisierer ---


def test_playbook_content_text_serializes_description_and_body() -> None:
    content: dict[str, object] = {
        "description": "Onboarding-Ablauf",
        "body": json.dumps([_block("b1", "Schritt eins")]),
        "type": "workflow",
        "tags": ["a"],
        "triggers": "x",
    }
    assert playbook_content_text(content) == "Onboarding-Ablauf\n\nSchritt eins"


def test_resource_content_text_serializes_blocks_with_pills() -> None:
    content: dict[str, object] = {
        "description": "Styleguide",
        "blocks": [_block("b1", "Regel eins"), _pill_block("b2", "resource", "xyz")],
        "tags": [],
    }
    assert resource_content_text(content) == "Styleguide\n\nRegel eins\n\nNutze {{resource:xyz}}"


def test_system_prompt_content_text_parses_stringified_blocknote_body() -> None:
    content: dict[str, object] = {
        "description": "Standard",
        "body": json.dumps([_pill_block("b1", "persona-ref", "")]),
    }
    assert system_prompt_content_text(content) == "Standard\n\nNutze {{persona-ref:}}"


def test_persona_content_text_matches_profile_render() -> None:
    content: dict[str, object] = {
        "description": "QA-Persona",
        "content": {"description": "", "blocks": [_block("b1", "Ich pruefe alles")]},
        "traits": ["genau"],
        "tags": [],
        "modes": [
            {
                "name": "Streng",
                "is_default": True,
                "trigger": "review",
                "identity_add": [_block("m1", "Noch strenger")],
            }
        ],
        "skills": [],
    }
    text = persona_content_text(content)
    assert "QA-Persona" in text
    assert "Ich pruefe alles" in text
    assert "**Traits:**\n- genau" in text
    assert "### Streng (Default)" in text
    assert "**Trigger:** review" in text
    assert "**Identity-Ergaenzung:** Noch strenger" in text


def test_serialization_is_deterministic() -> None:
    content: dict[str, object] = {
        "description": "d",
        "blocks": [_block("b1", "x"), _pill_block("b2", "playbook", "id-1")],
        "tags": ["t"],
    }
    assert resource_content_text(content) == resource_content_text(dict(content))


def test_empty_contents_serialize_to_empty_string() -> None:
    assert playbook_content_text({}) == ""
    assert resource_content_text({}) == ""
    assert system_prompt_content_text({}) == ""
    assert persona_content_text({}) == ""
