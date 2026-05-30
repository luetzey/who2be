import { useCallback, useEffect, useState } from 'react'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseAgentsResult {
  agents: Agent[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useAgents(): UseAgentsResult {
  const api = useApi()
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listAgents()
      .then(setAgents)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { agents, loading, error, reload: load }
}
