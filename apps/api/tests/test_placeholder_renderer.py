"""Unit-Tests fuer den Placeholder-Renderer und alle vier Resolver.

Kein DB-Zugriff in den Unit-Tests — wir mocken `asyncpg.Connection` mit
einem einfachen Fake, der `fetchrow` implementiert. Der Integrations-Pfad
gegen echte DB laeuft in `test_fetch_agent_endpoint.py`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from who2be_api.services.placeholders.registry import (
    DateResolver,
    PersonaFieldResolver,
    PlaybookResolver,
    RenderContext,
    ResourceResolver,
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

        assert "### Reset-Mail" in result
        assert "Kurzbeschreibung" in result
        assert "Schritte" in result

    def test_not_found_returns_error_string(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        db = _make_db(None)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert result == "<Playbook nicht verfuegbar>"

    def test_invalid_uuid_returns_error_string(self) -> None:
        resolver = PlaybookResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("keine-uuid", ctx, db))

        assert result == "<Playbook nicht verfuegbar>"
        # DB wurde nicht aufgerufen (früh abgebrochen).
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

        assert result == "### Leer"


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

        assert "#### Handbuch" in result
        assert "Erster Abschnitt." in result

    def test_not_found_returns_error_string(self) -> None:
        resolver = ResourceResolver()
        ctx = _ctx()
        db = _make_db(None)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert result == "<Resource nicht verfuegbar>"

    def test_invalid_uuid_returns_error_string(self) -> None:
        resolver = ResourceResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("keine-uuid", ctx, db))

        assert result == "<Resource nicht verfuegbar>"
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

        assert result == "Coach Carla"

    def test_resolves_description(self) -> None:
        resolver = PersonaFieldResolver()
        persona_id = uuid4()
        ctx = _ctx(persona_id=persona_id)
        row = MagicMock()
        _content = {"description": "Senior Coach", "system_prompt": ""}
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("description", ctx, db))

        assert result == "Senior Coach"

    def test_none_persona_id_returns_empty_string(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        db = _make_db()

        result = _async_run(resolver.resolve("name", ctx, db))

        assert result == ""
        db.fetchrow.assert_not_called()

    def test_unknown_field_returns_empty_string(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("unknown_field", ctx, db))

        assert result == ""
        db.fetchrow.assert_not_called()

    def test_persona_not_found_returns_empty_string(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(None)

        result = _async_run(resolver.resolve("name", ctx, db))

        assert result == ""


# ---------------------------------------------------------------------------
# DateResolver
# ---------------------------------------------------------------------------


class TestDateResolver:
    def test_empty_slug_returns_iso_date(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("", ctx, db))

        assert result == "2026-05-31"

    def test_human_slug_returns_german_date(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result == "31. Mai 2026"

    def test_human_slug_january(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 1, 1, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result == "1. Januar 2026"

    def test_human_slug_december(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 12, 25, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("human", ctx, db))

        assert result == "25. Dezember 2026"

    def test_unknown_slug_returns_iso_date(self) -> None:
        resolver = DateResolver()
        ctx = _ctx(now=datetime(2026, 3, 15, tzinfo=UTC))
        db = _make_db()

        result = _async_run(resolver.resolve("invalid-slug", ctx, db))

        # Fallback auf ISO.
        assert result == "2026-03-15"


# ---------------------------------------------------------------------------
# render_template_body (Renderer-Integration)
# ---------------------------------------------------------------------------


class TestRenderTemplateBody:
    """Tests fuer den Renderer selbst (ohne echte DB)."""

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

    def test_plain_format_returned_as_is(self) -> None:
        db = _make_db()
        ctx = _ctx()
        body = "Hallo {{ persona.name }}"

        result = _async_run(render_template_body(body, "plain", ctx, db))

        assert result == body

    def test_blocknote_text_inline(self) -> None:
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc({"type": "text", "text": "Hallo Welt", "styles": {}})

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Hallo Welt" in result

    def test_blocknote_date_placeholder_iso(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}}
        )

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "2026-05-31" in result

    def test_blocknote_date_placeholder_human(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "date", "target_id": "human", "label": "Datum"},
            }
        )

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "31. Mai 2026" in result

    def test_blocknote_unknown_kind_returns_error_string(self) -> None:
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc(
            {
                "type": "placeholder",
                "props": {"kind": "unknown-kind", "target_id": "", "label": "?"},
            }
        )

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "unknown-kind" in result

    def test_invalid_json_returned_as_is(self) -> None:
        db = _make_db()
        ctx = _ctx()
        bad_body = "{not valid json"

        result = _async_run(render_template_body(bad_body, "blocknote", ctx, db))

        assert result == bad_body

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

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Heute ist der 31. Mai 2026." in result
