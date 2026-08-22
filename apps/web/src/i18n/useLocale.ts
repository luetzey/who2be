import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import { supabase } from '@/lib/supabase'

import {
  DEFAULT_LOCALE,
  isLocale,
  type Locale,
  markExplicitLocaleChoice,
  SUPPORTED_LOCALES,
} from './index'

interface UseLocaleResult {
  locale: Locale
  locales: readonly Locale[]
  setLocale: (locale: Locale) => void
}

/**
 * Aktive Locale + Umschalter. `setLocale` schaltet die UI sofort um (i18next),
 * der Sprachdetektor cached die Wahl im localStorage (Geraete-Cache). Zusaetzlich
 * wird die Praeferenz best-effort in Supabase `user_metadata.preferred_locale`
 * geschrieben, damit sie dem User geraeteuebergreifend folgt (siehe
 * docs/frontend/i18n.md). Fehlt eine Session, bleibt es beim localStorage-Cache.
 */
export function useLocale(): UseLocaleResult {
  const { i18n } = useTranslation()
  const current = isLocale(i18n.resolvedLanguage) ? i18n.resolvedLanguage : DEFAULT_LOCALE

  const setLocale = useCallback(
    (locale: Locale) => {
      // Vor dem Umschalten markieren: ab jetzt hat die Wahl des Nutzers Vorrang
      // vor der serverseitig gespeicherten Praeferenz (siehe useApplyStoredLocale).
      markExplicitLocaleChoice()
      void i18n.changeLanguage(locale)
      void supabase.auth
        .updateUser({ data: { preferred_locale: locale } })
        .catch(() => {
          // Kein Login / offline — der localStorage-Cache reicht.
        })
    },
    [i18n],
  )

  return { locale: current, locales: SUPPORTED_LOCALES, setLocale }
}
