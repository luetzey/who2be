import { useCallback } from 'react'

import type { MemoryRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

/**
 * Alle Gedächtnis-Eintraege eines Agenten (ADR-0044), ungefiltert geladen —
 * die Sektion trennt pending/active/rejected clientseitig, damit Triage-
 * Block, aktive Liste und eingeklappte Rejected-Liste aus einem einzigen
 * Request gespeist werden (Muster `useAgentTokens`).
 */
export function useAgentMemories(agentId: string) {
  const api = useApi()
  const loader = useCallback(() => api.listAgentMemories(agentId), [api, agentId])
  const { data, loading, error, reload } = useListData<MemoryRead>(loader)
  return { memories: data, loading, error, reload }
}
