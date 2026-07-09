import { useCallback } from 'react'

import type { Playbook } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

// `agent` (WP-B) filtert serverseitig — ein Wechsel des Werts aendert den
// Loader (useCallback-Dependency) und loest damit einen Refetch aus.
export function usePlaybooks(agent?: string) {
  const api = useApi()
  const loader = useCallback(
    () => api.listPlaybooks(agent ? { agent } : undefined),
    [api, agent],
  )
  const { data, loading, error, reload } = useListData<Playbook>(loader)
  return { playbooks: data, loading, error, reload }
}
