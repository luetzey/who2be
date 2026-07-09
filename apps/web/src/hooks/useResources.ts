import { useCallback } from 'react'

import type { Resource } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

// `agent` (WP-B) filtert serverseitig — ein Wechsel des Werts aendert den
// Loader (useCallback-Dependency) und loest damit einen Refetch aus.
export function useResources(agent?: string) {
  const api = useApi()
  const loader = useCallback(
    () => api.listResources(agent ? { agent } : undefined),
    [api, agent],
  )
  const { data, loading, error, reload } = useListData<Resource>(loader)
  return { resources: data, loading, error, reload }
}
