"""Unit-Tests fuer den Placeholder-Renderer und alle Resolver.

Kein DB-Zugriff in den Unit-Tests — wir mocken `asyncpg.Connection` mit
einem einfachen Fake, der `fetchrow` implementiert. Der Integrations-Pfad
gegen echte DB laeuft in `test_fetch_agent_endpoint.py`.

Welle 6: Resolver geben `ResolveResult` zurueck; `render_template_body`
liefert `tuple[str, list[str]]`. Tests pruefen sowohl `text` als auch
`unresolved_key` / die unresolved-Liste.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from who2be_api.services.placeholders.registry import (
    REGISTRY,
    DateResolver,
    PersonaFieldResolver,
    PlaybookResolver,
    RenderContext,
    ResolveResult,
    ResourceResolver,
    ToolsOverviewResolver,
)
from who2be_api.services.placeholders.renderer import render_template_body

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ctx(
    persona_id: UUID | None = None,
    now: datetime | None = None,
) -> RenderContext:
    return RenderContext(
        workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
        persona_id=persona_id or UUID("00000000-0000-0000-0000-000000000001"),
        now=now or datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
    )


def _make_db(fetchrow_return: Any = None) -> MagicMock:
    """Erstellt einen Fake asyncpg.Connection-Mock."""
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=fetchrow_return)
    return db


def _async_run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# PlaybookResolver
# ---------------------------------------------------------------------------


class TestPlaybookResolver:
    def test_resolves_playbook_content(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Reset-Mail",
                "content": {"description": "Kurzbeschreibung", "body": "Schritte: 1, 2, 3"},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert isinstance(result, ResolveResult)
        assert "### Reset-Mail" in result.text
        assert "Kurzbeschreibung" in result.text
        assert "Schritte" in result.text
        assert result.unresolved_key is None

    def test_not_found_returns_error_string_and_miss_key(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        db = _make_db(None)
        target = str(uuid4())

        result = _async_run(resolver.resolve(target, ctx, db))

        assert result.text == "<Playbook nicht verfuegbar>"
        assert result.unresolved_key == f"playbook:{target}"

    def test_invalid_uuid_returns_error_string_and_miss_key(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("keine-uuid", ctx, db))

        assert result.text == "<Playbook nicht verfuegbar>"
        assert result.unresolved_key == "playbook:keine-uuid"
        # DB wurde nicht aufgerufen (frueh abgebrochen).
        db.fetchrow.assert_not_called()

    def test_empty_description_and_body(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Leer",
                "content": {"description": "", "body": ""},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert result.text == "### Leer"
        assert result.unresolved_key is None


# ---------------------------------------------------------------------------
# ResourceResolver
# ---------------------------------------------------------------------------


class TestResourceResolver:
    def test_resolves_resource_content_with_blocks(self) -> None:
        resolver = ResourceResolver()
        ctx = _ctx()
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "props": {},
                "content": [{"type": "text", "text": "Erster Abschnitt.", "styles": {}}],
                "children": [],
            }
        ]
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Handbuch",
                "content": {"blocks": blocks},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert isinstance(result, ResolveResult)
        assert "#### Handbuch" in result.text
        assert "Erster Abschnitt." in result.text
        assert result.unresolved_key is None

    def test_not_found_returns_error_string_and_miss_key(self) -> None:
        resolver = ResourceResolver()
        ctx = _ctx()
        db = _make_db(None)
        target = str(uuid4())

        result = _async_run(resolver.resolve(target, ctx, db))

        assert result.text == "<Resource nicht verfuegbar>"
        assert result.unresolved_key == f"resource:{target}"

    def test_invalid_uuid_returns_error_string_and_miss_key(self) -> None:
        resolver = ResourceResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("keine-uuid", ctx, db))

        assert result.text == "<Resource nicht verfuegbar>"
        assert result.unresolved_key == "resource:keine-uuid"
        db.fetchrow.assert_not_called()


# ---------------------------------------------------------------------------
# PersonaFieldResolver
# ---------------------------------------------------------------------------


class TestPersonaFieldResolver:
    def test_resolves_name(self) -> None:
        resolver = PersonaFieldResolver()
        persona_id = uuid4()
        ctx = _ctx(persona_id=persona_id)
        row = MagicMock()
        row.__getitem__ = MagicMock(return_value="Coach Carla")
        db = _make_db(row)

        result = _async_run(resolver.resolve("name", ctx, db))

        assert isinstance(result, ResolveResult)
        assert result.text == "Coach Carla"
        assert result.unresolved_key is None

    def test_resolves_description(self) -> None:
        resolver = PersonaFieldResolver()
        persona_id = uuid4()
        ctx = _ctx(persona_id=persona_id)
        row = MagicMock()
        _content = {"description": "Senior Coach", "system_prompt": ""}
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("description", ctx, db))

        assert result.text == "Senior Coach"
        assert result.unresolved_key is None

    def test_none_persona_id_returns_miss(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        db = _make_db()

        result = _async_run(resolver.resolve("name", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-field:name"
        db.fetchrow.assert_not_called()

    def test_unknown_field_returns_miss(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("unknown_field", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-field:unknown_field"
        db.fetchrow.assert_not_called()

    def test_persona_not_found_returns_miss(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(None)

        result = _async_run(resolver.resolve("name", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-field:name"


# ---------------------------------------------------------------------------
# DateResolver
# ---------------------------------------------------------------------------


class TestDateResolver:
    def test_empty_slug_returns_iso_date(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("", ctx, db))

        assert isinstance(result, ResolveResult)
        assert result.text == "2026-05-31"
        assert result.unresolved_key is None

    def test_human_slug_returns_german_date(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result.text == "31. Mai 2026"
        assert result.unresolved_key is None

    def test_human_slug_january(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 1, 1, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result.text == "1. Januar 2026"

    def test_human_slug_december(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 12, 25, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result.text == "25. Dezember 2026"

    def test_unknown_slug_returns_iso_date_never_miss(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 3, 15, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("invalid-slug", ctx, db))

        # Fallback auf ISO; nie Miss.
        assert result.text == "2026-03-15"
        assert result.unresolved_key is None


class TestToolsOverviewResolver:
    """Welle 5/6: statische MCP-Tool-Liste, nie Miss."""

    def test_returns_markdown_with_header(self) -> None:
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db))
        assert isinstance(result, ResolveResult)
        assert result.text.startswith("## Verfuegbare Werkzeuge")
        assert result.unresolved_key is None

    def test_lists_all_known_tool_signatures(self) -> None:
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db))
        for expected in (
            "get_persona(identifier)",
            "list_triggers()",
            "list_playbooks(tag?, trigger?)",
            "fetch_playbook(playbook_id)",
            "list_resources()",
            "fetch_resource(resource_id, block_ids?)",
        ):
            assert expected in result.text

    def test_registered_in_registry_under_tools_overview_key(self) -> None:
        assert "tools-overview" in REGISTRY
        ctx = _ctx()
        db = _make_db()
        result = _async_run(REGISTRY["tools-overview"].resolve("", ctx, db))
        assert "Verfuegbare Werkzeuge" in result.text


# ---------------------------------------------------------------------------
# render_template_body (Renderer-Integration) — Welle 6: tuple return
# ---------------------------------------------------------------------------


class TestRenderTemplateBody:
    """Tests fuer den Renderer selbst (ohne echte DB).

    `render_template_body` gibt jetzt `tuple[str, list[str]]` zurueck.
    Index 0 = gerenderter Text, Index 1 = unresolved-Keys.
    """

    def _blocknote_doc_array(self, *inline_items: dict[str, Any]) -> str:
        """Top-Level-Array-Variante — wie `editor.document` sie liefert."""
        return json.dumps(
            [
                {
                    "id": "p1",
                    "type": "paragraph",
                    "props": {},
                    "content": list(inline_items),
                    "children": [],
                }
            ]
        )

    def _blocknote_doc(self, *inline_items: dict[str, Any]) -> str:
        """Erzeugt ein minimales BlockNote-JSON-Dokument mit einem Paragraph."""
        return json.dumps(
            {
                "content": [
                    {
                        "id": "p1",
                        "type": "paragraph",
                        "props": {},
                        "content": list(inline_items),
                        "children": [],
                    }
                ]
            }
        )

    def test_plain_format_returned_as_is_with_empty_unresolved(self) -> None:
        db = _make_db()
        ctx = _ctx()
        body = "Hallo {{ persona.name }}"

        text, unresolved = _async_run(render_template_body(body, "plain", ctx, db))

        assert text == body
        assert unresolved == []

    def test_blocknote_text_inline(self) -> None:
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc({"type": "text", "text": "Hallo Welt", "styles": {}})

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Hallo Welt" in text
        assert unresolved == []

    def test_blocknote_top_level_array_shape(self) -> None:
        """Frontend serialisiert `editor.document` als reines Array — Renderer
        muss das ebenso akzeptieren wie das `{content: [...]}`-Wrapper-Format."""
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc_array({"type": "text", "text": "Top-Array", "styles": {}})

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Top-Array" in text
        assert unresolved == []

    def test_blocknote_top_level_array_with_placeholder(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc_array(
            {"type": "text", "text": "Heute: ", "styles": {}},
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}},
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert text.strip() == "Heute: 2026-05-31"
        assert unresolved == []

    def test_blocknote_date_placeholder_iso(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}}
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "2026-05-31" in text
        assert unresolved == []

    def test_blocknote_date_placeholder_human(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "date", "target_id": "human", "label": "Datum"},
            }
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "31. Mai 2026" in text
        assert unresolved == []

    def test_blocknote_unknown_kind_returns_error_string(self) -> None:
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "unknown-kind", "target_id": "", "label": "?"},
            }
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "unknown-kind" in text
        # Unbekanntes Kind landet NICHT in unresolved (kein Resolver vorhanden).
        assert unresolved == []

    def test_invalid_json_returned_as_is_with_empty_unresolved(self) -> None:
        db = _make_db()
        ctx = _ctx()
        bad_body = "{not valid json"

        text, unresolved = _async_run(render_template_body(bad_body, "blocknote", ctx, db))

        assert text == bad_body
        assert unresolved == []

    def test_mixed_text_and_placeholder(self) -> None:
        """Prefix-Text + Placeholder + Suffix-Text werden korrekt konkateniert."""
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {"type": "text", "text": "Heute ist der ", "styles": {}},
            {
                "type": "placeholder",
                "props": {"kind": "date", "target_id": "human", "label": "Datum"},
            },
            {"type": "text", "text": ".", "styles": {}},
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Heute ist der 31. Mai 2026." in text
        assert unresolved == []

    # -----------------------------------------------------------------------
    # Welle 6: unresolved-Tracking Tests
    # -----------------------------------------------------------------------

    def test_invalid_playbook_uuid_tracked_in_unresolved(self) -> None:
        """Ungueltige Playbook-UUID -> unresolved enthaelt 'playbook:keine-uuid'."""
        db = _make_db(None)  # DB liefert immer None (nicht gefunden)
        ctx = _ctx()
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {
                    "kind": "playbook",
                    "target_id": "keine-uuid",
                    "label": "Playbook: ?",
                },
            }
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert text == "<Playbook nicht verfuegbar>"
        assert unresolved == ["playbook:keine-uuid"]

    def test_missing_playbook_uuid_tracked_in_unresolved(self) -> None:
        """Gueltiger UUID, aber Playbook nicht gefunden -> Miss."""
        db = _make_db(None)
        ctx = _ctx()
        target = str(uuid4())
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "playbook", "target_id": target, "label": "Playbook"},
            }
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert text == "<Playbook nicht verfuegbar>"
        assert unresolved == [f"playbook:{target}"]

    def test_persona_field_with_none_persona_id_tracked(self) -> None:
        """persona_id=None -> persona-field:name in unresolved."""
        db = _make_db()
        ctx = RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {
                    "kind": "persona-field",
                    "target_id": "name",
                    "label": "Persona: Name",
                },
            }
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert text == ""
        assert unresolved == ["persona-field:name"]

    def test_three_pills_one_valid_two_misses(self) -> None:
        """BlockNote-Doc mit 3 Pills:
        - valider Playbook (DB liefert Daten) -> kein Miss
        - invalide Playbook-UUID -> Miss 'playbook:keine-uuid'
        - persona-field:name mit persona_id=None -> Miss 'persona-field:name'

        Plain-Text enthaelt den Playbook-Inhalt + Fallback-Strings.
        unresolved-Liste enthaelt genau 2 Keys, lexikografisch sortiert.
        """
        valid_uuid = str(uuid4())

        # fetchrow: erstes call liefert Playbook-Daten (gueltiger UUID),
        # zweiter call: nicht-existente UUID -> None (schon im Mock via side_effect).
        row_mock = MagicMock()
        row_mock.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Begruessung",
                "content": {"description": "Freundlich", "body": "Hallo!"},
            }[k]
        )
        db = MagicMock()
        db.fetchrow = AsyncMock(side_effect=[row_mock, None])

        ctx = RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=None,  # -> Miss fuer persona-field
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )

        doc = json.dumps(
            [
                {
                    "id": "b1",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "playbook",
                                "target_id": valid_uuid,
                                "label": "Playbook 1",
                            },
                        }
                    ],
                    "children": [],
                },
                {
                    "id": "b2",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "playbook",
                                "target_id": "keine-uuid",
                                "label": "Playbook 2",
                            },
                        }
                    ],
                    "children": [],
                },
                {
                    "id": "b3",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "persona-field",
                                "target_id": "name",
                                "label": "Persona: Name",
                            },
                        }
                    ],
                    "children": [],
                },
            ]
        )

        text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        # Valider Playbook muss im Text erscheinen.
        assert "Begruessung" in text
        assert "Hallo!" in text
        # Miss-Fallbacks muessen im Text erscheinen.
        assert "<Playbook nicht verfuegbar>" in text
        # persona-field:None -> leerer String -> kein sichtbarer Text, aber Miss.
        # Zwei Misses im unresolved, lexikografisch sortiert.
        assert unresolved == ["persona-field:name", "playbook:keine-uuid"]

    def test_duplicate_misses_deduplicated(self) -> None:
        """Gleiches Miss-Target mehrfach -> nur einmal in unresolved."""
        db = _make_db(None)
        ctx = _ctx()
        target = "keine-uuid"
        doc = json.dumps(
            [
                {
                    "id": "b1",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "playbook",
                                "target_id": target,
                                "label": "PB 1",
                            },
                        }
                    ],
                    "children": [],
                },
                {
                    "id": "b2",
                    "type": "paragraph",
                    "props": {},
                    "content": [
                        {
                            "type": "placeholder",
                            "props": {
                                "kind": "playbook",
                                "target_id": target,
                                "label": "PB 2 (duplikat)",
                            },
                        }
                    ],
                    "children": [],
                },
            ]
        )

        _text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        # Nur einmal in der Liste.
        assert unresolved == [f"playbook:{target}"]

    def test_date_and_tools_overview_never_in_unresolved(self) -> None:
        """date + tools-overview erzeugen nie Miss-Keys."""
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "date", "target_id": "human", "label": "Datum"},
            },
        )

        _text, unresolved = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert unresolved == []
