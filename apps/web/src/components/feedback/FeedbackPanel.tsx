import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { FeedbackSignal, FeedbackTarget, UsageOutcome } from '@/api/types'
import { DataView } from '@/components/data/DataView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useFeedback } from '@/hooks/useFeedback'
import { cn } from '@/lib/utils'

// Reihenfolge + Farbton der Auspraegungen. Positiv (applied/helpful) = brand
// (Warm Citrus), negativ + Fehler = destructive, neutral = muted. Keine neuen
// Tokens — bewusst innerhalb der Designsprache.
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

interface FeedbackPanelProps {
  type: FeedbackTarget
  id: string
  /** Optionaler „Überarbeiten"-Hook — wird nur bei negativen Signalen angeboten. */
  onRevise?: () => void
}

/**
 * Kurations-Sicht auf das Agenten-Feedback eines Elements (ADR-0038):
 * Nutzungszahl, Ergebnis-/Signal-Verteilung, letzte Notizen, Drill-down auf
 * Einzel-Ereignisse und — bei negativen Signalen — eine „Überarbeiten"-Aktion.
 * Editor-gated; die Page rendert dieses Panel nur fuer editor+.
 */
export function FeedbackPanel({ type, id, onRevise }: FeedbackPanelProps) {
  const { t } = useTranslation('feedback')
  const { summary, loading, error, events, eventsLoading, loadEvents } = useFeedback(type, id)
  const [showEvents, setShowEvents] = useState(false)

  const negativeCount = summary
    ? NEGATIVE_SIGNALS.reduce((sum, s) => sum + (summary.by_signal[s] ?? 0), 0)
    : 0
  const signalTotal = summary
    ? SIGNALS.reduce((sum, s) => sum + (summary.by_signal[s] ?? 0), 0)
    : 0
  const isEmpty =
    summary !== null &&
    summary.usage_count === 0 &&
    signalTotal === 0 &&
    summary.recent_notes.length === 0

  const toggleEvents = () => {
    if (!showEvents && events === null) {
      loadEvents()
    }
    setShowEvents((v) => !v)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('panel.title')}</CardTitle>
        <p className="text-sm text-muted-foreground">{t('panel.description')}</p>
      </CardHeader>
      <CardContent>
        <DataView
          loading={loading && summary === null}
          error={error}
          empty={isEmpty}
          emptyTitle={t('panel.empty')}
        >
          {summary !== null && !isEmpty ? (
            <div className="flex flex-col gap-6">
              {/* KPI: Nutzungszahl + Ergebnis-Verteilung als gestapelter Balken. */}
              <div className="flex flex-col gap-2">
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold">{summary.usage_count}</span>
                  <span className="text-sm text-muted-foreground">{t('panel.usageCount')}</span>
                </div>
                {summary.usage_count > 0 ? (
                  <div
                    className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
                    role="img"
                    aria-label={t('panel.outcomes')}
                  >
                    {OUTCOMES.map((o) => {
                      const n = summary.by_outcome[o] ?? 0
                      if (n === 0) return null
                      const pct = (n / summary.usage_count) * 100
                      return (
                        <div
                          key={o}
                          className={OUTCOME_BAR[o]}
                          style={{ width: `${pct}%` }}
                          title={`${t(`outcome.${o}`)}: ${n}`}
                        />
                      )
                    })}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {OUTCOMES.map((o) => {
                    const n = summary.by_outcome[o] ?? 0
                    if (n === 0) return null
                    return (
                      <span key={o} className="inline-flex items-center gap-1.5">
                        <span className={cn('inline-block h-2 w-2 rounded-full', OUTCOME_BAR[o])} />
                        {t(`outcome.${o}`)} · {n}
                      </span>
                    )
                  })}
                </div>
              </div>

              {/* Signale: beschriftete Zeilen mit Mini-Balken. */}
              {signalTotal > 0 ? (
                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium">{t('panel.signals')}</span>
                  {SIGNALS.map((s) => {
                    const n = summary.by_signal[s] ?? 0
                    if (n === 0) return null
                    const pct = (n / signalTotal) * 100
                    return (
                      <div key={s} className="flex items-center gap-2 text-sm">
                        <span className="w-24 shrink-0">{t(`signal.${s}`)}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                          <div className={cn('h-full', SIGNAL_BAR[s])} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="w-6 shrink-0 text-right tabular-nums">{n}</span>
                      </div>
                    )
                  })}
                </div>
              ) : null}

              {/* „Überarbeiten" — nur bei negativen Signalen + Handler. */}
              {onRevise !== undefined && negativeCount > 0 ? (
                <div className="flex flex-col gap-1">
                  <Button type="button" variant="outline" size="sm" className="self-start" onClick={onRevise}>
                    {t('panel.revise')}
                  </Button>
                  <p className="text-xs text-muted-foreground">{t('panel.reviseHint')}</p>
                </div>
              ) : null}

              {/* Letzte Notizen (escaped via React-Textnodes). */}
              {summary.recent_notes.length > 0 ? (
                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium">{t('panel.notes')}</span>
                  <ul className="flex flex-col gap-1.5">
                    {summary.recent_notes.map((note, i) => (
                      <li
                        key={i}
                        className="border-l-2 border-muted pl-3 text-sm text-muted-foreground"
                      >
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {/* Drill-down auf Einzel-Ereignisse. */}
              <div className="flex flex-col gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="self-start"
                  onClick={toggleEvents}
                  aria-expanded={showEvents}
                >
                  {showEvents ? t('panel.hideEvents') : t('panel.showEvents')}
                </Button>
                {showEvents ? (
                  <DataView
                    loading={eventsLoading && events === null}
                    error={null}
                    empty={events !== null && events.feedback.length === 0}
                    emptyTitle={t('panel.eventsEmpty')}
                  >
                    {events !== null && events.feedback.length > 0 ? (
                      <ul className="flex flex-col gap-3">
                        {events.feedback.map((ev) => (
                          <li key={ev.id} className="flex flex-col gap-1 text-sm">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                variant={
                                  NEGATIVE_SIGNALS.includes(ev.signal) ? 'destructive' : 'secondary'
                                }
                              >
                                {t(`signal.${ev.signal}`)}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {ev.version !== null
                                  ? `v${ev.version}`
                                  : t('panel.noVersion')}{' '}
                                · {ev.agent_id !== null ? t('panel.agent') : t('panel.human')} ·{' '}
                                {new Date(ev.created_at).toLocaleString()}
                              </span>
                            </div>
                            {ev.note !== null && ev.note !== '' ? (
                              <p className="text-muted-foreground">{ev.note}</p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </DataView>
                ) : null}
              </div>
            </div>
          ) : null}
        </DataView>
      </CardContent>
    </Card>
  )
}
