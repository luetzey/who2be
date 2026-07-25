"""Unit-Tests fuer `services/agent_language.py` (WP5, „Ein Element, eine
Sprache", ADR-0045).

Reine Funktions-Tests ohne DB: die zentralen Maps (Sprachanweisung,
Datums-Locale) plus der `append_language_instruction`-Helper, den
`AgentRenderService` und `AgentFetchRenderedService` beide als einzigen
Aufrufort fuer die Prompt-Injektion nutzen.
"""

import json
from collections.abc import Iterator

import pytest

from who2be_api.repositories.builder_content import get_content_pack
from who2be_api.services.agent_language import (
    DATE_LOCALES,
    LANGUAGE_INSTRUCTIONS,
    append_language_instruction,
    date_locale,
    language_instruction,
)
from who2be_models.locale import SUPPORTED_LOCALES


def test_language_instruction_de() -> None:
    assert language_instruction("de") == (
        "Standard-Antwortsprache ist Deutsch. Schreibt der Nutzer in einer "
        "anderen Sprache, folge seiner Sprache."
    )


def test_language_instruction_en() -> None:
    assert language_instruction("en") == (
        "Your default response language is English. If the user writes in "
        "another language, follow theirs."
    )


def test_language_instruction_unknown_locale_falls_back_to_de() -> None:
    assert language_instruction("fr") == LANGUAGE_INSTRUCTIONS["de"]


def test_language_instruction_none_falls_back_to_de() -> None:
    assert language_instruction(None) == LANGUAGE_INSTRUCTIONS["de"]


def test_date_locale_de_maps_to_de_de() -> None:
    assert date_locale("de") == "de-DE"


def test_date_locale_en_maps_to_en_us() -> None:
    assert date_locale("en") == "en-US"


def test_date_locale_unknown_falls_back_to_de_de() -> None:
    assert date_locale("fr") == DATE_LOCALES["de"]


def test_date_locale_none_falls_back_to_de_de() -> None:
    assert date_locale(None) == "de-DE"


def test_append_language_instruction_de_appends_as_final_section() -> None:
    rendered = append_language_instruction("Du bist ein hilfreicher Assistent.", "de")
    assert rendered == f"Du bist ein hilfreicher Assistent.\n\n{LANGUAGE_INSTRUCTIONS['de']}"


def test_append_language_instruction_en_appends_as_final_section() -> None:
    rendered = append_language_instruction("You are a helpful assistant.", "en")
    assert rendered == f"You are a helpful assistant.\n\n{LANGUAGE_INSTRUCTIONS['en']}"


def test_append_language_instruction_empty_body_returns_only_instruction() -> None:
    assert append_language_instruction("", "en") == LANGUAGE_INSTRUCTIONS["en"]
    assert append_language_instruction("   ", "de") == LANGUAGE_INSTRUCTIONS["de"]


def test_append_language_instruction_unknown_locale_falls_back_to_de() -> None:
    rendered = append_language_instruction("Body", "fr")
    assert rendered == f"Body\n\n{LANGUAGE_INSTRUCTIONS['de']}"


# --- Regressionsschutz: keine Sprachanweisung in den Template-Bodies --------
#
# Die Output-Sprache kommt AUSSCHLIESSLICH aus der zentralen Injektion hier im
# Modul. Fruehere Template-Bodies trugen eigene Sprachsaetze ("nutze die
# gleiche Sprache wie der Nutzer") und widersprachen damit der Injektion
# (WP-A, Issue #358). Dieser Test faengt einen Rueckfall ab.

_LANGUAGE_PHRASES = (
    "gleiche sprache",
    "selbe sprache",
    "sprache des nutzers",
    "same language",
    "user's language",
    "antworte auf deutsch",
    "respond in english",
    "auf englisch",
    "in german",
)


def _iter_block_texts(blocks: object) -> Iterator[str]:
    """Laeuft rekursiv ueber alle Textwerte eines BlockNote-Dokuments."""
    if isinstance(blocks, list):
        for block in blocks:
            yield from _iter_block_texts(block)
    elif isinstance(blocks, dict):
        for key, value in blocks.items():
            if key == "text" and isinstance(value, str):
                yield value
            elif isinstance(value, (list, dict)):
                yield from _iter_block_texts(value)


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_template_bodies_carry_no_language_instruction(locale: str) -> None:
    pack = get_content_pack(locale)
    offenders: list[str] = []
    for template in pack.templates:
        body = json.loads(template.load_body(locale))
        for text in _iter_block_texts(body):
            lowered = text.lower()
            for phrase in _LANGUAGE_PHRASES:
                if phrase in lowered:
                    offenders.append(f"{locale}/{template.slug}: {text!r}")
    assert offenders == [], (
        "Template-Bodies duerfen keine eigene Sprachanweisung tragen "
        f"(zentrale Injektion in agent_language.py): {offenders}"
    )
