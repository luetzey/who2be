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

import pytest

from who2be_api.services.placeholders.registry import (
    REGISTRY,
    DateResolver,
    PersonaFieldResolver,
    PersonaRefResolver,
    PlaybookResolver,
    PlaybooksCatalogResolver,
    RenderContext,
    ResolveResult,
    ResourceResolver,
    ResourcesCatalogResolver,
    ToolRefResolver,
    ToolsOverviewResolver,
    render_skills_table,
)
from who2be_api.services.placeholders.renderer import render_template_body

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _blk(block_id: str, text: str) -> dict[str, Any]:
    """Baut einen minimalen BlockNote-Paragraph-Block (ResourceBlock-Form)."""
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


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

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db)).text

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

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db)).text

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

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db)).text

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

    # --- Block-Anker (B2) ---

    def _heading(self, block_id: str, text: str, level: int = 1) -> dict[str, Any]:
        """Baut einen BlockNote-Heading-Block mit `props.level`."""
        return {
            "id": block_id,
            "type": "heading",
            "props": {"level": level},
            "content": [{"type": "text", "text": text, "styles": {}}],
            "children": [],
        }

    def _section_blocks(self) -> list[dict[str, Any]]:
        """Zwei Sections auf demselben Heading-Level (h1) mit je einem Absatz."""
        return [
            self._heading("h1", "Einleitung", level=1),
            _blk("p1", "Intro-Absatz."),
            self._heading("h2", "Details", level=1),
            _blk("p2", "Detail-Absatz."),
        ]

    def test_resource_pill_without_block_renders_whole_resource(self) -> None:
        """Pure UUID (kein '#') → ganze Resource, beide Sections im Output."""
        resolver = ResourceResolver()
        ctx = _ctx()
        blocks = self._section_blocks()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Handbuch",
                "content": {"blocks": blocks},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(str(uuid4()), ctx, db))

        assert "#### Handbuch" in result.text
        assert "Einleitung" in result.text
        assert "Intro-Absatz." in result.text
        assert "Details" in result.text
        assert "Detail-Absatz." in result.text
        assert result.unresolved_key is None

    def test_resource_pill_with_block_anchor_renders_only_section(self) -> None:
        """`<uuid>#<heading_block_id>` → nur die Section ab dem Anker-Heading."""
        resolver = ResourceResolver()
        ctx = _ctx()
        blocks = self._section_blocks()
        rid = uuid4()
        target = f"{rid}#h1"
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Handbuch",
                "content": {"blocks": blocks},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(target, ctx, db))

        assert "#### Handbuch" in result.text
        # Erste Section (Anker h1) ist drin.
        assert "Einleitung" in result.text
        assert "Intro-Absatz." in result.text
        # Zweite Section (h2, gleiches Level) ist abgeschnitten.
        assert "Details" not in result.text
        assert "Detail-Absatz." not in result.text
        assert result.unresolved_key is None

    def test_resource_pill_with_unknown_block_anchor_is_miss(self) -> None:
        """Nicht existierender block_id → leerer Body + Miss-Key (mit Anker-Suffix)."""
        resolver = ResourceResolver()
        ctx = _ctx()
        blocks = self._section_blocks()
        rid = uuid4()
        target = f"{rid}#does-not-exist"
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Handbuch",
                "content": {"blocks": blocks},
            }[k]
        )
        db = _make_db(row)

        result = _async_run(resolver.resolve(target, ctx, db))

        assert result.text == ""
        assert result.unresolved_key == f"resource:{target}"


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

        result = _async_run(resolver.resolve("profile", ctx, db)).text

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
                    "identity_add": [_blk("ia1", "Du bist ein Lehrer.")],
                    "output_style_override": [_blk("os1", "Schreibe einfach.")],
                },
                {
                    "name": "Standard",
                    "trigger": None,
                    "is_default": True,
                    "identity_add": [],
                    "output_style_override": [],
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "## Modi" in result
        assert "### Erklaerer" in result
        assert "Trigger" in result
        assert "erklaer,wie" in result
        assert "Du bist ein Lehrer." in result
        assert "Schreibe einfach." in result
        assert "### Standard (Default)" in result

    def test_resolves_profile_mode_blocks_rendered_multiline(self) -> None:
        """Block-Listen in identity_add/output_style_override werden per Block gerendert."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [
                {
                    "name": "Multi",
                    "trigger": None,
                    "is_default": True,
                    "identity_add": [_blk("a", "Zeile eins."), _blk("b", "Zeile zwei.")],
                    "output_style_override": [_blk("c", "Kurz.")],
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "**Identity-Ergaenzung:** Zeile eins.\n\nZeile zwei." in result
        assert "**Output-Stil:** Kurz." in result

    def test_resolves_profile_mode_empty_block_lists_no_lines(self) -> None:
        """Leere Block-Listen erzeugen keine Identity-/Output-/Anti-Pattern-Zeilen."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [
                {
                    "name": "Leer",
                    "trigger": None,
                    "is_default": True,
                    "identity_add": [],
                    "output_style_override": [],
                    "anti_patterns": [],
                    "playbook_name": "",
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "### Leer (Default)" in result
        assert "Identity-Ergaenzung" not in result
        assert "Output-Stil" not in result
        assert "Anti-Patterns" not in result
        assert "Zugehoeriges Playbook" not in result

    def test_resolves_profile_mode_anti_patterns_and_playbook_name(self) -> None:
        """Anti-Patterns (Block-Liste) und playbook_name (str) werden gerendert."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [
                {
                    "name": "Mit-Extras",
                    "trigger": None,
                    "is_default": True,
                    "identity_add": [],
                    "output_style_override": [],
                    "anti_patterns": [_blk("ap1", "Niemals raten.")],
                    "playbook_name": "Coding-Playbook",
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "**Anti-Patterns:** Niemals raten." in result
        assert "**Zugehoeriges Playbook:** Coding-Playbook" in result

    def test_resolves_profile_skills_section(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """## Skills-Sektion wird gerendert, note nur wenn vorhanden (Flag aktiv)."""
        # Skills sind Coming Soon (ADR-0026) — fuer den Render-Test lokal aktiv.
        monkeypatch.setattr("who2be_api.services.placeholders._core.SKILLS_ENABLED", True)
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [],
            "skills": [
                {"name": "Python", "note": "fortgeschritten"},
                {"name": "Refactoring", "note": ""},
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "## Skills" in result
        assert "- Python: fortgeschritten" in result
        assert "- Refactoring" in result
        assert "- Refactoring:" not in result

    def test_resolves_profile_no_skills_section_when_disabled(self) -> None:
        """Coming Soon (ADR-0026): keine ## Skills-Sektion, auch wenn skills da sind."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [],
            "skills": [{"name": "Python", "note": "fortgeschritten"}],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "## Skills" not in result

    def test_resolves_profile_no_skills_section_when_empty(self) -> None:
        """Keine ## Skills-Sektion wenn skills leer/fehlt."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [],
            "skills": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "## Skills" not in result

    def test_resolves_profile_mode_str_coercion_via_model_validate(self) -> None:
        """Alt-str in identity_add wird via PersonaMode.model_validate zu Block-Liste."""
        from who2be_models.persona import PersonaMode

        mode = PersonaMode.model_validate(
            {
                "name": "Legacy",
                "is_default": True,
                "identity_add": "Alt-Text identity.",
                "output_style_override": "Alt-Text style.",
            }
        )
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona",
            "content": None,
            "traits": [],
            "modes": [mode.model_dump(mode="json")],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "**Identity-Ergaenzung:** Alt-Text identity." in result
        assert "**Output-Stil:** Alt-Text style." in result

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

        result = _async_run(resolver.resolve("profile", ctx, db)).text

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

        result = _async_run(resolver.resolve("profile", ctx, db)).text

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

        result = _async_run(resolver.resolve("profile", ctx, db)).text

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

        result = _async_run(resolver.resolve("profile", ctx, db)).text

        assert "praezise" in result
        assert "empathisch" in result
        assert "Traits" in result

    def test_resolves_modes_only_section(self) -> None:
        """target_id='modes' rendert nur die ## Modi-Sektion."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Soll NICHT im Modes-Output erscheinen",
            "content": {"description": "", "blocks": [_blk("b1", "Profil-Body")]},
            "traits": [],
            "modes": [
                {
                    "name": "Erklaerer",
                    "trigger": "erklaer",
                    "is_default": False,
                    "identity_add": [_blk("ia1", "Du bist ein Lehrer.")],
                    "output_style_override": [],
                },
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("modes", ctx, db))

        assert result.unresolved_key is None
        assert "## Modi" in result.text
        assert "### Erklaerer" in result.text
        assert "Du bist ein Lehrer." in result.text
        # Profil-Body / Beschreibung gehoeren NICHT in den Modes-only-Output.
        assert "Profil-Body" not in result.text
        assert "Soll NICHT" not in result.text

    def test_resolves_modes_empty_returns_empty_string_no_miss(self) -> None:
        """Ohne Modi liefert 'modes' einen leeren String — kein Miss."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Persona ohne Modi",
            "content": {"description": "", "blocks": []},
            "traits": [],
            "modes": [],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("modes", ctx, db))

        assert result.text == ""
        assert result.unresolved_key is None

    def test_modes_none_persona_id_returns_miss(self) -> None:
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=None)
        ctx = RenderContext(workspace_id=ctx.workspace_id, persona_id=None, now=ctx.now)
        db = _make_db()

        result = _async_run(resolver.resolve("modes", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-field:modes"

    def test_resolves_profile_body_only(self) -> None:
        """target_id='profile-body' rendert nur den BlockNote-Body."""
        resolver = PersonaFieldResolver()
        ctx = _ctx(persona_id=uuid4())
        _content: dict[str, Any] = {
            "description": "Beschreibung NICHT im Body",
            "content": {
                "description": "",
                "blocks": [_blk("b1", "Profil-Body Zeile 1"), _blk("b2", "Profil-Body Zeile 2")],
            },
            "traits": ["trait-x"],
            "modes": [
                {"name": "M", "trigger": None, "is_default": True},
            ],
        }
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"content": _content}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("profile-body", ctx, db))

        assert result.unresolved_key is None
        assert "Profil-Body Zeile 1" in result.text
        assert "Profil-Body Zeile 2" in result.text
        # Beschreibung, Traits, Modi gehoeren NICHT in den Body-only-Output.
        assert "Beschreibung NICHT" not in result.text
        assert "trait-x" not in result.text
        assert "## Modi" not in result.text

    def test_resolves_profile_body_empty_returns_empty_string(self) -> None:
        """Ohne Profil-Body liefert 'profile-body' einen leeren String (kein Miss)."""
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

        result = _async_run(resolver.resolve("profile-body", ctx, db))

        assert result.text == ""
        assert result.unresolved_key is None


# ---------------------------------------------------------------------------
# PersonaRefResolver
# ---------------------------------------------------------------------------


class TestPersonaRefResolver:
    def test_renders_load_instruction_with_id_and_name(self) -> None:
        resolver = PersonaRefResolver()
        persona_id = uuid4()
        ctx = _ctx(persona_id=persona_id)
        row = MagicMock()
        row.__getitem__ = MagicMock(side_effect=lambda k: {"name": "Lena Support"}[k])
        db = _make_db(row)

        result = _async_run(resolver.resolve("", ctx, db))

        assert result.unresolved_key is None
        assert "Lena Support" in result.text
        assert str(persona_id) in result.text
        assert "get_persona" in result.text
        assert "content.modes" in result.text
        # WP-F: Hinweis auf den serverseitig angewendeten Modus-Parameter.
        assert 'mode="<Modus-Name>"' in result.text

    def test_none_persona_id_returns_miss(self) -> None:
        resolver = PersonaRefResolver()
        ctx = RenderContext(
            workspace_id=uuid4(),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        db = _make_db()

        result = _async_run(resolver.resolve("", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-ref:"

    def test_persona_not_found_returns_miss(self) -> None:
        resolver = PersonaRefResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(None)

        result = _async_run(resolver.resolve("", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "persona-ref:"


# ---------------------------------------------------------------------------
# PlaybooksCatalogResolver
# ---------------------------------------------------------------------------


def _catalog_row(name: str, triggers: str | None, description: str) -> MagicMock:
    row = MagicMock()
    data = {
        "id": uuid4(),
        "name": name,
        "triggers": triggers,
        "content": {"description": description, "body": "egal"},
    }
    row.__getitem__ = MagicMock(side_effect=lambda k: data[k])
    return row


class TestPlaybooksCatalogResolver:
    def test_renders_table_for_all_linked(self) -> None:
        resolver = PlaybooksCatalogResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(
            fetch_return=[
                _catalog_row("Reset-Mail", "passwort, reset", "Setzt das Passwort zurueck."),
                _catalog_row("Smalltalk", None, "Lockerer Einstieg."),
            ]
        )

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.unresolved_key is None
        assert "## Deine Playbooks" in result.text
        assert "| Playbook | Trigger | Aufruf | Beschreibung |" in result.text
        assert "Reset-Mail" in result.text
        assert "passwort, reset" in result.text
        assert "fetch_playbook(" in result.text
        # Ohne Filter erscheint auch das trigger-lose Playbook.
        assert "Smalltalk" in result.text

    def test_triggered_filter_excludes_triggerless(self) -> None:
        resolver = PlaybooksCatalogResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(
            fetch_return=[
                _catalog_row("Reset-Mail", "passwort", "Setzt zurueck."),
                _catalog_row("Smalltalk", "  ", "Lockerer Einstieg."),
            ]
        )

        result = _async_run(resolver.resolve("triggered", ctx, db))

        assert "Reset-Mail" in result.text
        assert "Smalltalk" not in result.text

    def test_empty_catalog_returns_hint_no_miss(self) -> None:
        resolver = PlaybooksCatalogResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(fetch_return=[])

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.unresolved_key is None
        assert "keine Playbooks" in result.text

    def test_pipe_in_name_is_escaped(self) -> None:
        resolver = PlaybooksCatalogResolver()
        ctx = _ctx(persona_id=uuid4())
        db = _make_db(fetch_return=[_catalog_row("A|B", "t", "desc")])

        result = _async_run(resolver.resolve("all", ctx, db))

        assert "A\\|B" in result.text

    def test_none_persona_id_returns_miss(self) -> None:
        resolver = PlaybooksCatalogResolver()
        ctx = RenderContext(
            workspace_id=uuid4(),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        db = _make_db()

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.text == ""
        assert result.unresolved_key == "playbooks-catalog:all"


# ---------------------------------------------------------------------------
# ResourcesCatalogResolver
# ---------------------------------------------------------------------------


def _resource_catalog_row(name: str, tags: list[str], description: str) -> MagicMock:
    row = MagicMock()
    data = {
        "id": uuid4(),
        "name": name,
        "content": {"description": description, "tags": tags},
    }
    row.__getitem__ = MagicMock(side_effect=lambda k: data[k])
    return row


class TestResourcesCatalogResolver:
    def test_renders_table_for_all_active(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(
            fetch_return=[
                _resource_catalog_row("Tarifwerk", ["billing", "preise"], "Aktuelle Tarife."),
                _resource_catalog_row("Tonalitaet", [], "Wie wir schreiben."),
            ]
        )

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.unresolved_key is None
        assert "## Verfuegbare Resources" in result.text
        assert "| Resource | Tags | Aufruf | Beschreibung |" in result.text
        assert "Tarifwerk" in result.text
        assert "billing, preise" in result.text
        assert "fetch_resource(" in result.text
        assert "Tonalitaet" in result.text

    def test_empty_target_id_behaves_like_all(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(fetch_return=[_resource_catalog_row("R", ["t"], "desc")])

        _async_run(resolver.resolve("", ctx, db))

        # Bei "all"/"" wird der Tag-Filter als NULL ($2) durchgereicht.
        # Positional-Args: (sql, workspace_id, tag_filter)
        positional = db.fetch.call_args[0]
        assert positional[2] is None

    def test_tag_filter_is_passed_through(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(fetch_return=[_resource_catalog_row("R", ["billing"], "desc")])

        _async_run(resolver.resolve("billing", ctx, db))

        positional = db.fetch.call_args[0]
        assert positional[2] == "billing"

    def test_empty_catalog_returns_hint_no_miss(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(fetch_return=[])

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.unresolved_key is None
        assert "keine aktiven Resources" in result.text

    def test_empty_tag_filtered_catalog_mentions_tag(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(fetch_return=[])

        result = _async_run(resolver.resolve("billing", ctx, db))

        assert result.unresolved_key is None
        assert "billing" in result.text

    def test_pipe_in_name_is_escaped(self) -> None:
        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        db = _make_db(fetch_return=[_resource_catalog_row("A|B", ["t"], "desc")])

        result = _async_run(resolver.resolve("all", ctx, db))

        assert "A\\|B" in result.text

    def test_no_persona_context_needed(self) -> None:
        """Resources-Katalog braucht — anders als playbooks-catalog — keine Persona."""
        resolver = ResourcesCatalogResolver()
        ctx = RenderContext(
            workspace_id=uuid4(),
            persona_id=None,
            now=datetime(2026, 5, 31, tzinfo=UTC),
        )
        db = _make_db(fetch_return=[_resource_catalog_row("R", [], "desc")])

        result = _async_run(resolver.resolve("all", ctx, db))

        assert result.unresolved_key is None
        assert "R" in result.text

    def test_registered_in_registry(self) -> None:
        assert isinstance(REGISTRY["resources-catalog"], ResourcesCatalogResolver)

    def test_overflow_truncates_and_appends_hint(self) -> None:
        from who2be_api.services.placeholders.resolvers.catalog import _CATALOG_LIMIT

        resolver = ResourcesCatalogResolver()
        ctx = _ctx()
        # Eine Zeile mehr als das Limit (+1-Peek) → Overflow-Pfad.
        rows = [_resource_catalog_row(f"R{i}", [], "desc") for i in range(_CATALOG_LIMIT + 1)]
        db = _make_db(fetch_return=rows)

        result = _async_run(resolver.resolve("all", ctx, db))

        # Nur _CATALOG_LIMIT Daten-Zeilen (R0..R{limit-1}); die letzte Zeile fehlt.
        data_lines = [
            line
            for line in result.text.splitlines()
            if line.startswith("|") and "fetch_resource(" in line
        ]
        assert len(data_lines) == _CATALOG_LIMIT
        assert "und weitere" in result.text
        assert "list_resources" in result.text


# ---------------------------------------------------------------------------
# render_skills_table
# ---------------------------------------------------------------------------


@pytest.fixture
def _skills_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aktiviert das (per Default deaktivierte) Skills-Feature fuer den Test.

    Skills sind derzeit Coming Soon (ADR-0026, `SKILLS_ENABLED = False`). Die
    folgende Klasse testet das zugrunde liegende Rendering — also die Logik, die
    bei Reaktivierung greift — und flippt das Flag dafuer lokal auf True.
    """
    monkeypatch.setattr("who2be_api.services.placeholders._core.SKILLS_ENABLED", True)


class TestRenderSkillsTable:
    def test_disabled_by_default_returns_empty(self) -> None:
        # Coming Soon (ADR-0026): ohne aktiviertes Flag rendert nichts.
        assert render_skills_table([{"name": "Python", "note": "fortgeschritten"}]) == ""

    def test_renders_table_with_note(self, _skills_enabled: None) -> None:
        table = render_skills_table(
            [
                {"name": "Python", "note": "fortgeschritten"},
                {"name": "Refactoring", "note": ""},
            ]
        )
        assert "## Skills" in table
        assert "| Skill | Hinweis |" in table
        assert "| Python | fortgeschritten |" in table
        assert "| Refactoring |  |" in table

    def test_empty_skills_returns_empty_string(self, _skills_enabled: None) -> None:
        assert render_skills_table([]) == ""

    def test_non_list_returns_empty_string(self, _skills_enabled: None) -> None:
        assert render_skills_table(None) == ""

    def test_skips_nameless_entries(self, _skills_enabled: None) -> None:
        table = render_skills_table([{"name": "  ", "note": "x"}, {"name": "Echt"}])
        assert "Echt" in table
        # Genau eine Daten-Zeile: Header `| Skill | Hinweis |`, Trenner `|---|---|`
        # und die eine Echt-Zeile — der namenlose Eintrag erscheint nicht.
        data_rows = [
            line
            for line in table.splitlines()
            if line.startswith("|") and "Skill | Hinweis" not in line and not line.startswith("|--")
        ]
        assert data_rows == ["| Echt |  |"]

    def test_pipe_escaped_in_table(self, _skills_enabled: None) -> None:
        table = render_skills_table([{"name": "A|B", "note": "c|d"}])
        assert "A\\|B" in table
        assert "c\\|d" in table


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
            "list_resources(tag?)",
            "fetch_resource(resource_id, block_ids?)",
        ):
            assert expected in result.text

    def test_registered_in_registry_under_tools_overview_key(self) -> None:
        assert "tools-overview" in REGISTRY
        ctx = _ctx()
        db = _make_db()
        result = _async_run(REGISTRY["tools-overview"].resolve("", ctx, db))
        assert "Verfuegbare Werkzeuge" in result.text

    def test_fetch_playbook_mentions_composite(self) -> None:
        """fetch_playbook-Eintrag erklaert Composite-Sequenz (E2)."""
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db)).text
        assert "Composite" in result or "composed_playbooks" in result

    def test_get_persona_mentions_modi(self) -> None:
        """get_persona-Eintrag erklaert content.modes / Modi-Auswahl (E2)."""
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db)).text
        assert "content.modes" in result or "Modi" in result

    def test_overview_includes_applied_vs_triggered_hint(self) -> None:
        """Overview enthaelt Hinweis: applied (immer geladen) vs. triggered (E2)."""
        resolver = ToolsOverviewResolver()
        ctx = _ctx()
        db = _make_db()
        result = _async_run(resolver.resolve("", ctx, db)).text
        assert "applied" in result or "eingebettet" in result
        assert "list_triggers" in result

    # --- Pro-Agent-Filter (Tool-Policy) -----------------------------------

    @staticmethod
    def _policy_ctx(**policy_kwargs: Any) -> RenderContext:
        from who2be_models import AgentToolPolicy

        return RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=UUID("00000000-0000-0000-0000-000000000001"),
            now=datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
            tool_policy=AgentToolPolicy(**policy_kwargs),
        )

    def test_no_policy_hides_write_tools(self) -> None:
        """Ohne Policy (None): nur Read-Tools, keine Write-Tools."""
        result = _async_run(ToolsOverviewResolver().resolve("", _ctx(), _make_db())).text
        assert "list_playbooks" in result
        assert "create_playbook" not in result
        assert "create_agent" not in result

    def test_default_policy_shows_reads_no_writes(self) -> None:
        """Default-Policy = Read-Assigned ohne Writes (secure by default)."""
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(), _make_db())
        ).text
        assert "list_playbooks" in result
        assert "create_playbook" not in result
        # Default ist jetzt `assigned` → der Scope-Hinweis erscheint.
        assert "nur die dir zugewiesenen" in result

    def test_playbook_write_capability_reveals_write_tools(self) -> None:
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(playbook_write=True), _make_db())
        ).text
        assert "create_playbook" in result
        assert "Schreibzugriff" in result
        # Andere Domains bleiben gesperrt.
        assert "create_resource" not in result
        assert "create_agent" not in result

    def test_assigned_scope_adds_hint(self) -> None:
        from who2be_models import ReadScope

        result = _async_run(
            ToolsOverviewResolver().resolve(
                "", self._policy_ctx(playbook_read=ReadScope.assigned), _make_db()
            )
        ).text
        assert "nur die dir zugewiesenen Playbooks" in result

    def test_read_scope_none_hides_tool(self) -> None:
        from who2be_models import ReadScope

        result = _async_run(
            ToolsOverviewResolver().resolve(
                "", self._policy_ctx(playbook_read=ReadScope.none), _make_db()
            )
        ).text
        # Die Tool-Eintraege (Signaturen) sind weg — der Applied-Hinweis-Text
        # darf "fetch_playbook(id)" weiterhin erwaehnen, daher auf die exakte
        # Tool-Signatur pruefen.
        assert "list_playbooks(tag?, trigger?)" not in result
        assert "fetch_playbook(playbook_id)" not in result
        # Resources bleiben (Default all) sichtbar.
        assert "list_resources(tag?)" in result

    def test_agent_read_tools_listed_in_overview(self) -> None:
        """list_agents/get_agent stehen in der Werkzeug-Uebersicht (nicht nur fetch_agent)."""
        result = _async_run(ToolsOverviewResolver().resolve("", _ctx(), _make_db())).text
        assert "list_agents()" in result
        assert "get_agent(agent_id)" in result
        assert "fetch_agent(agent_id)" in result

    def test_feedback_protocol_shown_when_feedback_write(self) -> None:
        """Bei aktivem feedback_write erscheint das Rueckmelde-Protokoll (ADR-0038)."""
        # Default-Policy hat feedback_write=True.
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(), _make_db())
        ).text
        assert "record_usage" in result
        assert "Rueckmeldung" in result
        assert "outcome" in result

    def test_feedback_protocol_hidden_when_feedback_write_off(self) -> None:
        """Ohne feedback_write: weder Tool-Eintrag noch Protokoll-Hinweis."""
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(feedback_write=False), _make_db())
        ).text
        assert "record_usage" not in result
        assert "Rueckmeldung" not in result

    def test_no_policy_hides_feedback_protocol(self) -> None:
        """Ohne Policy (Persona-Body): kein Feedback-Tool, kein Protokoll."""
        result = _async_run(ToolsOverviewResolver().resolve("", _ctx(), _make_db())).text
        assert "record_usage" not in result
        assert "Rueckmeldung" not in result

    def test_resolve_feedback_hidden_by_default(self) -> None:
        """Die Triage (feedback_resolve) ist secure-by-default aus — das Tool
        erscheint trotz aktivem feedback_write nicht."""
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(), _make_db())
        ).text
        assert "record_usage" in result  # feedback_write ist Default an
        assert "resolve_feedback" not in result

    def test_feedback_resolve_capability_reveals_triage_tool(self) -> None:
        result = _async_run(
            ToolsOverviewResolver().resolve("", self._policy_ctx(feedback_resolve=True), _make_db())
        ).text
        assert "resolve_feedback(feedback_id, resolution, note?)" in result
        assert "dismissed" in result

    def test_agent_read_assigned_marks_self_only(self) -> None:
        """Scope `assigned`: Hinweis „nur dein eigener Agent" + fetch_agent self-only."""
        from who2be_models import ReadScope

        result = _async_run(
            ToolsOverviewResolver().resolve(
                "", self._policy_ctx(agent_read=ReadScope.assigned), _make_db()
            )
        ).text
        assert "nur dein eigener Agent" in result
        # fetch_agent-Beschreibung verweist fuer fremde Agenten auf get_agent.
        assert "get_agent" in result

    def test_agent_read_none_hides_agent_tools(self) -> None:
        from who2be_models import ReadScope

        result = _async_run(
            ToolsOverviewResolver().resolve(
                "", self._policy_ctx(agent_read=ReadScope.none), _make_db()
            )
        ).text
        assert "list_agents()" not in result
        assert "get_agent(agent_id)" not in result
        assert "fetch_agent(agent_id)" not in result


# ---------------------------------------------------------------------------
# ToolRefResolver (WP-2)
# ---------------------------------------------------------------------------


class TestToolRefResolver:
    """Unit-Tests fuer den `tool-ref`-Resolver (Blueprint
    `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`, WP-2)."""

    def _row(
        self,
        alias: str = "todo",
        display_name: str = "Todoist",
        mcp_server_name: str = "Todoist MCP",
        tool_names: list[str] | None = None,
        usage_notes: str = "Immer fuer To-dos nutzen.",
        fallback_note: str | None = None,
    ) -> MagicMock:
        row = MagicMock()
        data = {
            "alias": alias,
            "content": {
                "display_name": display_name,
                "mcp_server_name": mcp_server_name,
                "tool_names": tool_names if tool_names is not None else ["add_task", "list_tasks"],
                "usage_notes": usage_notes,
                "fallback_note": fallback_note,
                "tags": [],
            },
        }
        row.__getitem__ = MagicMock(side_effect=lambda k: data[k])
        return row

    def test_resolves_active_tool_binding(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(self._row())

        result = _async_run(resolver.resolve("todo", ctx, db))

        assert isinstance(result, ResolveResult)
        assert result.unresolved_key is None
        assert "todo" in result.text
        assert "Todoist" in result.text
        assert "Todoist MCP" in result.text
        assert "`add_task`" in result.text
        assert "`list_tasks`" in result.text
        assert "Immer fuer To-dos nutzen." in result.text

    def test_resolves_optional_fallback_note(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(self._row(fallback_note="Erinnere den User, es manuell zu erledigen."))

        result = _async_run(resolver.resolve("todo", ctx, db))

        assert result.unresolved_key is None
        assert "Fallback: Erinnere den User, es manuell zu erledigen." in result.text

    def test_usage_notes_as_blocknote_json_renders_plain_text(self) -> None:
        """usage_notes als stringifiziertes BlockNote-JSON wird ueber
        `blocks_plain_text` (Single-Source, `placeholders._core`) zu Klartext."""
        resolver = ToolRefResolver()
        ctx = _ctx()
        doc = json.dumps([_blk("b1", "Nutze fuer alle To-do-Anfragen.")])
        db = _make_db(self._row(usage_notes=doc))

        result = _async_run(resolver.resolve("todo", ctx, db))

        assert "Nutze fuer alle To-do-Anfragen." in result.text
        # Rohes JSON darf nicht im Output landen.
        assert '"type"' not in result.text

    def test_no_tool_names_lists_none_gelistet(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(self._row(tool_names=[]))

        result = _async_run(resolver.resolve("todo", ctx, db))

        assert "keine gelistet" in result.text

    def test_unknown_alias_returns_error_string_and_miss_key(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(None)

        result = _async_run(resolver.resolve("unbekannt", ctx, db))

        assert result.text == "<Tool nicht verfuegbar>"
        assert result.unresolved_key == "tool-ref:unbekannt"

    def test_draft_only_tool_is_miss(self) -> None:
        """Nur Draft/Review (kein Active) -> derselbe Miss wie unbekannter Alias:
        der JOIN filtert bereits auf `status='active'`, daher liefert die Fake-DB
        hier `None` (kein Match), analog zu `test_unknown_alias_...`."""
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(None)

        result = _async_run(resolver.resolve("draft-tool", ctx, db))

        assert result.text == "<Tool nicht verfuegbar>"
        assert result.unresolved_key == "tool-ref:draft-tool"
        db.fetchrow.assert_awaited_once()

    def test_empty_alias_returns_miss_without_db_call(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db()

        result = _async_run(resolver.resolve("   ", ctx, db))

        assert result.text == "<Tool nicht verfuegbar>"
        assert result.unresolved_key == "tool-ref:   "
        db.fetchrow.assert_not_called()

    def test_missing_display_name_falls_back_to_alias(self) -> None:
        resolver = ToolRefResolver()
        ctx = _ctx()
        db = _make_db(self._row(display_name=""))

        result = _async_run(resolver.resolve("todo", ctx, db))

        assert "todo" in result.text

    def test_registered_in_registry(self) -> None:
        assert isinstance(REGISTRY["tool-ref"], ToolRefResolver)


class TestToolsOverviewSSoTParity:
    """Drift-Guard: kuratierte `_TOOLS`-Gruppen vs. Sichtbarkeits-SSoT (ADR-0042).

    Die Sichtbarkeit pro Tool-Name lebt in `who2be_models.tool_requirements`
    (`MCP_TOOL_REQUIREMENTS`); der Resolver gruppiert nur noch kuratiert.
    Diese Tests halten beide Seiten synchron — in beide Richtungen.
    """

    # Mapping-Tools, die BEWUSST in keiner kuratierten Prompt-Gruppe stehen —
    # der `tools-overview`-Katalog ist kuratiert, nicht vollstaendig. Ein
    # neues MCP-Tool muss entweder in eine `_ToolDoc.tool_names`-Gruppe
    # einsortiert ODER hier mit Begruendung eingetragen werden.
    _PROMPT_CATALOG_EXCEPTIONS: frozenset[str] = frozenset(
        {
            # Versions-/Discovery-Introspektion — Spezialwerkzeuge, die der
            # Agent on demand entdeckt; nicht Teil des Prompt-Katalogs.
            "find_usages",
            "list_versions",
            "get_version",
            "diff_versions",
            # Block-Introspektion — der Prompt-Fall ist durch
            # `fetch_resource(resource_id, block_ids?)` abgedeckt.
            "list_resource_blocks",
            # Fehler-Meldeweg (ADR-0038) — bewusst nicht im kuratierten
            # Feedback-Eintrag gelistet.
            "report_problem",
        }
    )

    @staticmethod
    def _all_group_names() -> list[str]:
        from who2be_api.services.placeholders.resolvers.tools import _TOOLS

        return [name for tool in _TOOLS for name in tool.tool_names]

    def test_every_group_reference_exists_in_mapping(self) -> None:
        """Jeder Name in `_ToolDoc.tool_names` ist ein Schluessel der SSoT."""
        from who2be_models import MCP_TOOL_REQUIREMENTS

        unknown = [n for n in self._all_group_names() if n not in MCP_TOOL_REQUIREMENTS]
        assert unknown == [], f"unbekannte tool_names (nicht in MCP_TOOL_REQUIREMENTS): {unknown}"

    def test_no_tool_referenced_in_two_groups(self) -> None:
        """Kein Tool-Name kommt in mehr als einer kuratierten Gruppe vor."""
        names = self._all_group_names()
        duplicates = sorted({n for n in names if names.count(n) > 1})
        assert duplicates == [], f"doppelt gruppierte tool_names: {duplicates}"

    def test_every_non_always_mapping_tool_grouped_or_documented(self) -> None:
        """Jedes Nicht-`always`-Mapping-Tool ist gruppiert oder dokumentierte Ausnahme."""
        from who2be_models import MCP_TOOL_REQUIREMENTS

        grouped = set(self._all_group_names())
        non_always = {n for n, req in MCP_TOOL_REQUIREMENTS.items() if not req.always}
        always = set(MCP_TOOL_REQUIREMENTS) - non_always

        missing = non_always - grouped - self._PROMPT_CATALOG_EXCEPTIONS
        assert missing == set(), f"weder gruppiert noch als Ausnahme dokumentiert: {missing}"
        # Ausnahmen duerfen nicht (mehr) gleichzeitig gruppiert sein.
        assert grouped & self._PROMPT_CATALOG_EXCEPTIONS == set()
        # `always`-Tools (ping/whoami) sind bewusst nicht im kuratierten Katalog.
        assert grouped & always == set()
        # Kein Stale-Eintrag: jede Ausnahme existiert (nicht-`always`) im Mapping.
        assert self._PROMPT_CATALOG_EXCEPTIONS <= non_always

    # --- Verhaltens-Aequivalenz nach dem SSoT-Refactor ---------------------

    @staticmethod
    def _render(**policy_kwargs: Any) -> str:
        from who2be_models import AgentToolPolicy

        ctx = RenderContext(
            workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
            persona_id=UUID("00000000-0000-0000-0000-000000000001"),
            now=datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
            tool_policy=AgentToolPolicy(**policy_kwargs),
        )
        return str(_async_run(ToolsOverviewResolver().resolve("", ctx, _make_db())).text)

    def test_default_policy_shows_reads_and_feedback_no_writes(self) -> None:
        """Default-Policy: alle Read-Gruppen + Feedback-Gruppe, keine Writes."""
        result = self._render()
        for signature in (
            "get_persona(identifier)",
            "search(query, types?, limit?)",
            "list_triggers()",
            "list_playbooks(tag?, trigger?)",
            "fetch_playbook(playbook_id)",
            "list_resources(tag?)",
            "fetch_resource(resource_id, block_ids?)",
            "list_agents()",
            "get_agent(agent_id)",
            "fetch_agent(agent_id)",
            "record_usage(...) / submit_feedback(...)",
        ):
            assert signature in result
        for write_fragment in (
            "create_persona",
            "create_playbook",
            "create_resource",
            "create_agent",
            "transition_persona",
            "create_system_prompt",
            "list_placeholders()",
        ):
            assert write_fragment not in result

    def test_full_policy_shows_all_curated_groups(self) -> None:
        """Voll-Policy: jede kuratierte Gruppe erscheint im Output."""
        from who2be_api.services.placeholders.resolvers.tools import _TOOLS
        from who2be_models import ReadScope

        result = self._render(
            playbook_read=ReadScope.all,
            resource_read=ReadScope.all,
            agent_read=ReadScope.all,
            persona_read=True,
            persona_write=True,
            playbook_write=True,
            resource_write=True,
            agent_write=True,
            system_prompt_write=True,
            feedback_write=True,
            feedback_resolve=True,
            promote_retire=True,
            external_tool_write=True,
        )
        for tool in _TOOLS:
            assert tool.signature in result

    def test_resource_read_none_hides_resource_reads_search_stays(self) -> None:
        """`resource_read=none`: Resource-Zeilen weg, search + andere Reads bleiben."""
        from who2be_models import ReadScope

        result = self._render(resource_read=ReadScope.none)
        assert "list_resources(tag?)" not in result
        assert "fetch_resource(resource_id, block_ids?)" not in result
        assert "search(query, types?, limit?)" in result
        assert "list_playbooks(tag?, trigger?)" in result
        assert "get_persona(identifier)" in result


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

    def test_non_json_body_returned_as_is_with_empty_unresolved(self) -> None:
        # Track B: kein body_format mehr — ein nicht-JSON-Body (z. B. ein
        # frischer Plain-Entwurf) wird unveraendert + leere unresolved-Liste
        # zurueckgegeben (kein Fehler).
        db = _make_db()
        ctx = _ctx()
        body = "Hallo {{ persona.name }}"

        text, unresolved = _async_run(render_template_body(body, ctx, db))

        assert text == body
        assert unresolved == []

    def test_blocknote_text_inline(self) -> None:
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc({"type": "text", "text": "Hallo Welt", "styles": {}})

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

        assert "Hallo Welt" in text
        assert unresolved == []

    def test_blocknote_top_level_array_shape(self) -> None:
        """Frontend serialisiert `editor.document` als reines Array — Renderer
        muss das ebenso akzeptieren wie das `{content: [...]}`-Wrapper-Format."""
        db = _make_db()
        ctx = _ctx()
        doc = self._blocknote_doc_array({"type": "text", "text": "Top-Array", "styles": {}})

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

        assert "Top-Array" in text
        assert unresolved == []

    def test_blocknote_top_level_array_with_placeholder(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc_array(
            {"type": "text", "text": "Heute: ", "styles": {}},
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}},
        )

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

        assert text.strip() == "Heute: 2026-05-31"
        assert unresolved == []

    def test_blocknote_date_placeholder_iso(self) -> None:
        db = _make_db()
        ctx = _ctx(now=datetime(2026, 5, 31, tzinfo=UTC))
        doc = self._blocknote_doc(
            {"type": "placeholder", "props": {"kind": "date", "target_id": "", "label": "Datum"}}
        )

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

        assert "unknown-kind" in text
        # Unbekanntes Kind landet NICHT in unresolved (kein Resolver vorhanden).
        assert unresolved == []

    def test_invalid_json_returned_as_is_with_empty_unresolved(self) -> None:
        db = _make_db()
        ctx = _ctx()
        bad_body = "{not valid json"

        text, unresolved = _async_run(render_template_body(bad_body, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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
        # Valider Playbook ist kein Composite -> db.fetch liefert keine Kinder.
        db.fetch = AsyncMock(return_value=[])

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

        text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        _text, unresolved = _async_run(render_template_body(doc, ctx, db))

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

        _text, unresolved = _async_run(render_template_body(doc, ctx, db))

        assert unresolved == []


# ---------------------------------------------------------------------------
# Read-Scoping (assigned) der Inhalts-/Katalog-Resolver (MEDIUM-Findings)
# ---------------------------------------------------------------------------


def _agent_render_ctx(scope: Any = None, persona_id: UUID | None = None) -> RenderContext:
    from who2be_models import AgentToolPolicy, ReadScope

    rs = scope if scope is not None else ReadScope.assigned
    return RenderContext(
        workspace_id=UUID("00000000-0000-0000-0000-000000000099"),
        persona_id=persona_id or UUID("00000000-0000-0000-0000-000000000001"),
        now=datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC),
        tool_policy=AgentToolPolicy(playbook_read=rs, resource_read=rs),
        agent_id=uuid4(),
    )


def _scope_db(
    assigned: list[UUID], *, fetch_rows: Any = None, fetchrow_return: Any = None
) -> MagicMock:
    """Fake-Connection, die `assigned_*_ids` (RECURSIVE „FROM agent a") vom
    Resolver-Query trennt: erstere liefert die assigned-Menge, letztere die
    konfigurierten Entity-Zeilen."""
    db = MagicMock()

    async def _fetch(sql: str, *_args: object) -> Any:
        if "FROM agent a" in sql:
            return [{"id": a} for a in assigned]
        return fetch_rows if fetch_rows is not None else []

    db.fetch = AsyncMock(side_effect=_fetch)
    db.fetchrow = AsyncMock(return_value=fetchrow_return)
    return db


class TestRenderReadScope:
    def test_resource_catalog_filters_to_assigned(self) -> None:
        visible, hidden = uuid4(), uuid4()
        rows = [
            {"id": visible, "name": "Sichtbar", "content": {"description": "d", "tags": []}},
            {"id": hidden, "name": "Geheim", "content": {"description": "d", "tags": []}},
        ]
        db = _scope_db([visible], fetch_rows=rows)
        result = _async_run(ResourcesCatalogResolver().resolve("all", _agent_render_ctx(), db))
        assert "Sichtbar" in result.text
        assert "Geheim" not in result.text

    def test_resource_catalog_all_scope_unfiltered(self) -> None:
        from who2be_models import ReadScope

        a, b = uuid4(), uuid4()
        rows = [
            {"id": a, "name": "Eins", "content": {"description": "", "tags": []}},
            {"id": b, "name": "Zwei", "content": {"description": "", "tags": []}},
        ]
        db = _scope_db([], fetch_rows=rows)
        result = _async_run(
            ResourcesCatalogResolver().resolve("all", _agent_render_ctx(ReadScope.all), db)
        )
        assert "Eins" in result.text
        assert "Zwei" in result.text

    def test_playbook_pill_gated_when_unassigned(self) -> None:
        db = _scope_db([uuid4()])  # Ziel-Pill nicht in der assigned-Menge
        result = _async_run(PlaybookResolver().resolve(str(uuid4()), _agent_render_ctx(), db))
        assert result.text == "<Playbook nicht verfuegbar>"
        assert result.unresolved_key is not None
        db.fetchrow.assert_not_called()

    def test_playbook_pill_visible_when_assigned(self) -> None:
        pid = uuid4()
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "name": "Mein PB",
                "content": {"description": "x", "body": "y"},
            }[k]
        )
        db = _scope_db([pid], fetchrow_return=row)
        result = _async_run(PlaybookResolver().resolve(str(pid), _agent_render_ctx(), db))
        assert "### Mein PB" in result.text

    def test_resource_pill_gated_when_unassigned(self) -> None:
        db = _scope_db([uuid4()])
        result = _async_run(ResourceResolver().resolve(str(uuid4()), _agent_render_ctx(), db))
        assert result.text == "<Resource nicht verfuegbar>"
        db.fetchrow.assert_not_called()
