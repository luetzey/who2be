import { useCallback, useEffect, useState } from 'react'

import type { SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseSystemPromptsResult {
  templates: SystemPromptTemplate[]
  loading: boolean
  error: string | null
  reload: () => void
}

// `locale` (ADR-0045) filtert serverseitig — ein Wechsel des Werts aendert
// den Loader (useCallback-Dependency) und loest damit einen Refetch aus.
export function useSystemPrompts(locale?: string): UseSystemPromptsResult {
  const api = useApi()
  const [templates, setTemplates] = useState<SystemPromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listSystemPromptTemplates(locale ? { locale } : undefined)
      .then(setTemplates)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, locale])

  useEffect(load, [load])

  return { templates, loading, error, reload: load }
}
