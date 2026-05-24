import { useMemo } from 'react'

import { useAuthToken } from '../auth/useAuthToken'
import { type Api, createApi } from './client'

export function useApi(): Api {
  const token = useAuthToken()
  return useMemo(() => createApi(token), [token])
}
