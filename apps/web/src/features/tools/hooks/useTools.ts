import { useCallback } from 'react'

import type { ExternalTool } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

// Kein Agent-Facetten-Filter (anders als `useResources`/`usePlaybooks`) — die
// Backend-Surface (`GET .../external_tools`) traegt WP-4 (noch) kein
// `?agent=`-Query (siehe `apps/api/tests/contract/openapi_surface.json`).
export function useTools() {
  const api = useApi()
  const loader = useCallback(() => api.listExternalTools(), [api])
  const { data, loading, error, reload } = useListData<ExternalTool>(loader)
  return { tools: data, loading, error, reload }
}
