"""Output-Sprache des gerenderten Agent-System-Prompts (WP5, ADR-0045).

„Ein Element, eine Sprache": ein Agent-System-Prompt IST deutsch oder
englisch — die Sprache des verlinkten System-Prompt-Templates (Identitaets-
Zeile, `system_prompt_template.locale`). Zwei Konsequenzen aus derselben
Quelle, zentral an einer Stelle gepflegt, damit ALLE Render-Konsumenten
(API-Render-Endpoint `/agents/{id}/render`, API-Endpoint `/agents/{id}/rendered`
UND — darueber — das MCP-Tool `fetch_agent`) konsistent bleiben:

1. `language_instruction`: eine explizite, aber weiche Output-Sprachanweisung
   (Standardsprache mit Vorrang der Nutzersprache), die
   `append_language_instruction` als abschliessender Abschnitt an den
   expandierten Prompt anhaengt. Sprachaussagen gehoeren AUSSCHLIESSLICH
   hierher — nicht in die Template-Bodies selbst. Nur eine zentrale
   Injektionsstelle verhindert widerspruechliche Sprachanweisungen (ein
   Body-Satz „nutze die gleiche Sprache wie der Nutzer" neben der harten
   Renderer-Injektion war genau so ein Widerspruch, siehe ADR-0045-Nachzug).
2. `date_locale`: der BCP-47-Tag fuer `RenderContext.locale` (Placeholder-
   Registry, Datums-/Format-Resolver) — ersetzt das frueher hart gesetzte
   `'de-DE'`.

Beide Maps sind bewusst offen erweiterbar (neue Sprache = ein Eintrag in
beiden Dicts); eine unbekannte oder fehlende Sprache faellt auf
`DEFAULT_LOCALE` ('de') zurueck, analog `who2be_models.locale.DEFAULT_LOCALE`.
"""

from __future__ import annotations

from who2be_models import DEFAULT_LOCALE

# Explizite, aber weiche Output-Sprachanweisung pro App-Sprachkuerzel
# ('de'/'en', wie `who2be_models.locale.SUPPORTED_LOCALES'): Standardsprache
# mit Vorrang der Nutzersprache (User-Entscheidung, ADR-0045-Nachzug — Element-
# Sprache ist Vorgabe, der Nutzer kann sie kippen). Neue Sprache -> ein
# Eintrag hier.
LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "de": (
        "Standard-Antwortsprache ist Deutsch. Schreibt der Nutzer in einer "
        "anderen Sprache, folge seiner Sprache."
    ),
    "en": (
        "Your default response language is English. If the user writes in "
        "another language, follow theirs."
    ),
}

# BCP-47-Tag fuer `RenderContext.locale` (Datumsformat der Placeholder-
# Registry) pro App-Sprachkuerzel. Neue Sprache -> ein Eintrag hier.
DATE_LOCALES: dict[str, str] = {
    "de": "de-DE",
    "en": "en-US",
}


def language_instruction(locale: str | None) -> str:
    """Output-Sprachanweisung fuer `locale`; Fallback auf `DEFAULT_LOCALE`."""
    fallback = LANGUAGE_INSTRUCTIONS[DEFAULT_LOCALE]
    return LANGUAGE_INSTRUCTIONS.get(locale or DEFAULT_LOCALE, fallback)


def date_locale(locale: str | None) -> str:
    """BCP-47-Tag fuer `RenderContext.locale`; Fallback auf `DEFAULT_LOCALE`."""
    fallback = DATE_LOCALES[DEFAULT_LOCALE]
    return DATE_LOCALES.get(locale or DEFAULT_LOCALE, fallback)


def append_language_instruction(rendered: str, locale: str | None) -> str:
    """Haengt die Sprachanweisung als abschliessenden Abschnitt an `rendered` an.

    Deterministisch EIN Aufrufort pro Render-Pfad (`AgentRenderService`,
    `AgentFetchRenderedService`) — beide rufen exakt diese Funktion, damit die
    Injektion nicht pro Konsument dupliziert wird. Leerer `rendered`-Text
    (theoretisch, z. B. komplett leeres Template) liefert nur die Anweisung,
    kein fuehrender Leerzeilen-Block.
    """
    instruction = language_instruction(locale)
    if not rendered.strip():
        return instruction
    return f"{rendered}\n\n{instruction}"


__all__ = [
    "DATE_LOCALES",
    "LANGUAGE_INSTRUCTIONS",
    "append_language_instruction",
    "date_locale",
    "language_instruction",
]
