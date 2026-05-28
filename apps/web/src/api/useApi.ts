import { useMemo } from 'react'

import { useAuthToken } from '../auth/useAuthToken'
import { useWorkspaceId } from '../auth/useWorkspaceId'
import { type Api, createApi } from './client'

export function useApi(): Api {
  const token = useAuthToken()
  const workspaceId = useWorkspaceId()
  return useMemo(() => createApi(token, workspaceId), [token, workspaceId])
}
