import { useEffect, useState } from 'react'

// Standard-Verzoegerung fuer Server-Suchen. 300 ms ist der uebliche Kompromiss:
// kurz genug, dass sich die Suche live anfuehlt, lang genug, dass Tippen nicht
// pro Anschlag einen Request ausloest.
const DEFAULT_DELAY_MS = 300

/**
 * Gibt `value` verzoegert zurueck — jede Aenderung startet die Wartezeit neu.
 *
 * Gedacht fuer serverseitige Freitext-Suchen: der Roh-Wert bleibt im Input
 * (die Eingabe fuehlt sich sofort an), der verzoegerte Wert geht in die
 * `useCallback`-Dependency des Daten-Hooks und loest damit den Refetch aus.
 * Bewusst OHNE `flush()` (anders als `useAutoSaveDraft`): ein verworfener
 * Suchlauf kostet nichts, ein verworfener Entwurf waere Datenverlust.
 */
export function useDebouncedValue<T>(value: T, delayMs: number = DEFAULT_DELAY_MS): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebounced(value)
    }, delayMs)
    return () => {
      clearTimeout(timeout)
    }
  }, [value, delayMs])

  return debounced
}
