import { useCallback, useEffect, useState } from 'react'

import type { Resource, ResourceVersion } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseResourceResult {
  resource: Resource | null
  versions: ResourceVersion[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt Resource + Version-History fuer eine gegebene Resource-ID.
 * `id === undefined` ist Routing-Glue-Sache der Page (`<Navigate/>`).
 */
export function useResource(id: string | undefined): UseResourceResult {
  const api = useApi()
  const [resource, setResource] = useState<Resource | null>(null)
  const [versions, setVersions] = useState<ResourceVersion[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.getResource(id), api.listResourceVersions(id)])
      .then(([loaded, versionList]) => {
        setResource(loaded)
        setVersions(versionList)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { resource, versions, loading, error, reload: load }
}
