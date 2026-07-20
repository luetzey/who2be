import { ChevronDown, MessageSquarePlus, SquarePen, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'

import type {
  FeedbackResolution,
  FeedbackSignal,
  FeedbackTarget,
  UsageOutcome,
} from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner, DetailHeader, MetaPill } from '@/components/data'
import { DataView } from '@/components/data/DataView'
import { DeleteFeedbackButton } from '@/components/feedback/DeleteFeedbackButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useFeedback } from '@/hooks/useFeedback'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import { DETAIL_SEGMENT, entityMeta } from '../lib/entityMeta'
import { ResolutionSegments } from '../components/ResolutionSegments'

const TARGETS: readonly FeedbackTarget[] = ['persona', 'playbook', 'resource']
const OUTCOMES: readonly UsageOutcome[] = ['applied', 'skipped', 'error']
const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']
const NEGATIVE_SIGNALS: readonly FeedbackSignal[] = ['outdated', 'incorrect', 'unclear']

const OUTCOME_BAR: Record<UsageOutcome, string> = {
  applied: 'bg-brand',
  skipped: 'bg-muted-foreground/40',
  error: 'bg-destructive',
}
const SIGNAL_BAR: Record<FeedbackSignal, string> = {
  helpful: 'bg-brand',
  outdated: 'bg-destructive/70',
  incorrect: 'bg-destructive',
  unclear: 'bg-muted-foreground/50',
}

// Beschriftete Mini-Meter-Zeile (Label · Balken · Zahl) — geteilt von der
// Nutzungs- und der Signal-Karte.
function MeterRow({
  label,
  value,
  total,
  bar,
  labelWidth,
}: {
  label: string
  value: number
  total: number
  bar: string
  labelWidth: string
}) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className={cn('flex-none', labelWidth)}>{label}</span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
        <span className={cn('block h-full', bar)} style={{ width: `${pct}%` }} />
      </span>
      <span className="w-8 flex-none text-right tabular-nums">{value}</span>
    </div>
  )
}

/**
 * Feedback-Kuration eines einzelnen Elements (ADR-0038): Nutzung/Ergebnis,
 * Signal-Verteilung, negative-Signal-Callout, Kurations-Notiz und die
 * Einzel-Ereignisse mit Inline-Triage. Datenquelle ist `useFeedback` (das
 * bestehende Pro-Element-Aggregat `GET …/feedback/{type}/{id}` + Events).
 */
export function FeedbackDetailPage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { entityType, entityId } = useParams<{ entityType: string; entityId: string }>()
  const location = useLocation()
  const navState = location.state as { name?: string } | null

  const isValidTarget = TARGETS.includes(entityType as FeedbackTarget)
  const type = entityType as FeedbackTarget

  const {
    summary,
    loading,
    error,
    events,
    eventsLoading,
    loadEvents,
    setResolution,
    deleteFeedback,
  } = useFeedback(isValidTarget ? type : ('persona' as FeedbackTarget), isValidTarget ? entityId : undefined)

  const [showEvents, setShowEvents] = useState(false)
  const [note, setNote] = useState('')
  const [savingNote, setSavingNote] = useState(false)

  const signalTotal = useMemo(
    () => (summary ? SIGNALS.reduce((sum, s) => sum + (summary.by_signal[s] ?? 0), 0) : 0),
    [summary],
  )
  const negativeCount = useMemo(
    () => (summary ? NEGATIVE_SIGNALS.reduce((sum, s) => sum + (summary.by_signal[s] ?? 0), 0) : 0),
    [summary],
  )

  if (!isValidTarget || entityId === undefined) {
    return <Navigate to={wsPath('/feedback')} replace />
  }

  const meta = entityMeta(type)
  const name = navState?.name ?? entityId
  const typeLabel = t(`overview.type.${type}`)
  const elementPath = wsPath(`/${DETAIL_SEGMENT[type]}/${entityId}`)

  const usageCount = summary?.usage_count ?? 0
  const appliedCount = summary?.by_outcome.applied ?? 0
  const successRate = usageCount > 0 ? Math.round((appliedCount / usageCount) * 100) : 0

  // Kurations-Notiz haengt am juengsten offenen Signal (einziger note-tragender
  // Mutations-Endpunkt: setFeedbackResolution). Ohne offenes Signal deaktiviert.
  const noteTarget = summary?.recent_feedback?.find((f) => f.resolution === null) ?? null

  const onSaveNote = async () => {
    if (noteTarget === null || note.trim() === '') return
    setSavingNote(true)
    try {
      await setResolution(noteTarget.id, 'in_progress', note.trim())
      notify.success(t('detail.noteSuccess'))
      setNote('')
    } catch {
      notify.error(t('resolution.error'))
    } finally {
      setSavingNote(false)
    }
  }

  const onResolution = async (feedbackId: string, value: FeedbackResolution) => {
    try {
      await setResolution(feedbackId, value)
    } catch {
      notify.error(t('resolution.error'))
    }
  }

  const toggleEvents = () => {
    if (!showEvents && events === null) loadEvents()
    setShowEvents((v) => !v)
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6">
      <DetailHeader
        icon={meta.icon}
        iconTone={meta.tone}
        title={name}
        backHref={wsPath('/feedback')}
        backLabel={t('overview.title')}
        description={t('detail.description')}
        badges={
          <MetaPill tone={meta.tone} icon={meta.icon}>
            {typeLabel}
          </MetaPill>
        }
        actions={
          <Button asChild variant="outline">
            <Link to={elementPath}>{t('detail.openElement')}</Link>
          </Button>
        }
      />

      <DataView
        loading={loading && summary === null}
        error={error}
        empty={
          !loading &&
          summary !== null &&
          usageCount === 0 &&
          signalTotal === 0 &&
          (summary.recent_notes?.length ?? 0) === 0
        }
        emptyTitle={t('detail.empty')}
      >
        {summary !== null ? (
          <div className="flex flex-col gap-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* Nutzung & Ergebnis */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('detail.usageTitle')}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-semibold tracking-tight tabular-nums">
                      {usageCount}
                    </span>
                    <span className="text-sm text-muted-foreground">{t('detail.usageCount')}</span>
                  </div>
                  <div className="flex flex-col gap-2.5">
                    {OUTCOMES.map((o) => (
                      <MeterRow
                        key={o}
                        label={t(`outcome.${o}`)}
                        value={summary.by_outcome[o] ?? 0}
                        total={usageCount}
                        bar={OUTCOME_BAR[o]}
                        labelWidth="w-24"
                      />
                    ))}
                  </div>
                  <div className="flex items-center justify-between gap-3 border-t pt-3">
                    <span className="text-sm text-muted-foreground">{t('detail.successRate')}</span>
                    <span className="inline-flex items-baseline gap-1.5">
                      <span className="text-lg font-semibold tabular-nums">{successRate}%</span>
                      <span className="text-xs text-muted-foreground">{t('detail.applied')}</span>
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Signale */}
              <Card>
                <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
                  <CardTitle>{t('detail.signalsTitle')}</CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {t('detail.signalsTotal', { count: signalTotal })}
                  </span>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2.5">
                    {SIGNALS.map((s) => (
                      <MeterRow
                        key={s}
                        label={t(`signal.${s}`)}
                        value={summary.by_signal[s] ?? 0}
                        total={signalTotal}
                        bar={SIGNAL_BAR[s]}
                        labelWidth="w-20"
                      />
                    ))}
                  </div>
                  {negativeCount > 0 ? (
                    <AttentionBanner
                      variant="destructive"
                      icon={TriangleAlert}
                      title={t('detail.negativeTitle', { count: negativeCount })}
                      description={t('detail.negativeHint')}
                      actions={
                        <Button asChild variant="brand" size="sm">
                          <Link to={elementPath}>
                            <SquarePen />
                            {t('detail.revise')}
                          </Link>
                        </Button>
                      }
                    />
                  ) : null}
                </CardContent>
              </Card>
            </div>

            {/* Notiz hinzufügen */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquarePlus className="size-4 text-muted-foreground" aria-hidden="true" />
                  {t('detail.noteTitle')}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Textarea
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t('detail.notePlaceholder')}
                  aria-label={t('detail.noteTitle')}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {noteTarget === null ? (
                    <p className="text-xs text-muted-foreground">{t('detail.noteNoOpen')}</p>
                  ) : (
                    <span />
                  )}
                  <Button
                    type="button"
                    variant="brand"
                    disabled={savingNote || noteTarget === null || note.trim() === ''}
                    onClick={() => void onSaveNote()}
                  >
                    {t('detail.noteSave')}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Einzel-Ereignisse (Drill-down, lazy) */}
            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
                <CardTitle>{t('detail.eventsTitle')}</CardTitle>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={toggleEvents}
                  aria-expanded={showEvents}
                >
                  {showEvents ? t('detail.eventsHide') : t('detail.eventsShow')}
                  <ChevronDown
                    className={cn(
                      'transition-transform duration-[var(--duration-fast)] ease-standard',
                      showEvents && 'rotate-180',
                    )}
                    aria-hidden="true"
                  />
                </Button>
              </CardHeader>
              {showEvents ? (
                <CardContent>
                  <DataView
                    loading={eventsLoading && events === null}
                    error={null}
                    empty={events !== null && events.feedback.length === 0}
                    emptyTitle={t('detail.eventsEmpty')}
                  >
                    {events !== null && events.feedback.length > 0 ? (
                      <ul className="flex flex-col divide-y">
                        {events.feedback.map((ev) => {
                          const eventName = `${t(`signal.${ev.signal}`)} · ${
                            ev.version !== null ? `v${ev.version}` : t('panel.noVersion')
                          }`
                          return (
                            <li key={ev.id} className="flex flex-col gap-2.5 py-4 first:pt-0 last:pb-0">
                              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                                <Badge
                                  variant={
                                    NEGATIVE_SIGNALS.includes(ev.signal) ? 'destructive' : 'secondary'
                                  }
                                >
                                  <span
                                    className="mr-1 inline-block size-1.5 rounded-full bg-current"
                                    aria-hidden="true"
                                  />
                                  {t(`signal.${ev.signal}`)}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  {ev.version !== null ? `v${ev.version}` : t('panel.noVersion')}
                                </span>
                                <span className="ml-auto text-xs text-muted-foreground">
                                  {ev.agent_id !== null ? t('panel.agent') : t('panel.human')} ·{' '}
                                  {new Date(ev.created_at).toLocaleDateString()}
                                </span>
                              </div>
                              {ev.note !== null && ev.note !== '' ? (
                                <p className="border-l-2 border-border pl-3 text-sm text-foreground/90">
                                  {ev.note}
                                </p>
                              ) : null}
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                  {t('resolution.label')}
                                </span>
                                <ResolutionSegments
                                  name={eventName}
                                  value={ev.resolution}
                                  onChange={(r) => void onResolution(ev.id, r)}
                                />
                                <div className="ml-auto">
                                  <DeleteFeedbackButton onConfirm={() => deleteFeedback(ev.id)} />
                                </div>
                              </div>
                            </li>
                          )
                        })}
                      </ul>
                    ) : null}
                  </DataView>
                </CardContent>
              ) : null}
            </Card>
          </div>
        ) : null}
      </DataView>
    </div>
  )
}
