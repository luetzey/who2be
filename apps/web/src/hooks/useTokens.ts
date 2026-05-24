import { useCallback, useEffect, useState } from 'react'

import type { Token } from '../api/types'
import { useApi } from '../api/useApi'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

interface TokensState {
  tokens: Token[]
  loading: boolean
  error: string | null
  reload: () => void
}

export function useTokens(): TokensState {
  const api = useApi()
  const [tokens, setTokens] = useState<Token[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .listTokens()
      .then(setTokens)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(reload, [reload])

  return { tokens, loading, error, reload }
}
