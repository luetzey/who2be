import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { FeedbackSignal, FeedbackTarget, SystemFeedbackCategory } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Zustand + Absenden der beiden Feedback-Formulare („Feedback geben“,
// „Problem melden“). Die Hooks liegen bei der Huelle (Dialog ab `md`,
// Vollbildseite darunter — Mobil-Spec W4=b), damit der Dialog wie bisher die
// Eingabe ueber Schliessen und Wiederoeffnen behaelt. Die Felder selbst
// rendern `GiveFeedbackForm` bzw. `ReportProblemForm`; eine Form, zwei Huellen.

export interface GiveFeedbackTarget {
  entityType: FeedbackTarget
  entityId: string
  /** Bezugsversion des Feedbacks (i. d. R. `current_version`). */
  version?: number
}

export interface GiveFeedbackFormState {
  signal: FeedbackSignal
  setSignal: (signal: FeedbackSignal) => void
  note: string
  setNote: (note: string) => void
  busy: boolean
  submit: () => Promise<void>
}

/** „Feedback geben“: `onSubmitted` laeuft nur nach Erfolg. */
export function useGiveFeedbackForm(
  { entityType, entityId, version }: GiveFeedbackTarget,
  onSubmitted: () => void,
): GiveFeedbackFormState {
  const { t } = useTranslation('feedback')
  const api = useApi()
  const [signal, setSignal] = useState<FeedbackSignal>('helpful')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await api.submitFeedback({
        entity_type: entityType,
        entity_id: entityId,
        version,
        signal,
        note: note.trim() === '' ? undefined : note.trim(),
      })
      notify.success(t('give.success'))
      setSignal('helpful')
      setNote('')
      onSubmitted()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('give.error'))
    } finally {
      setBusy(false)
    }
  }

  return { signal, setSignal, note, setNote, busy, submit }
}

export interface ReportProblemFormState {
  category: SystemFeedbackCategory
  setCategory: (category: SystemFeedbackCategory) => void
  note: string
  setNote: (note: string) => void
  busy: boolean
  submit: () => Promise<void>
}

/** „Problem melden“: `onSubmitted` laeuft nur nach Erfolg. */
export function useReportProblemForm(onSubmitted: () => void): ReportProblemFormState {
  const { t } = useTranslation('feedback')
  const api = useApi()
  const [category, setCategory] = useState<SystemFeedbackCategory>('technical')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (note.trim() === '') return
    setBusy(true)
    try {
      await api.submitSystemFeedback({ category, note: note.trim() })
      notify.success(t('report.success'))
      setCategory('technical')
      setNote('')
      onSubmitted()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('report.error'))
    } finally {
      setBusy(false)
    }
  }

  return { category, setCategory, note, setNote, busy, submit }
}
