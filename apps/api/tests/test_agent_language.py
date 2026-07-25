"""Unit-Tests fuer `services/agent_language.py` (WP5, „Ein Element, eine
Sprache", ADR-0045).

Reine Funktions-Tests ohne DB: die zentralen Maps (Sprachanweisung,
Datums-Locale) plus der `append_language_instruction`-Helper, den
`AgentRenderService` und `AgentFetchRenderedService` beide als einzigen
Aufrufort fuer die Prompt-Injektion nutzen.
"""

from who2be_api.services.agent_language import (
    DATE_LOCALES,
    LANGUAGE_INSTRUCTIONS,
    append_language_instruction,
    date_locale,
    language_instruction,
)


def test_language_instruction_de() -> None:
    assert language_instruction("de") == "Antworte auf Deutsch."


def test_language_instruction_en() -> None:
    assert language_instruction("en") == "Respond in English."


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
    assert rendered == "Du bist ein hilfreicher Assistent.\n\nAntworte auf Deutsch."


def test_append_language_instruction_en_appends_as_final_section() -> None:
    rendered = append_language_instruction("You are a helpful assistant.", "en")
    assert rendered == "You are a helpful assistant.\n\nRespond in English."


def test_append_language_instruction_empty_body_returns_only_instruction() -> None:
    assert append_language_instruction("", "en") == "Respond in English."
    assert append_language_instruction("   ", "de") == "Antworte auf Deutsch."


def test_append_language_instruction_unknown_locale_falls_back_to_de() -> None:
    rendered = append_language_instruction("Body", "fr")
    assert rendered == "Body\n\nAntworte auf Deutsch."
