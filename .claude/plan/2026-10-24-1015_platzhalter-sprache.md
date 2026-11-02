# Plan: Platzhalter-Saetze in der Template-Sprache (Kanban t_1ba0cf7d)

Stand: origin/main f9697fab. Entscheidung PM 2026-10-24: Option B.

## Ziel

`persona-ref`, `playbooks-catalog`, `resources-catalog`, `memory` und der
Rahmen von `tools-overview` rendern ihre festen Saetze nach
`RenderContext.locale`. Die Saetze kommen aus genau einer Textquelle
(`placeholders/_texts.py`). Fehlt die Locale, gilt Deutsch.

## Sprachquelle (keine neue Einstellung)

`system_prompt_template.locale` → `agent_language.date_locale()` →
`RenderContext.locale` (de-DE / en-US), gesetzt in `agent_render_service.py`
und `agent_fetch_rendered_service.py`. `texts_for()` nimmt das Sprachkuerzel
vor dem Bindestrich; unbekannt oder leer → `DEFAULT_LOCALE` ('de').

## Schritte

1. [x] Baseline: alle betroffenen Resolver ueber 157 Varianten (Policies,
   Memory-Modi/-Direktiven, Scopes, Leer-/Overflow-Faelle) am alten Code
   gerendert und gehasht; DE-Builder-Render gehasht.
2. [x] `_texts.py` mit `PlaceholderTexts` (frozen dataclass, jede Sprache
   traegt jeden Satz) fuer DE und EN; DE-Wortlaut 1:1 uebernommen.
3. [x] Resolver umgestellt; `memory_prompt_block(policy, locale=None)` bleibt
   rueckwaertskompatibel (PersonaService ruft ohne Locale → DE).
4. [x] Tests `test_placeholder_locale.py`: DE byte-identisch (Golden-Hash vom
   alten Code), EN ohne deutschen festen Satz, echtes Builder-Template DE
   unveraendert / EN englisch, Fallback.
5. [x] Rot-Probe: Locale-Weiche in `texts_for` auf festes DE → 7 rot;
   neue Tests gegen alten Resolver-Code → 4 rot.
6. [x] Changelog-Fragment, DoD, PR.

## Bewusst nicht

- Die ~50 kuratierten Werkzeug-Beschreibungen in `tools-overview` bleiben
  deutsch (eigene Karte).
- `## Modi` im persona-ref-Satz bleibt: `get_persona` rendert die
  Ueberschrift sprachunabhaengig so (`resolvers/persona.py`
  `_render_modes_section`); der Verweis muss treffen.
- Die Laufzeit-Sektion `## Gedaechtnis` in `PersonaService` (get_persona)
  ist kein Placeholder und nicht Teil der Karte.

## Messung (echtes Builder-Template, Builder-Policy, neutrale Inhalte)

| Sprache | vorher | nachher |
|---|---|---|
| DE | 5 079 B | 5 079 B (sha256 identisch) |
| EN | 4 945 B | 4 826 B (−119 B, −2,4 %) |
