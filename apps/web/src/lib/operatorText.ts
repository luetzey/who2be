// Betreiber-Freitext (Hinweisseite, Banner) — reine Hilfsfunktionen
// (Karte t_27d7c6ad). Bewusst ausserhalb von `src/config.ts`: viele Tests
// ersetzen `@/config` durch ein Teilobjekt, diese Funktionen sollen davon
// unberuehrt bleiben.

/** Freitext je Sprache. Leerstring = nicht gesetzt. */
export interface LocalizedText {
  de: string
  en: string
}

export type NoticeLevel = 'info' | 'warning'

/**
 * Obergrenze fuer Betreiber-Freitext in Zeichen (Code-Points). Ein Hinweis ist
 * ein Satz oder drei, kein Artikel — und ein versehentlich eingefuegter
 * Riesenblock soll das Layout nicht sprengen.
 */
export const FREE_TEXT_MAX_LENGTH = 500

/**
 * Trimmt und kappt auf `FREE_TEXT_MAX_LENGTH` (mit Auslassungszeichen).
 * Gerendert wird der Wert ausschliesslich als Textknoten — Markup wird nie
 * interpretiert, auch nicht hier.
 */
export function resolveFreeText(value: string | undefined): string {
  const trimmed = (value ?? '').trim()
  const chars = Array.from(trimmed)
  if (chars.length <= FREE_TEXT_MAX_LENGTH) {
    return trimmed
  }
  return `${chars.slice(0, FREE_TEXT_MAX_LENGTH - 1).join('').trimEnd()}…`
}

/**
 * Text zur aktiven Sprache; fehlt er, der der jeweils anderen (EN → DE,
 * DE → EN). Leerstring, wenn keiner gesetzt ist — auch bei fehlendem Objekt.
 */
export function pickLocalizedText(
  text: Partial<LocalizedText> | undefined,
  language: string | undefined,
): string {
  const de = text?.de ?? ''
  const en = text?.en ?? ''
  const isEn = language?.toLowerCase().startsWith('en') === true
  const [primary, secondary] = isEn ? [en, de] : [de, en]
  return primary !== '' ? primary : secondary
}

/** Unbekannte Level fallen auf "info" zurueck. */
export function resolveNoticeLevel(value: string | undefined): NoticeLevel {
  return value === 'warning' ? 'warning' : 'info'
}
