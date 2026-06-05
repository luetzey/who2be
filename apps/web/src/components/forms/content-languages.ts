// Content-i18n (ADR-0027): beim Anlegen waehlt der User eine oder mehrere
// Sprachen — pro Sprache legt das Backend eine eigene Draft-Version an. Das
// Set ist hier bewusst klein gehalten (Backend-Sprach-Set ist offen, die UI
// bietet vorerst DE/EN an). UI-Strings bleiben deutsch (String-Extraktion =
// Stream D1, nicht hier).
//
// Eigene Datei (kein Komponenten-Modul), damit `LanguageSelect.tsx` rein
// Komponenten exportiert (react-refresh/only-export-components).
export const CONTENT_LANGUAGES = [
  { value: 'de', label: 'Deutsch' },
  { value: 'en', label: 'English' },
] as const
