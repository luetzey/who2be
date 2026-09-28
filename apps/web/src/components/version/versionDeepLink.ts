import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

// Deep-Link in die Pruefansicht (Audit E1 = A): `?tab=versions&diff=<n>`
// oeffnet auf einer Detailseite den Tab „Versions" mit dem Diff der Version
// <n> bereits aufgeklappt. Die URL ist die einzige Quelle fuer den aktiven
// Tab — Statusleiste und Dashboard verlinken nur, sie steuern keinen State.

export const VERSIONS_TAB = 'versions'

/** Query-String, der den Versions-Tab mit dem Diff von `version` oeffnet. */
export function versionDiffSearch(version: number): string {
  return `?tab=${VERSIONS_TAB}&diff=${version}`
}

/** `?diff=` nur als positive Ganzzahl, alles andere wird ignoriert. */
export function parseDiffParam(raw: string | null): number | undefined {
  if (raw === null || !/^[1-9]\d*$/.test(raw)) return undefined
  const value = Number(raw)
  return Number.isSafeInteger(value) ? value : undefined
}

/**
 * Kontrollierter Tab-State einer Detailseite aus der URL. Unbekannte
 * `?tab=`-Werte fallen auf `defaultTab` zurueck. Ein Tab-Wechsel schreibt
 * `tab` (ersetzt den History-Eintrag, damit „Zurueck" die Seite verlaesst
 * statt durch Tabs zu blaettern) und verwirft `diff` — der vorab geoeffnete
 * Diff gilt nur fuer den ersten Aufruf des Links.
 */
export function useVersionDeepLink<T extends string>(
  tabs: readonly T[],
  defaultTab: T,
): { tab: T; setTab: (next: string) => void; diffVersion: number | undefined } {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab = raw !== null && (tabs as readonly string[]).includes(raw) ? (raw as T) : defaultTab
  // Kein eigener Guard auf `tab === versions` noetig: der Diff-Wunsch wirkt
  // nur, wenn der Versions-Tab gemountet ist, und jeder Tab-Wechsel verwirft ihn.
  const diffVersion = parseDiffParam(params.get('diff'))

  const setTab = useCallback(
    (next: string) => {
      setParams(
        (prev) => {
          const updated = new URLSearchParams(prev)
          if (next === defaultTab) updated.delete('tab')
          else updated.set('tab', next)
          updated.delete('diff')
          return updated
        },
        { replace: true },
      )
    },
    [setParams, defaultTab],
  )

  return { tab, setTab, diffVersion }
}
