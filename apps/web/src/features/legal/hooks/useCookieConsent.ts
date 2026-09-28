import { useCallback, useEffect, useState } from 'react'

/**
 * Cookie-Hinweis — **keine** Einwilligungs-Wahl mehr.
 *
 * Die App laedt kein Analytics/Tracking und nutzt ausschliesslich technisch
 * notwendige Speicherung (Session/Auth, Sprache, Darstellung). Gemessen
 * (Audit A5): kein Request an Dritte beim Erstbesuch und keiner nach der
 * frueheren Wahl „Alle akzeptieren\", kein einziges Cookie. Die fruehere
 * Analytics-Kategorie (`accepted` + `hasAnalyticsConsent`) hatte keinen
 * Verbraucher im Code und ist deshalb entfallen (Owner-Freigabe 2026-09-28).
 *
 * Kommt je ein optionaler Dienst dazu, braucht es wieder eine echte Wahl
 * (Opt-in) mit **benanntem** Dienst — nicht als Platzhalter.
 *
 * Die Kenntnisnahme liegt in `localStorage` (kein Cookie noetig) und ist
 * tab-uebergreifend synchron (storage-Event). `false` = noch nicht gesehen →
 * Banner zeigt sich.
 */
export const CONSENT_STORAGE_KEY = 'who2be:cookie-consent'

/** Wert, den der heutige Banner beim Bestaetigen schreibt. */
export const ACKNOWLEDGED_VALUE = 'acknowledged'

/**
 * Gespeicherte Werte, die als „erledigt\" gelten. `accepted`/`rejected` stammen
 * aus der Zeit mit zwei Knoepfen: wer damals entschieden hat, bekommt den
 * Hinweis nicht erneut.
 */
const DECIDED_VALUES: ReadonlySet<string> = new Set([ACKNOWLEDGED_VALUE, 'accepted', 'rejected'])

function readAcknowledged(): boolean {
  try {
    const value = window.localStorage.getItem(CONSENT_STORAGE_KEY)
    return value !== null && DECIDED_VALUES.has(value)
  } catch {
    // Private-Mode / blockierter Storage → wie „noch nicht gesehen\".
    return false
  }
}

export function useCookieConsent() {
  const [isDecided, setIsDecided] = useState<boolean>(() => readAcknowledged())

  // Zweiter Tab/Fenster: Kenntnisnahme dort uebernehmen, damit das Banner
  // nicht doppelt erscheint.
  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === CONSENT_STORAGE_KEY) {
        setIsDecided(readAcknowledged())
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const acknowledge = useCallback(() => {
    setIsDecided(true)
    try {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, ACKNOWLEDGED_VALUE)
    } catch {
      // Persistenz best-effort; das State-Update haelt das Banner im Tab fern.
    }
  }, [])

  return { isDecided, acknowledge }
}
