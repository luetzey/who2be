import { useCallback } from 'react'

import type { Member } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

export function useMembers() {
  const api = useApi()
  const loader = useCallback(() => api.listMembers(), [api])
  const { data, loading, error, reload } = useListData<Member>(loader)
  return { members: data, loading, error, reload }
}
