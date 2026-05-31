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
    REGISTRY,
    DateResolver,
    PersonaFieldResolver,
    PlaybookResolver,
    RenderContext,
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


def _make_db(fetchrow_return: Any = None, fetch_return: Any = None) -> MagicMock:
    """Erstellt einen Fake asyncpg.Connection-Mock.

    `fetchrow_return` — Rueckgabewert fuer `db.fetchrow(...)`.
    `fetch_return`    — Rueckgabewert fuer `db.fetch(...)` (Default: leere Liste,
                        damit der Composite-Zweig des PlaybookResolvers korrekt
                        „kein Kind → Atomic" meldet).
    """
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=fetchrow_return)
    db.fetch = AsyncMock(return_value=fetch_return if fetch_return is not None else [])
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

    # --- Composite-aware (B1) ---

    def _make_child_row(self, name: str, description: str, body: str) -> MagicMock:
        """Erstellt einen Fake-Child-Row-Mock fuer `db.fetch`."""
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "child_name": name,
                "child_content": {"description": description, "body": body},
            }[k]
        )
        return row

    def test_composite_pill_includes_composite_body_and_children_in_order(self) -> None:
        """Pill auf Composite → Output enthaelt Composite-Body + Kinder in position-Reihenfolge."""
        resolver = PlaybookResolver()
        ctx = _ctx()
        parent_row = MagicMock()
        parent_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Onboarding",
                "content": {"description": "Gesamt-Onboarding", "body": "Bitte folgen."},
            }[k]
        )
        child_rows = [
            self._make_child_row("Schritt-1: Konto", "Konto anlegen", "Gehe zu Settings."),
            self._make_child_row("Schritt-2: Profil", "Profil ausfuellen", "Name eingeben."),
        ]
        db = _make_db(fetchrow_return=parent_row, fetch_return=child_rows)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert "### Onboarding" in result
        assert "Gesamt-Onboarding" in result
        assert "Bitte folgen." in result
        assert "## Ablauf (Sub-Playbooks)" in result
        # Kinder erscheinen nummeriert in Reihenfolge.
        assert "1." in result
        assert "2." in result
        assert result.index("Schritt-1: Konto") < result.index("Schritt-2: Profil")
        assert "Gehe zu Settings." in result
        assert "Name eingeben." in result

    def test_atomic_pill_returns_only_own_body(self) -> None:
        """Pill auf Atomic (keine Kinder) → nur eigener Body, keine Ablauf-Sektion."""
        resolver = PlaybookResolver()
        ctx = _ctx()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Reset-Mail",
                "content": {"description": "Passwort zuruecksetzen", "body": "Mail senden."},
            }[k]
        )
        db = _make_db(fetchrow_return=row, fetch_return=[])

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert "### Reset-Mail" in result
        assert "Passwort zuruecksetzen" in result
        assert "Mail senden." in result
        assert "## Ablauf (Sub-Playbooks)" not in result

    def test_composite_pill_skips_inactive_children(self) -> None:
        """Inaktive Kinder (kein active-Join-Match) werden uebersprungen — kein Hard-Fail."""
        resolver = PlaybookResolver()
        ctx = _ctx()
        parent_row = MagicMock()
        parent_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Composite",
                "content": {"description": "", "body": "Sequenz."},
            }[k]
        )
        # Nur ein aktives Kind geliefert (inaktives Kind fehlt im JOIN-Ergebnis).
        active_child = self._make_child_row("Aktiv-Schritt", "Nur aktiv", "Fertig.")
        db = _make_db(fetchrow_return=parent_row, fetch_return=[active_child])

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert "Aktiv-Schritt" in result
        assert "## Ablauf (Sub-Playbooks)" in result
        # Nur ein Kind → nur "1." vorhanden, kein "2."
        assert "1." in result
        lines_with_2 = [ln for ln in result.splitlines() if ln.strip().startswith("2.")]
        assert lines_with_2 == []


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

    # --- profile-Target (E1 + C4) ---

    def test_resolves_profile_with_description_and_blocks(self) -> None:
        """profile rendert description + BlockNote-Body."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "props": {},
                "content": [{"type": "text", "text": "Empathisch und praezise.", "styles": {}}],
                "children": [],
            }
        ]
        _content: dict[str, Any] = {
            "description": "Senior Coach",
            "content": {"description": "", "blocks": blocks},
            "traits": [],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert "Senior Coach" in result
        assert "Empathisch und praezise." in result

    def test_resolves_profile_with_modi_sektion(self) -> None:
        """profile enthaelt ## Modi-Sektion wenn modes vorhanden (C4)."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona mit Modi",
            "content": None,
            "traits": [],
            "modes": [
                {
                    "name": "Erklaerer",
                    "trigger": "erklaer,wie",
                    "is_default": False,
                    "identity_add": "Du bist ein Lehrer.",
                    "output_style_override": "Schreibe einfach.",
                },
                {
                    "name": "Standard",
                    "trigger": None,
                    "is_default": True,
                    "identity_add": "",
                    "output_style_override": "",
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert "## Modi" in result
        assert "### Erklaerer" in result
        assert "Trigger" in result
        assert "erklaer,wie" in result
        assert "Du bist ein Lehrer." in result
        assert "Schreibe einfach." in result
        assert "### Standard (Default)" in result

    def test_resolves_profile_without_modi_sektion_when_modes_empty(self) -> None:
        """profile enthaelt keine ## Modi-Sektion wenn modes leer."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Einfache Persona",
            "content": None,
            "traits": [],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert "Einfache Persona" in result
        assert "## Modi" not in result

    def test_resolves_profile_with_empty_body_returns_description_only(self) -> None:
        """profile mit leerem Body gibt nur description zurueck."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Nur Beschreibung",
            "content": {"description": "", "blocks": []},
            "traits": [],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert result.strip() == "Nur Beschreibung"

    def test_resolves_profile_empty_description_and_body_returns_empty_string(self) -> None:
        """profile mit leerer description und leerem Body gibt leeren String zurueck."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "",
            "content": {"description": "", "blocks": []},
            "traits": [],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert result == ""

    def test_resolves_profile_with_traits(self) -> None:
        """profile rendert Traits-Liste (deprecated aber lesbar)."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona mit Traits",
            "content": None,
            "traits": ["praezise", "empathisch"],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db))

        assert "praezise" in result
        assert "empathisch" in result
        assert "Traits" in result


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


class TestToolsOverviewResolver:
    """Welle 5: statische MCP-Tool-Liste."""

    def test_returns_markdown_with_header(self) -> None:
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db))
        assert result.startswith("## Verfuegbare Werkzeuge")

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
            "list_resources(tag?)",
            "fetch_resource(resource_id, block_ids?)",
        ):
            assert expected in result

    def test_registered_in_registry_under_tools_overview_key(self) -> None:
        assert "tools-overview" in REGISTRY
        # Sicherstellen, dass der Renderer das Kind ueber dieselbe Map findet.
        ctx = _ctx()
        db = _make_db()
        result = _async_run(REGISTRY["tools-overview"].resolve("", ctx, db))
        assert "Verfuegbare Werkzeuge" in result


# ---------------------------------------------------------------------------
# render_template_body (Renderer-Integration)
# ---------------------------------------------------------------------------


class TestRenderTemplateBody:
    """Tests fuer den Renderer selbst (ohne echte DB)."""

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

    def test_blocknote_top_level_array_shape(self) -> None:
        """Frontend serialisiert `editor.document` als reines Array — siehe
        SystemPromptEditorForm.handleBlockNoteChange. Renderer muss das
        ebenso akzeptieren wie das `{content: [...]}`-Wrapper-Format."""
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc_array({"type": "text", "text": "Top-Array", "styles": {}})

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert "Top-Array" in result

    def test_blocknote_top_level_array_with_placeholder(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc_array(
            {"type": "text", "text": "Heute: ", "styles": {}},
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}},
        )

        result = _async_run(render_template_body(doc, "blocknote", ctx, db))

        assert result.strip() == "Heute: 2026-05-31"

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
