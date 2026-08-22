import { useCallback, useEffect, useState } from 'react'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface ListDataState<T> {
  data: T[]
  loading: boolean
  error: string | null
  reload: () => void
}

// Generischer Loader-Hook fuer Listen — usePersonas/usePlaybooks/useTokens
// teilten denselben State-Skeleton (load → setData / setError, finally
// setLoading). `loader` muss stable sein (useCallback im Konsumenten),
// sonst rerendert useEffect endlos.
export function useListData<T>(loader: () => Promise<T[]>): ListDataState<T> {
  const [data, setData] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    loader()
      .then(setData)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [loader])

  useEffect(reload, [reload])

  return { data, loading, error, reload }
}
