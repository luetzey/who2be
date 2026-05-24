import { useCallback } from 'react'

import type { Playbook } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

export function usePlaybooks() {
  const api = useApi()
  const loader = useCallback(() => api.listPlaybooks(), [api])
  const { data, loading, error, reload } = useListData<Playbook>(loader)
  return { playbooks: data, loading, error, reload }
}
