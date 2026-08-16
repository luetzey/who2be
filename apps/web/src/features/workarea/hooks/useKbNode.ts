import { useCallback, useEffect, useState } from 'react'

import type { KbNeighbor, KbNode } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

export interface UseKbNodeResult {
  node: KbNode | null
  neighbors: KbNeighbor[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Ein KB-Node samt seiner Nachbarn (Muster `usePersona`: zwei Reads, ein Zustand).
 *
 * Die Nachbarn kommen ueber den Anker `node:<id>` — dieselbe Anker-Sprache, die
 * Agenten nutzen. Ein Fehler der Nachbar-Abfrage darf die Aussage selbst nicht
 * verdecken: die Aussage mit ihrem Beleg ist die eigentliche Information, die
 * Verknuepfungen sind Kontext.
 */
export function useKbNode(nodeId: string): UseKbNodeResult {
  const api = useApi()
  const [node, setNode] = useState<KbNode | null>(null)
  const [neighbors, setNeighbors] = useState<KbNeighbor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getKbNode(nodeId)
      .then(async (fetched) => {
        setNode(fetched)
        try {
          setNeighbors(await api.kbNeighbors({ anchor: `node:${nodeId}` }))
        } catch {
          setNeighbors([])
        }
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : i18n.t('workarea:node.loadError'))
      })
      .finally(() => setLoading(false))
  }, [api, nodeId])

  useEffect(load, [load])

  return { node, neighbors, loading, error, reload: load }
}
