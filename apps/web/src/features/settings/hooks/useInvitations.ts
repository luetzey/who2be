import { useCallback } from 'react'

import type { Invitation } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useListData } from '@/hooks/useListData'

export function useInvitations() {
  const api = useApi()
  const loader = useCallback(() => api.listInvitations(), [api])
  const { data, loading, error, reload } = useListData<Invitation>(loader)
  return { invitations: data, loading, error, reload }
}
