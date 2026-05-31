import { useCallback, useEffect, useState } from 'react'

import type { SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseSystemPromptsResult {
  templates: SystemPromptTemplate[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useSystemPrompts(): UseSystemPromptsResult {
  const api = useApi()
  const [templates, setTemplates] = useState<SystemPromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listSystemPromptTemplates()
      .then(setTemplates)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { templates, loading, error, reload: load }
}
