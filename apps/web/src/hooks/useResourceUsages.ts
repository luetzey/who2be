import { useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { ResourceUsage } from '@/api/types'
import { useApi } from '@/api/useApi'

interface UseResourceUsagesResult {
  usages: ResourceUsage[]
  loading: boolean
  error: string | null
}

// Backlinks "welche Playbooks referenzieren Bloecke dieser Resource?".
// Endpoint `GET /v1/workspaces/{ws}/resources/{id}/usages` kommt aus
// Track A; bis dahin antwortet das Backend mit 404 — behandeln wir als
// leere Liste, damit der EmptyState waehrend der Track-Serialisierung
// rendert (statt Fehler-Banner).
export function useResourceUsages(resourceId: string | undefined): UseResourceUsagesResult {
  const api = useApi()
  const [usages, setUsages] = useState<ResourceUsage[]>([])
  const [loading, setLoading] = useState(resourceId !== undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (resourceId === undefined) {
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getResourceUsages(resourceId)
      .then((result) => {
        if (!cancelled) {
          setUsages(result)
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) {
          return
        }
        if (cause instanceof ApiError && cause.status === 404) {
          setUsages([])
          return
        }
        setError(cause instanceof Error ? cause.message : 'Unbekannter Fehler.')
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [api, resourceId])

  return { usages, loading, error }
}
