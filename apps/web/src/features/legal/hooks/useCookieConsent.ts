import { useCallback, useEffect, useState } from 'react'

/**
 * Cookie-/Tracking-Einwilligung — **Opt-in**: Ohne ausdrueckliche Zustimmung
 * wird **kein** Tracking/Analytics geladen. Es werden ausschliesslich technisch
 * notwendige Cookies (Session/Auth) gesetzt, die keiner Einwilligung beduerfen.
 *
 * Die Entscheidung liegt in `localStorage` (kein Cookie noetig) und ist
 * tab-uebergreifend synchron (storage-Event). `null` = noch nicht entschieden →
 * Banner zeigt sich.
 */
export type ConsentDecision = 'accepted' | 'rejected'

export const CONSENT_STORAGE_KEY = 'who2be:cookie-consent'

function readConsent(): ConsentDecision | null {
  try {
    const value = window.localStorage.getItem(CONSENT_STORAGE_KEY)
    return value === 'accepted' || value === 'rejected' ? value : null
  } catch {
    // Private-Mode / blockierter Storage → wie „noch nicht entschieden".
    return null
  }
}

/**
 * Gate fuer optionale Analytics/Tracking-Integrationen. Erst `true`, wenn der
 * Nutzer aktiv zugestimmt hat — bis dahin darf nichts geladen werden.
 */
export function hasAnalyticsConsent(): boolean {
  return readConsent() === 'accepted'
}

export function useCookieConsent() {
  const [decision, setDecision] = useState<ConsentDecision | null>(() => readConsent())

  // Zweiter Tab/Fenster: Entscheidung dort uebernehmen, damit das Banner nicht
  // doppelt erscheint.
  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === CONSENT_STORAGE_KEY) {
        setDecision(readConsent())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const decide = useCallback((next: ConsentDecision) => {
    setDecision(next)
    try {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, next)
    } catch {
      // Persistenz best-effort; das State-Update haelt das Banner im Tab fern.
    }
  }, [])

  return {
    decision,
    isDecided: decision !== null,
    accept: useCallback(() => decide('accepted'), [decide]),
    reject: useCallback(() => decide('rejected'), [decide]),
  }
}
