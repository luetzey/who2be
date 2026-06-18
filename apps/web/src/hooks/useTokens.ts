import { useCallback } from 'react'

import type { Token } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

export function useTokens() {
  const api = useApi()
  const loader = useCallback(() => api.listTokens(), [api])
  const { data, loading, error, reload } = useListData<Token>(loader)
  return { tokens: data, loading, error, reload }
}

/** Tokens eines einzelnen Agenten (Agent-Konfig-Sektion). */
export function useAgentTokens(agentId: string) {
  const api = useApi()
  const loader = useCallback(() => api.listTokens({ agentId }), [api, agentId])
  const { data, loading, error, reload } = useListData<Token>(loader)
  return { tokens: data, loading, error, reload }
}
