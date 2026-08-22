import { useCallback, useEffect, useState } from 'react'

import type { SystemPromptTemplate, SystemPromptTemplateVersion } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseSystemPromptResult {
  template: SystemPromptTemplate | null
  versions: SystemPromptTemplateVersion[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useSystemPrompt(id: string | undefined): UseSystemPromptResult {
  const api = useApi()
  const [template, setTemplate] = useState<SystemPromptTemplate | null>(null)
  const [versions, setVersions] = useState<SystemPromptTemplateVersion[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      api.getSystemPromptTemplate(id),
      api.listSystemPromptTemplateVersions(id),
    ])
      .then(([loaded, versionList]) => {
        setTemplate(loaded)
        setVersions(versionList)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { template, versions, loading, error, reload: load }
}
