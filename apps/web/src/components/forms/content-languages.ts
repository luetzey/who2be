// Content-Locale (ADR-0045 „Ein Element, eine Sprache"): zentrale Liste der
// im Web-UI waehlbaren Element-Sprachen (Label + Value) fuer Persona /
// Playbook / Resource / externes Tool / System-Prompt. Eigene Quelle,
// unabhaengig vom UI-String-i18n-Set (`src/i18n`) — beide starten heute mit
// de/en, koennen aber unabhaengig voneinander wachsen. Die Backend-Spalte ist
// offen (kein CHECK-Constraint, ADR-0027/0045); die UI startet bewusst klein
// und erweitert hier zentral.
//
// Eigene Datei (kein Komponenten-Modul), damit `LanguageSelect.tsx` rein
// Komponenten exportiert (react-refresh/only-export-components).
export const CONTENT_LOCALES = [
  { value: 'de', label: 'Deutsch' },
  { value: 'en', label: 'English' },
] as const

// Wie `CONTENT_LOCALES`, aber als mutables `{ value: string; label: string
// }[]` — passt ohne Zusatz-Mapping auf `ListFilterBar`/`PlaybookListToolbar`-
// Facetten-Props (`LocaleFilterOption[]`), die generisch mit anderen
// String-Facetten (Tags, Typen) geteilt werden.
export const CONTENT_LOCALE_OPTIONS: { value: string; label: string }[] = CONTENT_LOCALES.map(
  (entry) => ({ ...entry }),
)
