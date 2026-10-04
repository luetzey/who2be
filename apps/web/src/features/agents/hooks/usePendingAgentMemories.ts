import { useEffect, useState } from 'react'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'

const NONE: Record<string, number> = {}

/**
 * Offene Gedaechtnis-Freigaben je Agent fuer die Agentenliste — ein einziger
 * Request `GET /memories/counts?status=pending&scope=agent&group_by=agent`
 * fuer die ganze Liste (ADR-0053 6.4.1 „Zaehler“). Kein `kind`-Filter: `lesson`
 * faellt serverseitig ueber die Warteschlangen-Regel heraus.
 *
 * Agentengedaechtnis sieht erst `editor` (Muster `AgentMemoryCard`): fuer
 * viewer — und solange die Rolle unbekannt ist — geht kein Request raus und
 * die Map bleibt leer. Ein Fehler laesst nur die Pills weg.
 */
export function usePendingAgentMemories(): Record<string, number> {
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const enabled = role !== null && role !== 'viewer'
  const [counts, setCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api
      .countMemories({ status: 'pending', scope: 'agent' }, ['agent'])
      .then((result) => {
        if (!cancelled) setCounts(result.groups?.agent ?? {})
      })
      .catch(() => {
        if (!cancelled) setCounts({})
      })
    return () => {
      cancelled = true
    }
  }, [api, enabled])

  return enabled ? counts : NONE
}
