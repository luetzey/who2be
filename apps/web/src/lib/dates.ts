import i18n, { DEFAULT_LOCALE } from '@/i18n'

// Zentrale Datumsformatierung: Datumsangaben folgen der UI-Sprache, nicht der
// Browser-Locale. `toLocaleString()` ohne Argument nimmt die Locale des
// Browsers — mit en-US-Browser stand in deutscher UI dann "10/9/2026, 7:11:53 AM".
// Die ESLint-Regel in `eslint.config.js` verbietet deshalb die argumentlosen
// `toLocale*String()`-Aufrufe; neue Stellen nutzen diese Helfer.
//
// `resolvedLanguage` statt `language`: `language` kann ein vom Detektor
// geliefertes, nicht unterstuetztes Tag sein (z. B. `fr`), waehrend die UI im
// Fallback `de` steht. `resolvedLanguage` ist die Sprache, die die UI wirklich
// zeigt.
export function uiLocale(): string {
  return i18n.resolvedLanguage ?? i18n.language ?? DEFAULT_LOCALE
}

type DateInput = Date | string | number

function toDate(value: DateInput): Date {
  return value instanceof Date ? value : new Date(value)
}

/** Datum ohne Uhrzeit in der UI-Sprache (Ersatz fuer `toLocaleDateString()`). */
export function formatDate(value: DateInput, options?: Intl.DateTimeFormatOptions): string {
  return toDate(value).toLocaleDateString(uiLocale(), options)
}

/** Datum mit Uhrzeit in der UI-Sprache (Ersatz fuer `toLocaleString()`). */
export function formatDateTime(value: DateInput, options?: Intl.DateTimeFormatOptions): string {
  return toDate(value).toLocaleString(uiLocale(), options)
}
