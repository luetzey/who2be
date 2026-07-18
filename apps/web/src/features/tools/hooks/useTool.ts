import { useCallback, useEffect, useState } from 'react'

import type { ExternalTool, ExternalToolVersion } from '@/api/types'
import { useApi } from '@/api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseToolResult {
  tool: ExternalTool | null
  versions: ExternalToolVersion[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt ein externes Tool + Version-History fuer eine gegebene ID. Spiegelt
 * `features/resources/hooks/useResource.ts` 1:1.
 * `id === undefined` ist Routing-Glue-Sache der Page (`<Navigate/>`).
 */
export function useTool(id: string | undefined): UseToolResult {
  const api = useApi()
  const [tool, setTool] = useState<ExternalTool | null>(null)
  const [versions, setVersions] = useState<ExternalToolVersion[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.getExternalTool(id), api.listExternalToolVersions(id)])
      .then(([loaded, versionList]) => {
        setTool(loaded)
        setVersions(versionList)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { tool, versions, loading, error, reload: load }
}
