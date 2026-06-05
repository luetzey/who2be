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

export default i18n
