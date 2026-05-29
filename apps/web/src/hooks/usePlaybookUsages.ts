import { useEffect, useState } from 'react'

import { ApiError } from '@/api/client'
import type { PlaybookUsage } from '@/api/types'
import { useApi } from '@/api/useApi'

interface UsePlaybookUsagesResult {
  usages: PlaybookUsage[]
  loading: boolean
  error: string | null
}

// Backlinks "welche Personas referenzieren dieses Playbook?".
// Endpoint `GET /v1/workspaces/{ws}/playbooks/{id}/usages` kommt aus
// Track A; bis dahin antwortet das Backend mit 404 — wir behandeln das
// als leere Liste (kein Fehler-Banner, EmptyState reicht).
export function usePlaybookUsages(playbookId: string | undefined): UsePlaybookUsagesResult {
  const api = useApi()
  const [usages, setUsages] = useState<PlaybookUsage[]>([])
  const [loading, setLoading] = useState(playbookId !== undefined)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (playbookId === undefined) {
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getPlaybookUsages(playbookId)
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
  }, [api, playbookId])

  return { usages, loading, error }
}
