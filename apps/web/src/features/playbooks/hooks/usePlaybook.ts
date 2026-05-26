import { useCallback, useEffect, useState } from 'react'

import type { Playbook, PlaybookVersion } from '@/api/types'
import { useApi } from '@/api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePlaybookResult {
  playbook: Playbook | null
  versions: PlaybookVersion[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt Playbook + Version-History fuer eine gegebene Playbook-ID.
 * `id === undefined` ist Routing-Glue-Sache der Page (`<Navigate/>`).
 */
export function usePlaybook(id: string | undefined): UsePlaybookResult {
  const api = useApi()
  const [playbook, setPlaybook] = useState<Playbook | null>(null)
  const [versions, setVersions] = useState<PlaybookVersion[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.getPlaybook(id), api.listPlaybookVersions(id)])
      .then(([loaded, versionList]) => {
        setPlaybook(loaded)
        setVersions(versionList)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { playbook, versions, loading, error, reload: load }
}
