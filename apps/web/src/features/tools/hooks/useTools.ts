import { useCallback } from 'react'

import type { ExternalTool } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

// Kein Agent-Facetten-Filter (anders als `useResources`/`usePlaybooks`) — die
// Backend-Surface (`GET .../external_tools`) traegt WP-4 (noch) kein
// `?agent=`-Query (siehe `apps/api/tests/contract/openapi_surface.json`).
// `locale` (ADR-0045) filtert serverseitig — ein Wechsel des Werts aendert
// den Loader (useCallback-Dependency) und loest damit einen Refetch aus.
export function useTools(locale?: string) {
  const api = useApi()
  const loader = useCallback(
    () => api.listExternalTools(locale ? { locale } : undefined),
    [api, locale],
  )
  const { data, loading, error, reload } = useListData<ExternalTool>(loader)
  return { tools: data, loading, error, reload }
}
