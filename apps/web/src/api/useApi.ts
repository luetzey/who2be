import { useMemo } from 'react'

import { useSession } from '../auth/session-context'
import { type Api, createApi } from './client'

export function useApi(): Api {
  const { session } = useSession()
  const token = session?.access_token ?? ''
  return useMemo(() => createApi(token), [token])
}
