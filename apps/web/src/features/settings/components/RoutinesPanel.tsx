import { AlertTriangle } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import type { RoutineLastRun, RoutineStatus, RoutinesOverview } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// ADR-0057 §7 (Paket P5) — nur lesender Abschnitt „Hintergrund-Routinen“ fuer
// Betreiber der Instanz. Quelle ist `GET /v1/system/routines` (P4c). Die API
// entscheidet, wer Betreiber ist (`WHO2BE_OPERATORS` + MFA); das Web kennt die
// Liste nicht und fragt deshalb einfach an.
//
// Sichtbarkeit (PM-W7): bei 403 gibt es den Abschnitt nicht — keine Karte,
// keine Fehlermeldung, kein Navigationseintrag (der Abschnitt hat bewusst nie
// einen). Gleiches gilt fuer jeden anderen Fehler vor der ersten Antwort: wer
// nicht als Betreiber belegt ist, soll von der Existenz nichts erfahren. Einzige
// Ausnahme ist 503 — die liefert die Route nur Betreibern (Gate laeuft vorher),
// wenn ein `WHO2BE_ROUTINE_*`-Override ungueltig ist; das muss der Betreiber sehen.
//
// Nur lesend (W3 = a): keine Knoepfe, kein manueller Lauf, keine Bearbeitung.

type LoadState =
  | { kind: 'loading' }
  | { kind: 'hidden' }
  | { kind: 'error'; message: string }
  | { kind: 'ready'; data: RoutinesOverview }

// Feste Objekte: ein erneuter `setState` mit demselben Zustand loest keinen
// neuen Render aus, auch wenn sich die `api`-Referenz aendert.
const LOADING: LoadState = { kind: 'loading' }
const HIDDEN: LoadState = { kind: 'hidden' }

function useSystemRoutines(): LoadState {
  const api = useApi()
  const [state, setState] = useState<LoadState>(LOADING)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const data = await api.getSystemRoutines()
        if (active) setState({ kind: 'ready', data })
      } catch (cause) {
        if (!active) return
        if (cause instanceof ApiError && cause.status === 503) {
          setState({ kind: 'error', message: cause.message })
        } else {
          setState(HIDDEN)
        }
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [api])

  return state
}

function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone
}

function Timestamp({ iso, locale }: { iso: string | null; locale: string }) {
  const { t } = useTranslation('settings')
  if (iso === null) return <>{t('routines.none')}</>
  const date = new Date(iso)
  const local = date.toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })
  const sameUtcDay =
    date.toLocaleDateString('en-CA') === date.toLocaleDateString('en-CA', { timeZone: 'UTC' })
  const utc = date.toLocaleString(locale, {
    ...(sameUtcDay ? {} : { dateStyle: 'medium' }),
    timeStyle: 'short',
    timeZone: 'UTC',
  })
  // Ortszeit vorn, UTC sichtbar dahinter (Hover gibt es auf Touch nicht).
  return (
    <time dateTime={iso}>
      {local} <span className="text-muted-foreground">{t('routines.utcHint', { time: utc })}</span>
    </time>
  )
}

function formatDuration(ms: number, locale: string): string {
  if (ms < 1000) return `${ms.toLocaleString(locale)} ms`
  const seconds = ms / 1000
  if (seconds < 60) {
    return `${seconds.toLocaleString(locale, { maximumFractionDigits: 1 })} s`
  }
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes.toLocaleString(locale)} min ${rest.toLocaleString(locale)} s`
}

const STATUS_VARIANT = {
  succeeded: 'secondary',
  running: 'outline',
  skipped: 'outline',
  failed: 'destructive',
} as const

function LastRun({ run, locale }: { run: RoutineLastRun | null; locale: string }) {
  const { t } = useTranslation('settings')
  if (run === null) return <>{t('routines.neverRun')}</>
  const counters = Object.entries(run.result ?? {})
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Badge variant={STATUS_VARIANT[run.status]}>{t(`routines.status.${run.status}`)}</Badge>
        <Timestamp iso={run.started_at} locale={locale} />
        <span className="text-muted-foreground">
          {t(`routines.trigger.${run.trigger}`)}
          {run.duration_ms !== null ? ` · ${formatDuration(run.duration_ms, locale)}` : ''}
        </span>
      </div>
      {counters.length > 0 ? (
        <span className="break-words text-muted-foreground">
          {t('routines.counters')}{' '}
          {counters.map(([key, value]) => `${key}: ${value.toLocaleString(locale)}`).join(', ')}
        </span>
      ) : null}
      {run.error_class !== null ? (
        <span className="break-all text-destructive">
          {t('routines.errorClass')} <code className="font-mono text-xs">{run.error_class}</code>
        </span>
      ) : null}
    </div>
  )
}

function RoutineItem({ routine, locale }: { routine: RoutineStatus; locale: string }) {
  const { t } = useTranslation('settings')
  return (
    <li className="flex flex-col gap-3 rounded-md border p-3" data-testid="routine-item">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 font-mono text-sm font-medium break-all">
          {routine.name}
        </h3>
        <Badge variant={routine.enabled ? 'secondary' : 'outline'}>
          {routine.enabled ? t('routines.enabled') : t('routines.disabled')}
        </Badge>
        <Badge variant="outline">{t(`routines.source.${routine.source}`)}</Badge>
      </div>
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[10rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">{t('routines.schedule')}</dt>
        <dd className="min-w-0">
          <code className="font-mono text-xs break-all">{routine.schedule}</code>{' '}
          <span className="text-muted-foreground">{t('routines.scheduleUtc')}</span>
        </dd>
        <dt className="text-muted-foreground">{t('routines.lastRun')}</dt>
        <dd className="min-w-0">
          <LastRun run={routine.last_run} locale={locale} />
        </dd>
        <dt className="text-muted-foreground">{t('routines.nextRun')}</dt>
        <dd className="min-w-0">
          <Timestamp iso={routine.next_run_at} locale={locale} />
        </dd>
        <dt className="text-muted-foreground">{t('routines.lastSuccess')}</dt>
        <dd className="min-w-0">
          <Timestamp iso={routine.last_success_at} locale={locale} />
        </dd>
      </dl>
      {routine.external_schedule_detected ? (
        <Alert>
          <AlertTriangle />
          <AlertTitle>{t('routines.externalTitle')}</AlertTitle>
          <AlertDescription>{t('routines.externalDescription')}</AlertDescription>
        </Alert>
      ) : null}
    </li>
  )
}

export function RoutinesPanel() {
  const { t, i18n } = useTranslation('settings')
  const state = useSystemRoutines()
  const titleId = useId()

  // Solange unklar ist, ob der Aufrufer Betreiber ist, wird nichts gezeigt —
  // auch kein Lade-Skelett, das die Existenz des Abschnitts verraten wuerde.
  if (state.kind === 'loading' || state.kind === 'hidden') return null

  const locale = i18n.language
  return (
    <Card aria-labelledby={titleId} role="region" data-testid="routines-panel">
      <CardHeader>
        <CardTitle id={titleId}>{t('routines.title')}</CardTitle>
        <CardDescription>
          {t('routines.description', { timeZone: localTimeZone() })}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {state.kind === 'error' ? (
          <ErrorAlert message={state.message} />
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm">
              <span className="text-muted-foreground">{t('routines.workerLastSeen')}</span>{' '}
              <Timestamp iso={state.data.worker_last_seen_at} locale={locale} />
            </p>
            {state.data.routines.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('routines.empty')}</p>
            ) : (
              <ul className="flex flex-col gap-3" aria-label={t('routines.listLabel')}>
                {state.data.routines.map((routine) => (
                  <RoutineItem key={routine.name} routine={routine} locale={locale} />
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
