import { useCallback } from 'react'

import type { Persona } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

// `agent` (WP-B) filtert serverseitig — ein Wechsel des Werts aendert den
// Loader (useCallback-Dependency) und loest damit einen Refetch aus.
export function usePersonas(agent?: string) {
  const api = useApi()
  const loader = useCallback(
    () => api.listPersonas(agent ? { agent } : undefined),
    [api, agent],
  )
  const { data, loading, error, reload } = useListData<Persona>(loader)
  return { personas: data, loading, error, reload }
}
