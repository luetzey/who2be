import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import de from './locales/de.json'
import en from './locales/en.json'

// Unterstuetzte Locales. `de` ist Default + Fallback — die App ist deutsch
// gewachsen, EN ist die Zweitsprache. Neue Sprachen: hier ergaenzen, in beiden
// Locale-JSONs uebersetzen und `LOCALE_LABELS` pflegen.
export const SUPPORTED_LOCALES = ['de', 'en'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'de'

// Anzeigelabel des Sprachumschalters (Endonyme — jeweils in der Zielsprache).
export const LOCALE_LABELS: Record<Locale, string> = {
  de: 'Deutsch',
  en: 'English',
}

// Persistenz-Schluessel (localStorage) des Sprachdetektors. Geraete-Cache; die
// geraeteuebergreifende Quelle ist Supabase `user_metadata.preferred_locale`
// (siehe docs/frontend/i18n.md).
export const LOCALE_STORAGE_KEY = 'who2be.locale'

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

// Namespaces = Top-Level-Keys der Locale-JSON (ein Namespace pro Feature plus
// die geteilten `common`/`layout`/`data`/`version`). Aus `de` abgeleitet, damit
// das Hinzufuegen eines Namespaces nur die JSONs beruehrt.
const resources = { de, en } as const

// `documentElement.lang` an die aktive Sprache angleichen: Screenreader waehlen
// darueber die Aussprache, Browser leiten daraus ihr Uebersetzungsangebot ab,
// und `htmlTag` ist die letzte Stufe der Detektor-Kette oben — ohne Sync bliebe
// das Attribut dauerhaft auf dem statischen Startwert aus `index.html` stehen.
// Bewusst hier im Setup statt in einem React-Hook: eine Modul-Funktion greift
// auch auf oeffentlichen Seiten ohne App-Shell, in der kein Hook gemountet ist.
// `resolvedLanguage` liefert bereits den Basis-Sprachcode (`load:
// 'languageOnly'`), also z. B. `en` statt `en-US`. Guard gegen `document`, falls
// dieses Modul je in einer Umgebung ohne DOM ausgewertet wird (SSR/Node).
function syncHtmlLang(): void {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.lang = i18n.resolvedLanguage ?? DEFAULT_LOCALE
}

i18n.on('languageChanged', syncHtmlLang)

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: SUPPORTED_LOCALES,
    // Nicht-explizite Treffer (z. B. `en-US` aus dem Navigator) auf die
    // Basissprache `en` mappen.
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    defaultNS: 'common',
    ns: Object.keys(de),
    interpolation: {
      // React escaped bereits — doppeltes Escaping wuerde Umlaute zerlegen.
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
    },
    react: {
      // Resources liegen inline gebundlet vor — kein Suspense-Fallback noetig.
      useSuspense: false,
    },
  })
  .then(syncHtmlLang)

export default i18n

// --- Vorrang-Regel fuer die gespeicherte Sprachpraeferenz -------------------
//
// `user_metadata.preferred_locale` ist ein STARTWERT fuer ein Geraet ohne
// eigene Wahl, keine laufende Quelle der Wahrheit. Zwei Zustaende entscheiden,
// ob `useApplyStoredLocale` ihn anwenden darf — beide bewusst im Modul und
// nicht in einem Hook-Ref: der Hook haengt an `AppLayout` und wird bei
// Logout/Login neu gemountet, ein Ref waere dann leer und die Regel liefe ins
// Leere. Ebenso bewusst nicht in localStorage: der Sprachdetektor cached dort
// schon beim Init, ein Cache-Eintrag belegt also keine bewusste Entscheidung.
let explicitLocaleChoice = false
let lastLocaleUser: string | undefined

/** Nur `useLocale().setLocale` ruft das — ab hier gewinnt die Wahl des Nutzers. */
export function markExplicitLocaleChoice(): void {
  explicitLocaleChoice = true
}

/**
 * Darf die gespeicherte Praeferenz fuer `userId` jetzt angewandt werden?
 *
 * - Derselbe User wie beim letzten Mal → nein (einmal pro Person genuegt).
 * - Ein ANDERER User (Logout → anderer Login) → ja; die Wahl der vorigen
 *   Person gilt fuer die neue nicht, das Flag wird zurueckgesetzt.
 * - Erste Person in diesem Tab → nur, wenn noch nichts gewaehlt wurde. Der
 *   Session-Bootstrap ist asynchron, der Umschalter im Header ist also oft
 *   schneller bedient als `session.user` eintrifft.
 *
 * Nicht idempotent: der Aufruf merkt sich `userId`.
 */
export function shouldApplyStoredLocale(userId: string): boolean {
  if (lastLocaleUser === userId) {
    return false
  }
  const isUserSwitch = lastLocaleUser !== undefined
  lastLocaleUser = userId
  if (isUserSwitch) {
    explicitLocaleChoice = false
    return true
  }
  return !explicitLocaleChoice
}

/** Nur fuer Tests: beide Zustaende auf den Startwert zuruecksetzen. */
export function resetLocaleChoiceState(): void {
  explicitLocaleChoice = false
  lastLocaleUser = undefined
}
