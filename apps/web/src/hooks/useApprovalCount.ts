import { useEffect, useState } from 'react'

import type { Api } from '@/api/client'
import type { MemoryFilter } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'

/**
 * Zahl der Warteschlange „Zur Freigabe“ — die EINE Quelle fuer den Tab-Zaehler
 * auf `/memory` und den Dashboard-Banner (Gedaechtnisverwaltung §11.1):
 * `status=pending` (der Server schliesst Lernvorschlaege dort aus) plus offene
 * Aenderungs-/Loeschvorschlaege. Viewer zaehlen nur das eigene
 * Nutzergedaechtnis (`scope=user`, wie `useApprovalQueue`); fremdes
 * Nutzergedaechtnis wird nie angefragt, auch nicht als Zahl (ADR-0053 3.1.1).
 */
export async function countApprovalQueue(api: Api, canManageAgents: boolean): Promise<number> {
  const filter: MemoryFilter = { status: 'pending' }
  if (!canManageAgents) filter.scope = 'user'
  const [pending, proposals] = await Promise.all([
    api.countMemories(filter),
    api.listMemoryProposals({ status: 'pending' }),
  ])
  const open = proposals.filter((proposal) => proposal.status === 'pending').length
  return pending.total + open
}

/**
 * Zahl fuer den Dashboard-Banner (Lernschleife C5a-2): dieselbe Menge wie der
 * Tab-Zaehler „Zur Freigabe“. `null`, solange die Rolle fehlt, die Zahl laedt
 * oder nicht ladbar ist — dann behauptet das Dashboard nichts.
 */
export function useApprovalCount(): number | null {
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  // Ergebnis samt Anfrage-Schluessel: eine Zahl fuer eine andere Rolle oder
  // einen anderen Workspace gilt nicht (kein Zuruecksetzen im Effekt noetig).
  const [result, setResult] = useState<{ api: Api; role: string; total: number | null } | null>(
    null,
  )

  useEffect(() => {
    if (role === null) return
    let cancelled = false
    countApprovalQueue(api, role !== 'viewer')
      .then((total) => {
        if (!cancelled) setResult({ api, role, total })
      })
      .catch(() => {
        if (!cancelled) setResult({ api, role, total: null })
      })
    return () => {
      cancelled = true
    }
  }, [api, role])

  if (result === null || result.api !== api || result.role !== role) return null
  return result.total
}
