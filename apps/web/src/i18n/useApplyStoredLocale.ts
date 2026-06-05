import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { useSession } from '@/auth/session-context'

import { isLocale } from './index'

/**
 * Wendet die geraeteuebergreifend gespeicherte Sprachpraeferenz an, sobald eine
 * Session vorliegt. Quelle ist Supabase `user_metadata.preferred_locale`
 * (gesetzt von `useLocale().setLocale`). So folgt die Sprache dem User auf ein
 * neues Geraet, auf dem der localStorage-Cache noch leer ist.
 */
export function useApplyStoredLocale(): void {
  const { session } = useSession()
  const { i18n } = useTranslation()
  const stored = session?.user?.user_metadata?.preferred_locale as unknown

  useEffect(() => {
    if (isLocale(stored) && stored !== i18n.resolvedLanguage) {
      void i18n.changeLanguage(stored)
    }
  }, [stored, i18n])
}
