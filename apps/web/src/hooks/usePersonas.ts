import { useCallback, useEffect, useState } from 'react'

import type { Persona } from '../api/types'
import { useApi } from '../api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

interface PersonasState {
  personas: Persona[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function usePersonas(): PersonasState {
  const api = useApi()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listPersonas()
      .then(setPersonas)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(reload, [reload])

  return { personas, loading, error, reload }
}
