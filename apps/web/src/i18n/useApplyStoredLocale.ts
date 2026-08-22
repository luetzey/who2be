import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { useSession } from '@/auth/session-context'

import { isLocale, shouldApplyStoredLocale } from './index'

/**
 * Wendet die geraeteuebergreifend gespeicherte Sprachpraeferenz an, sobald eine
 * Session vorliegt. Quelle ist Supabase `user_metadata.preferred_locale`
 * (gesetzt von `useLocale().setLocale`). So folgt die Sprache dem User auf ein
 * neues Geraet, auf dem der localStorage-Cache noch leer ist.
 *
 * OB angewandt werden darf, entscheidet `shouldApplyStoredLocale` — eine Wahl,
 * die der Nutzer in diesem Tab selbst getroffen hat, gewinnt gegen den
 * gespeicherten Wert. Ohne diesen Vorrang kippt die Sprache zurueck: der
 * Session-Bootstrap ist asynchron, und zusaetzlich behaelt
 * `supabase.auth.updateUser` den bestehenden `access_token` bei (es setzt nur
 * `session.user`), waehrend `SessionProvider.apply()` genau auf diesen Token
 * dedupliziert — das `USER_UPDATED`-Event wird verworfen und der Session-State
 * im React-Baum traegt weiter die alte `preferred_locale`.
 */
export function useApplyStoredLocale(): void {
  const { session } = useSession()
  const { i18n } = useTranslation()
  const stored = session?.user?.user_metadata?.preferred_locale as unknown
  const userId = session?.user?.id

  useEffect(() => {
    if (userId === undefined || !shouldApplyStoredLocale(userId)) {
      return
    }
    if (isLocale(stored) && stored !== i18n.resolvedLanguage) {
      void i18n.changeLanguage(stored)
    }
  }, [userId, stored, i18n])
}
