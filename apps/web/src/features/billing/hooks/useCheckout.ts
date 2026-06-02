import { useCallback, useState } from 'react'

import { useApi } from '@/api/useApi'

interface UseCheckoutResult {
  start: (plan: string) => void
  pending: boolean
  error: string | null
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Checkout fehlgeschlagen.'
}

/**
 * Startet einen Mollie-Checkout (Track J) und leitet bei Erfolg auf die
 * Hosted-Checkout-URL weiter. `pending` bleibt nach Erfolg gesetzt, weil der
 * Browser bereits navigiert — nur im Fehlerfall wird es zurueckgesetzt.
 */
export function useCheckout(): UseCheckoutResult {
  const api = useApi()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(
    (plan: string) => {
      setPending(true)
      setError(null)
      api
        .createCheckout({ plan })
        .then((result) => {
          window.location.href = result.checkout_url
        })
        .catch((cause: unknown) => {
          setError(describeError(cause))
          setPending(false)
        })
    },
    [api],
  )

  return { start, pending, error }
}
