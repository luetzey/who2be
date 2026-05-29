import { useCallback } from 'react'

import type { Resource } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

export function useResources() {
  const api = useApi()
  const loader = useCallback(() => api.listResources(), [api])
  const { data, loading, error, reload } = useListData<Resource>(loader)
  return { resources: data, loading, error, reload }
}
