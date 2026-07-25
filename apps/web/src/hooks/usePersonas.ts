import { useCallback } from 'react'

import type { Persona } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

// `agent` (WP-B) und `locale` (ADR-0045) filtern serverseitig — ein Wechsel
// eines Werts aendert den Loader (useCallback-Dependency) und loest damit
// einen Refetch aus.
export function usePersonas(agent?: string, locale?: string) {
  const api = useApi()
  const loader = useCallback(() => {
    const hasFilter = Boolean(agent) || Boolean(locale)
    return api.listPersonas(
      hasFilter ? { ...(agent ? { agent } : {}), ...(locale ? { locale } : {}) } : undefined,
    )
  }, [api, agent, locale])
  const { data, loading, error, reload } = useListData<Persona>(loader)
  return { personas: data, loading, error, reload }
}
