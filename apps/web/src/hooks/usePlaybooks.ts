import { useCallback, useEffect, useState } from 'react'

import type { Playbook } from '../api/types'
import { useApi } from '../api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

interface PlaybooksState {
  playbooks: Playbook[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function usePlaybooks(tag: string, trigger: string): PlaybooksState {
  const api = useApi()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listPlaybooks({ tag: tag || undefined, trigger: trigger || undefined })
      .then(setPlaybooks)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, tag, trigger])

  useEffect(reload, [reload])

  return { playbooks, loading, error, reload }
}
