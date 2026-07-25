"""Unit-Tests des Passage-Schnitts (ADR-0046).

Prueft die Zerlegung eines Versions-Contents in Passagen ohne DB: Schnitt an
Heading-Bloecken, Anker-Treue (`block_id` == bestehender Block-Anker aus
ADR-0021), Ueberschriften-Kette und Verlustfreiheit bei langen Abschnitten.
"""

import json

from who2be_api.services.content_chunks import chunk_content, chunk_version_content


def _para(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def _heading(block_id: str, text: str, level: int = 1) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": level},
        "content": [{"type": "text", "text": text, "styles": {}}],
    }


def test_resource_splits_at_headings_and_keeps_anchors() -> None:
    content = {
        "description": "Alles zum Thema Reklamation.",
        "blocks": [
            _heading("h1", "Annahme"),
            _para("p1", "Beschwerde aufnehmen."),
            _heading("h2", "Eskalation"),
            _para("p2", "An Teamleitung uebergeben."),
        ],
    }

    chunks = chunk_content("resource", content)

    assert [c.block_id for c in chunks] == [None, "h1", "h2"]
    assert [c.ord for c in chunks] == [0, 1, 2]
    # Die Praeambel ist die Beschreibung, ankerlos.
    assert chunks[0].text == "Alles zum Thema Reklamation."
    # Der Heading-Text steht als erste Zeile der Passage.
    assert chunks[1].text == "Annahme\n\nBeschwerde aufnehmen."
    assert chunks[2].text == "Eskalation\n\nAn Teamleitung uebergeben."


def test_heading_path_carries_ancestors_but_not_the_own_heading() -> None:
    content = {
        "description": "",
        "blocks": [
            _heading("h1", "Reklamation", level=1),
            _para("p1", "Grundsaetzliches."),
            _heading("h2", "Eskalation", level=2),
            _para("p2", "Ab Stufe 3."),
            _heading("h3", "Sonderfall", level=3),
            _para("p3", "Grosskunden."),
            _heading("h4", "Versand", level=1),
            _para("p4", "Anderes Thema."),
        ],
    }

    chunks = chunk_content("resource", content)
    paths = {c.block_id: c.heading_path for c in chunks}

    assert paths["h1"] == ""
    assert paths["h2"] == "Reklamation"
    assert paths["h3"] == "Reklamation > Eskalation"
    # Level 1 schliesst die tieferen Ebenen — kein Nachwirken.
    assert paths["h4"] == ""


def test_text_before_the_first_heading_becomes_an_anchorless_chunk() -> None:
    content = {
        "description": "",
        "blocks": [_para("p0", "Vorspann ohne Ueberschrift."), _heading("h1", "Kapitel")],
    }

    chunks = chunk_content("resource", content)

    assert [c.block_id for c in chunks] == [None, "h1"]
    assert chunks[0].text == "Vorspann ohne Ueberschrift."


def test_playbook_body_is_parsed_from_stringified_blocknote() -> None:
    """Playbook-Bodies sind ein String MIT stringifiziertem BlockNote-JSON."""
    body = json.dumps([_heading("h1", "Schritte"), _para("p1", "Erst pruefen.")])
    content = {"description": "Kurzbeschreibung", "body": body, "type": "workflow"}

    chunks = chunk_content("playbook", content)

    assert [c.block_id for c in chunks] == [None, "h1"]
    assert chunks[1].text == "Schritte\n\nErst pruefen."


def test_playbook_plain_text_body_falls_back_to_preamble() -> None:
    """Alt-Bestand ohne BlockNote-JSON darf nicht verloren gehen."""
    content = {"description": "Beschreibung", "body": "1. Einfach nur Text.", "type": "workflow"}

    chunks = chunk_content("playbook", content)

    assert len(chunks) == 1
    assert chunks[0].block_id is None
    assert "1. Einfach nur Text." in chunks[0].text
    assert "Beschreibung" in chunks[0].text


def test_external_tool_head_fields_are_indexed() -> None:
    content = {
        "display_name": "Todoist",
        "description": "Aufgabenverwaltung",
        "usage_notes": json.dumps([_heading("h1", "Wann nutzen"), _para("p1", "Bei To-dos.")]),
        "fallback_note": "Wenn nicht verbunden: nachfragen.",
        "tags": [],
    }

    chunks = chunk_content("external_tool", content)

    assert chunks[0].block_id is None
    assert "Todoist" in chunks[0].text
    assert "Wenn nicht verbunden" in chunks[0].text
    assert chunks[1].block_id == "h1"


def test_persona_profile_blocks_and_traits() -> None:
    content = {
        "description": "Support-Persona",
        "traits": ["gruendlich", "freundlich"],
        "content": {"description": "x", "blocks": [_heading("h1", "Tonfall")]},
    }

    chunks = chunk_content("persona", content)

    assert "gruendlich, freundlich" in chunks[0].text
    assert chunks[1].block_id == "h1"


def test_long_section_is_split_without_losing_text() -> None:
    """Lange Abschnitte werden verteilt, nicht abgeschnitten."""
    paragraphs = [_para(f"p{i}", "wort " * 200) for i in range(20)]
    content = {"description": "", "blocks": [_heading("h1", "Lang"), *paragraphs]}

    chunks = chunk_content("resource", content)

    assert len(chunks) > 1
    # Alle Teilstuecke tragen denselben Anker und fortlaufende Positionen.
    assert {c.block_id for c in chunks} == {"h1"}
    assert [c.ord for c in chunks] == list(range(len(chunks)))
    total = sum(len(c.text) for c in chunks)
    original = len("Lang") + sum(len("wort " * 200) for _ in range(20))
    # Nur die Trenn-Newlines gehen verloren, kein Inhalt.
    assert total >= original - 4 * len(chunks)


def test_empty_content_yields_no_chunks() -> None:
    assert chunk_content("resource", {"description": "", "blocks": []}) == []


def test_chunk_version_content_accepts_a_json_string() -> None:
    raw = json.dumps({"description": "Hallo", "blocks": []})

    chunks = chunk_version_content("resource", raw)

    assert [c.text for c in chunks] == ["Hallo"]


def test_chunk_version_content_survives_garbage() -> None:
    assert chunk_version_content("resource", "nicht json") == []
    assert chunk_version_content("resource", None) == []
