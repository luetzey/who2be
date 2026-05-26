import { useCallback, useEffect, useState } from 'react'

import type { Persona, PersonaVersion } from '@/api/types'
import { useApi } from '@/api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePersonaResult {
  persona: Persona | null
  versions: PersonaVersion[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt Persona + Version-History fuer eine gegebene Persona-ID.
 * Behandlung von `id === undefined` bleibt Sache der Page (`<Navigate/>`).
 */
export function usePersona(id: string | undefined): UsePersonaResult {
  const api = useApi()
  const [persona, setPersona] = useState<Persona | null>(null)
  const [versions, setVersions] = useState<PersonaVersion[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([api.getPersona(id), api.listPersonaVersions(id)])
      .then(([loaded, versionList]) => {
        setPersona(loaded)
        setVersions(versionList)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { persona, versions, loading, error, reload: load }
}
