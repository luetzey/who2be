import { useCallback, useEffect, useState } from 'react'

import type { FeedbackDetail } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseFeedbackDetailResult {
  detail: FeedbackDetail | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt die Detailsicht auf EIN Feedback (`GET …/feedback/{feedbackId}`):
 * alle FeedbackItem-Felder + menschlicher Absender (`actor_id`) +
 * vollstaendige Triage-Historie. Datenquelle der Einzel-Feedback-Detailseite.
 *
 * Read-only + `reload` — die Mutationen (Triage/Delete) liegen in der Page
 * (rufen `useApi()` direkt) und rufen danach `reload`, damit der Verlauf
 * das neue Ereignis spiegelt. Editor-gated; ein 404 (fremdes/geloeschtes
 * Feedback) landet als `error` in `DataView`.
 */
export function useFeedbackDetail(feedbackId: string | undefined): UseFeedbackDetailResult {
  const api = useApi()
  const [detail, setDetail] = useState<FeedbackDetail | null>(null)
  const [loading, setLoading] = useState(feedbackId !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (feedbackId === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    api
      .getFeedbackDetail(feedbackId)
      .then(setDetail)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, feedbackId])

  useEffect(load, [load])

  return { detail, loading, error, reload: load }
}
