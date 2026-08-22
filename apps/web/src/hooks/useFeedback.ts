import { useCallback, useEffect, useState } from 'react'

import type {
  FeedbackEvents,
  FeedbackItems,
  FeedbackOverview,
  FeedbackResolution,
  FeedbackSummary,
  FeedbackTarget,
  FeedbackUnused,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('common:errors.unknown')
}

export interface UseFeedbackResult {
  summary: FeedbackSummary | null
  loading: boolean
  error: string | null
  reload: () => void
  // Drill-down: Einzel-Ereignisse werden erst auf Anforderung geladen (lazy).
  events: FeedbackEvents | null
  eventsLoading: boolean
  eventsError: string | null
  loadEvents: () => void
  // Triage: setzt den Status eines Feedback-Eintrags (optional mit Notiz) und
  // laedt die Liste neu.
  setResolution: (
    feedbackId: string,
    resolution: FeedbackResolution,
    note?: string,
  ) => Promise<void>
  // Hard-Delete (editor+): loescht den Eintrag und laedt Aggregat + Events neu.
  deleteFeedback: (feedbackId: string) => Promise<void>
}

/**
 * Laedt das Feedback-Aggregat (`summary`) eines Elements und — auf Anforderung —
 * die Einzel-Ereignisse (`events`). Beide Endpunkte sind editor-gated; die Page
 * rendert das Panel nur fuer editor+, daher faengt der Hook 403 nur defensiv ab.
 */
export function useFeedback(type: FeedbackTarget, id: string | undefined): UseFeedbackResult {
  const api = useApi()
  const [summary, setSummary] = useState<FeedbackSummary | null>(null)
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)
  const [events, setEvents] = useState<FeedbackEvents | null>(null)
  const [eventsLoading, setEventsLoading] = useState(false)
  const [eventsError, setEventsError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    api
      .getFeedback(type, id)
      .then(setSummary)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, type, id])

  useEffect(load, [load])

  const loadEvents = useCallback(() => {
    if (id === undefined) {
      return
    }
    setEventsLoading(true)
    setEventsError(null)
    api
      .getFeedbackEvents(type, id)
      .then(setEvents)
      .catch((cause: unknown) => setEventsError(describeError(cause)))
      .finally(() => setEventsLoading(false))
  }, [api, type, id])

  const setResolution = useCallback(
    async (feedbackId: string, resolution: FeedbackResolution, note?: string) => {
      await api.setFeedbackResolution(feedbackId, note !== undefined ? { resolution, note } : { resolution })
      // Aggregat (recent_feedback/Zaehler) UND Drill-down spiegeln die Triage.
      load()
      loadEvents()
    },
    [api, load, loadEvents],
  )

  const deleteFeedback = useCallback(
    async (feedbackId: string) => {
      await api.deleteFeedback(feedbackId)
      // Aggregat (Zaehler) UND Drill-down spiegeln den Wegfall.
      load()
      loadEvents()
    },
    [api, load, loadEvents],
  )

  return {
    summary,
    loading,
    error,
    reload: load,
    events,
    eventsLoading,
    eventsError,
    loadEvents,
    setResolution,
    deleteFeedback,
  }
}

export interface UseFeedbackOverviewResult {
  overview: FeedbackOverview | null
  loading: boolean
  error: string | null
  reload: () => void
}

/** Laedt die workspace-weite Kurations-Uebersicht (Dashboard-Kacheln + Seite). */
export function useFeedbackOverview(): UseFeedbackOverviewResult {
  const api = useApi()
  const [overview, setOverview] = useState<FeedbackOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getFeedbackOverview()
      .then(setOverview)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { overview, loading, error, reload: load }
}

export interface UseFeedbackItemsResult {
  data: FeedbackItems | null
  loading: boolean
  error: string | null
  reload: () => void
  // Inline-Triage aus dem Posteingang: setzt den Status + laedt die Liste neu.
  setResolution: (feedbackId: string, resolution: FeedbackResolution) => Promise<void>
  // Hard-Delete (editor+): loescht den Eintrag und laedt den Posteingang neu.
  deleteFeedback: (feedbackId: string) => Promise<void>
}

/** Laedt den workspace-weiten Feedback-Posteingang (alle Eintraege + Status-Zaehler). */
export function useFeedbackItems(): UseFeedbackItemsResult {
  const api = useApi()
  const [data, setData] = useState<FeedbackItems | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getFeedbackItems()
      .then(setData)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  const setResolution = useCallback(
    async (feedbackId: string, resolution: FeedbackResolution) => {
      await api.setFeedbackResolution(feedbackId, { resolution })
      load()
    },
    [api, load],
  )

  const deleteFeedback = useCallback(
    async (feedbackId: string) => {
      await api.deleteFeedback(feedbackId)
      load()
    },
    [api, load],
  )

  return { data, loading, error, reload: load, setResolution, deleteFeedback }
}

export interface UseFeedbackUnusedResult {
  unused: FeedbackUnused | null
  loading: boolean
  error: string | null
  reload: () => void
}

/** Laedt die veroeffentlichten, aber ungenutzten Elemente (Stale-Kandidaten). */
export function useFeedbackUnused(): UseFeedbackUnusedResult {
  const api = useApi()
  const [unused, setUnused] = useState<FeedbackUnused | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .getFeedbackUnused()
      .then(setUnused)
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api])

  useEffect(load, [load])

  return { unused, loading, error, reload: load }
}
