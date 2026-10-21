"""Unit-Tests des Markdown-Schreibwegs ohne DB (ADR-0058 §4.2, §6.1 B, §6.2).

Die reinen Bausteine des Services: Abschnittsgrenzen, Anker-Erbe, bitgleicher
Body bei unveraendertem Inhalt, Feld-/Anker-Aufloesung, Fehlerabbildung und
die Eingabevalidierung von `ContentEdit`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from who2be_api.core.errors import ApiError
from who2be_api.repositories.versioned_repository import BaseRevConflictError
from who2be_api.services.content_markdown_service import (
    _MAPPERS,
    ContentMarkdownService,
    _body_string,
    _conflict_as_409,
    _conversion_error,
    _Field,
    _inherit_anchor,
    _section,
)
from who2be_models import MarkdownConversionError, PersonaVersionContent, from_markdown
from who2be_models.content_markdown import ContentEdit, MarkdownWrite


def _heading(bid: str, level: int) -> dict[str, Any]:
    return {"id": bid, "type": "heading", "props": {"level": level}, "children": []}


def _para(bid: str) -> dict[str, Any]:
    return {"id": bid, "type": "paragraph", "props": {}, "children": []}


_DOC = [
    _para("intro"),
    _heading("h1", 1),
    _para("p1"),
    _heading("h2", 2),
    _para("p2"),
    _heading("h3", 2),
    _para("p3"),
    _heading("h4", 1),
    _para("p4"),
]


# --- Abschnittsgrenzen --------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        ("h1", (1, 7)),  # bis vor die naechste Ebene-1-Ueberschrift
        ("h2", (3, 5)),  # gleiche Ebene beendet den Abschnitt
        ("h3", (5, 7)),  # hoehere Ebene beendet den Abschnitt
        ("h4", (7, 9)),  # letzter Abschnitt reicht bis zum Ende
        ("p1", None),  # Absaetze sind keine Anker
        ("fehlt", None),
    ],
)
def test_section_bounds(anchor: str, expected: tuple[int, int] | None) -> None:
    assert _section(_DOC, anchor) == expected


def test_blocks_without_anchor_belong_to_preceding_section() -> None:
    start, end = _section(_DOC, "h2") or (0, 0)
    assert [b["id"] for b in _DOC[start:end]] == ["h2", "p2"]


# --- Anker-Erbe bei replace ---------------------------------------------------


def test_inherit_anchor_adds_id_to_first_heading_without_anchor() -> None:
    assert _inherit_anchor("\n## Neu\n\nText", "abc") == "\n## Neu [#abc]\n\nText"


def test_inherit_anchor_keeps_explicit_anchor_and_ignores_paragraph_start() -> None:
    assert _inherit_anchor("## Neu [#xyz]\n", "abc") == "## Neu [#xyz]\n"
    assert _inherit_anchor("Nur Text\n\n## Spaeter", "abc") == "Nur Text\n\n## Spaeter"


# --- Bitgleichheit ------------------------------------------------------------


def test_body_string_keeps_stored_string_when_blocks_are_unchanged() -> None:
    blocks = from_markdown("# Titel\n\nText.", None)
    # Gespeichert mit anderer Serialisierung (Leerraum): bleibt Byte fuer Byte.
    stored = json.dumps(blocks, indent=2)
    assert _body_string(blocks, stored) == stored
    changed = from_markdown("# Titel\n\nAnders.", blocks)
    assert _body_string(changed, stored) != stored
    assert json.loads(_body_string(changed, stored)) == changed


def test_body_string_empty_document_uses_field_default() -> None:
    assert _body_string([], "", empty="[]") == "[]"


def test_playbook_mapper_roundtrip_is_bitwise_for_unchanged_markdown() -> None:
    from who2be_models import PlaybookContent

    blocks = from_markdown("# A\n\nText *kursiv*.\n\n- x\n- y", None)
    stored = PlaybookContent.model_validate({"body": json.dumps(blocks), "type": "workflow"})
    mapper = _MAPPERS["playbooks"]
    md = mapper.to_markdown_content(stored)
    service = ContentMarkdownService.__new__(ContentMarkdownService)
    back = mapper.from_markdown_content(md, stored, service._converter({}))
    assert back.model_dump() == stored.model_dump()


def test_persona_mapper_fields_cover_profile_and_modes() -> None:
    content = PersonaVersionContent.model_validate(
        {"description": "d", "modes": [{"name": "Recherche", "anti_patterns": []}]}
    )
    names = [f.name for f in _MAPPERS["personas"].fields(content)]
    assert names == [
        "profile",
        "modes[Recherche].identity_add",
        "modes[Recherche].output_style_override",
        "modes[Recherche].anti_patterns",
    ]


# --- Feld-/Anker-Aufloesung ---------------------------------------------------


def _edit(**kw: Any) -> ContentEdit:
    return ContentEdit.model_validate({"base_rev": "0" * 16, "op": "delete", **kw})


def test_locate_field_is_case_insensitive_for_modes() -> None:
    fields = [_Field("profile", []), _Field("modes[Recherche].anti_patterns", [])]
    found, section = ContentMarkdownService._locate(
        fields, _edit(field="modes[recherche].anti_patterns")
    )
    assert found.name == "modes[Recherche].anti_patterns" and section is None


def test_locate_unknown_field_and_anchor_are_anchor_unknown() -> None:
    fields = [_Field("body", _DOC)]
    with pytest.raises(ApiError) as field_exc:
        ContentMarkdownService._locate(fields, _edit(field="profile"))
    assert field_exc.value.reason == "anchor_unknown"
    assert field_exc.value.status_code == 422
    with pytest.raises(ApiError) as anchor_exc:
        ContentMarkdownService._locate(fields, _edit(anchor="p1"))
    assert anchor_exc.value.reason == "anchor_unknown"
    found, section = ContentMarkdownService._locate(fields, _edit(anchor="h4"))
    assert section == (7, 9)


# --- Fehlerabbildung ----------------------------------------------------------


def test_conversion_error_maps_reason_and_params() -> None:
    with pytest.raises(MarkdownConversionError) as raw:
        from_markdown("# A [#x1]\n\n## B [#x1]", [_heading("x1", 1)])
    err = _conversion_error(raw.value, "body")
    assert err.status_code == 422
    assert err.reason == "anchor_duplicate"
    assert err.params is not None and err.params["field"] == "body"


def test_base_rev_conflict_becomes_409_version_conflict() -> None:
    with pytest.raises(ApiError) as exc, _conflict_as_409():
        raise BaseRevConflictError(4, "abcdef0123456789")
    assert exc.value.status_code == 409
    assert exc.value.reason == "version_conflict"
    assert exc.value.params == {"current_version": 4, "current_base_rev": "abcdef0123456789"}


# --- Eingabemodelle -----------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"op": "delete"},  # weder anchor noch field
        {"op": "delete", "anchor": "a", "field": "body"},  # beides
        {"op": "delete", "anchor": "a", "markdown": "x"},  # delete mit markdown
        {"op": "replace", "anchor": "a"},  # replace ohne markdown
    ],
)
def test_content_edit_rejects_invalid_targets(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ContentEdit.model_validate({"base_rev": "0" * 16, **payload})


def test_content_edit_requires_base_rev_but_put_does_not() -> None:
    with pytest.raises(ValidationError):
        ContentEdit.model_validate({"op": "delete", "anchor": "a"})
    assert MarkdownWrite.model_validate({"content": {}}).base_rev is None
