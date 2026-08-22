import { useCallback, useEffect, useState } from 'react'
import '../i18n'

import { ApiError } from '@/api/client'
import type { EntitlementInfo } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

interface UseEntitlementResult {
  data: EntitlementInfo | null
  loading: boolean
  error: string | null
  notFound: boolean
  reload: () => void
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

/**
 * Laedt das aufgeloeste Org-Entitlement + den MCP-Verbrauch fuer den
 * Billing-Slot (Track D). Der Endpoint ist On-Prem zwar vorhanden, liefert dort
 * aber `edition='onprem'` — das Panel blendet sich dann selbst aus. Ein 404
 * (aelteres Backend ohne Track D) wird als `notFound` ausgewiesen, damit die
 * UI einen ruhigen Empty-State statt eines roten Alerts zeigt.
 */
export function useEntitlement(): UseEntitlementResult {
  const api = useApi()
  const [data, setData] = useState<EntitlementInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    setNotFound(false)
    api
      .getEntitlement()
      .then((result) => setData(result))
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 404) {
          setNotFound(true)
          setData(null)
          return
        }
        setError(describeError(cause))
      })
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { data, loading, error, notFound, reload: load }
}
