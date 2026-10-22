import { useCallback, useEffect, useState } from 'react'

/**
 * Cookie-Hinweis — **keine** Einwilligungs-Wahl mehr.
 *
 * Die App laedt kein Analytics/Tracking und nutzt ausschliesslich technisch
 * notwendige Speicherung (Session/Auth, Sprache, Darstellung). Gemessen
 * (Audit A5): kein Request an Dritte beim Erstbesuch und keiner nach der
 * frueheren Wahl „Alle akzeptieren“, kein einziges Cookie. Die fruehere
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
 * Gespeicherte Werte, die als „erledigt“ gelten. `accepted`/`rejected` stammen
 * aus der Zeit mit zwei Knoepfen: wer damals entschieden hat, bekommt den
 * Hinweis nicht erneut.
 */
const DECIDED_VALUES: ReadonlySet<string> = new Set([ACKNOWLEDGED_VALUE, 'accepted', 'rejected'])

function readAcknowledged(): boolean {
  try {
    const value = window.localStorage.getItem(CONSENT_STORAGE_KEY)
    return value !== null && DECIDED_VALUES.has(value)
  } catch {
    // Private-Mode / blockierter Storage → wie „noch nicht gesehen“.
    return false
  }
}

/**
 * Fenster-Event, mit dem `acknowledge` die Bestaetigung im **selben** Tab an
 * alle anderen Hook-Instanzen meldet. Das `storage`-Event feuert nur in
 * anderen Tabs; ohne dieses Signal bliebe z. B. die Begruessung (Onboarding
 * P6), die auf den Hinweis wartet, bis zum Neuladen zu.
 */
export const CONSENT_ACKNOWLEDGED_EVENT = 'who2be:cookie-consent-acknowledged'

export function useCookieConsent() {
  const [isDecided, setIsDecided] = useState<boolean>(() => readAcknowledged())

  // Zweiter Tab/Fenster: Kenntnisnahme dort uebernehmen, damit das Banner
  // nicht doppelt erscheint. Im selben Tab kommt sie ueber das eigene Event —
  // direkt als `true`, damit sie auch ohne Storage (Private-Mode) ankommt.
  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === CONSENT_STORAGE_KEY) {
        setIsDecided(readAcknowledged())
      }
    }
    function onAcknowledged() {
      setIsDecided(true)
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener(CONSENT_ACKNOWLEDGED_EVENT, onAcknowledged)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener(CONSENT_ACKNOWLEDGED_EVENT, onAcknowledged)
    }
  }, [])

  const acknowledge = useCallback(() => {
    setIsDecided(true)
    try {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, ACKNOWLEDGED_VALUE)
    } catch {
      // Persistenz best-effort; das State-Update haelt das Banner im Tab fern.
    }
    window.dispatchEvent(new Event(CONSENT_ACKNOWLEDGED_EVENT))
  }, [])

  return { isDecided, acknowledge }
}
