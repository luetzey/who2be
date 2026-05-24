import { useCallback } from 'react'

import type { Persona } from '../api/types'
import { useApi } from '../api/useApi'
import { useListData } from './useListData'

export function usePersonas() {
  const api = useApi()
  const loader = useCallback(() => api.listPersonas(), [api])
  const { data, loading, error, reload } = useListData<Persona>(loader)
  return { personas: data, loading, error, reload }
}
