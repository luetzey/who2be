import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { DashboardData } from '@/api/types'
import { useApi } from '@/api/useApi'

interface UseDashboardResult {
  data: DashboardData | null
  loading: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

/**
 * Laedt das Dashboard-Aggregat fuer den aktuellen Workspace. Backend
 * (Phase 2.1b-A/B) ist noch nicht gemergt — ein 404 wird hier explizit
 * als `notFound` ausgewiesen, damit die Page einen sauberen Empty-State
 * zeigt und keinen roten Error-Alert.
 */
export function useDashboard(): UseDashboardResult {
  const api = useApi()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    setNotFound(false)
    api
      .getDashboard()
      .then((result) => setData(result))
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) {
          setNotFound(true)
          setData(null)
          return
        }
        setError(describeError(cause))
      })
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { data, loading, error, notFound, reload: load }
}
