import { ArrowDown, CalendarClock, ChevronRight } from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Api } from '@/api/client'
import type {
  CaseCounts,
  CaseStatus,
  InboxCounts,
  MeasureRead,
  MeasureTarget,
  PatternListRead,
  SessionListItem,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ReportCaseDialog } from '@/components/cases/ReportCaseForm'
import { MetaPill } from '@/components/data/MetaPill'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  daysSince,
  followUpDate,
  followUpStatus,
  isDue,
  parseDay,
  type FollowUpStatus,
} from '@/features/evolution/lib/followUp'
import { EvolutionTimeline } from '@/features/evolution/components/EvolutionTimeline'
import { formatDate } from '@/lib/dates'
import { cn } from '@/lib/utils'

// Agent-Tab „Weiterentwicklung“ (Neuschnitt §3, E5g). Code-Namen bleiben bei
// der API (Session = Review-Ergebnis, Measure = Aenderung), Texte folgen A4a.
// Liegt unter `components/`, nicht unter `features/evolution/` (Zuschnitt
// §7.1): die Agent-Seite darf kein anderes Feature importieren
// (Cross-Feature-Gate), Muster `AgentMemoryCard`.
//
// Rechte (§3.7): editor/admin sehen Anleitung, Schritte ①–④, „Aenderungen“
// und „Reviews“. Ein viewer sieht nur ① mit seinen eigenen Rueckmeldungen
// (der Server zaehlt fuer ihn nur eigene) und einen Erklaersatz; Reviews,
// Aenderungen und Muster werden fuer ihn nicht angefragt. Solange die Rolle
// unbekannt ist, rendert der Tab nichts und laedt nichts (Muster D6b Nit d).
//
// Eine Quelle je Wert (PM 2026-10-14): Die Zahl in ④ und am Tab kommt aus
// `/inbox/counts` (`follow_ups_due`), die Faellig-Markierung einer
// Review-Zeile aus `due_measure_count`. `followUp.ts` rechnet nur an der
// einzelnen Aenderung (Zustand, Pill), wo es keinen Serverwert gibt.
//
// Verlauf (Generationen, §3.6, E5k): `EvolutionTimeline` unter den Reviews,
// Daten aus dem Dossier-Block `generations` (eine Anfrage, Cursor).

/** Reviews, deren Aenderungen der Tab hoechstens laedt (§3.4: 10 × `getSession`). */
export const EVOLUTION_REVIEW_LIMIT = 10

// Rueckmeldungen, die noch auf jemanden warten (wie die Ueberblick-Kachel).
const OPEN_CASE_STATUSES = ['open', 'reopened', 'triaged', 'in_progress'] as const

// Zustaende, in denen eine Aenderung noch nicht aktiviert ist (③ „offen“).
const NOT_ACTIVE = new Set(['agreed', 'draft_linked'])

// Status-Teile der viewer-Karte, in dieser Reihenfolge.
const VIEWER_STATUSES: readonly CaseStatus[] = [
  'open',
  'reopened',
  'triaged',
  'in_progress',
  'addressed',
  'verified',
  'dismissed',
]

const DAY_FORMAT: Intl.DateTimeFormatOptions = { day: '2-digit', month: '2-digit', year: 'numeric' }

/** `YYYY-MM-DD` (lokal) bzw. ISO-Zeitstempel als Datum der Oberflaeche. */
function formatDay(value: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? formatDate(parseDay(value), DAY_FORMAT)
    : formatDate(value, DAY_FORMAT)
}

/** Nur der Kalendertag, fuer `<time dateTime>`. */
function dayOf(value: string): string {
  return value.slice(0, 10)
}

type Loaded<T> = { status: 'loading' } | { status: 'ok'; data: T } | { status: 'error' }

/**
 * Laedt einen Wert, solange `load` gesetzt ist; ein Ergebnis gilt nur fuer
 * denselben API-Client und Schluessel (keine ueberholte Antwort).
 */
function useLoaded<T>(load: ((api: Api) => Promise<T>) | null, key: string): Loaded<T> {
  const api = useApi()
  const [result, setResult] = useState<{ api: Api; key: string; value: Loaded<T> } | null>(null)
  useEffect(() => {
    if (load === null) return
    let alive = true
    Promise.resolve()
      .then(() => load(api))
      .then(
        (data) => {
          if (alive) setResult({ api, key, value: { status: 'ok', data } })
        },
        () => {
          if (alive) setResult({ api, key, value: { status: 'error' } })
        },
      )
    return () => {
      alive = false
    }
  }, [api, key, load])
  return result !== null && result.api === api && result.key === key
    ? result.value
    : { status: 'loading' }
}

/** Zahl aus einer Antwort, die auch fehlen oder kaputt sein kann. */
function num(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

/**
 * Wartet am Agenten auf dich: offene Rueckmeldungen plus faellige
 * Nachkontrollen (§3.1). Muster zaehlen nicht (Navigation §3.3).
 */
function evolutionWaitingCount(counts: InboxCounts | null): number {
  if (counts === null) return 0
  return num(counts.cases_open) + num(counts.follow_ups_due)
}

// ------------------------------------------------------------ Bausteine

interface ReviewsState {
  items: SessionListItem[]
  nextCursor: string | null
  /** Aenderungen der ersten Seite je Review, `null` = noch nicht geladen. */
  measures: MeasureRead[] | null
  /** Namen der Elemente (`target:entity_id`). */
  names: Record<string, string>
  loading: boolean
  loadingMore: boolean
  error: boolean
}

const elementKey = (target: MeasureTarget, entityId: string) => `${target}:${entityId}`

function fetchElementName(api: Api, target: MeasureTarget, id: string): Promise<string> | null {
  switch (target) {
    case 'persona':
      return api.getPersona(id).then((entity) => entity.name)
    case 'playbook':
      return api.getPlaybook(id).then((entity) => entity.name)
    case 'resource':
      return api.getResource(id).then((entity) => entity.name)
    case 'external_tool':
      return api.getExternalTool(id).then((entity) => entity.name)
    case 'system_prompt_template':
      return api.getSystemPromptTemplate(id).then((entity) => entity.name)
    default:
      // Werkzeugrechte und Gedaechtnis erscheinen nur als Art.
      return null
  }
}

/**
 * Reviews des Agenten (neueste zuerst) und die Aenderungen der ersten Seite
 * (§3.4: hoechstens 10 Reviews, je ein `getSession`, parallel). „Weitere
 * laden“ haengt Reviews an, laedt aber keine weiteren Aenderungen.
 */
function useAgentReviews(agentId: string, enabled: boolean) {
  const api = useApi()
  const [state, setState] = useState<ReviewsState>({
    items: [],
    nextCursor: null,
    measures: null,
    names: {},
    loading: true,
    loadingMore: false,
    error: false,
  })

  useEffect(() => {
    if (!enabled) return
    let alive = true
    const run = async () => {
      const page = await api.listSessions({ agent_id: agentId }, { limit: EVOLUTION_REVIEW_LIMIT })
      if (!alive) return
      setState((prev) => ({
        ...prev,
        items: page.items,
        nextCursor: page.next_cursor,
        loading: false,
        loadingMore: false,
      }))
      // Ein Review, dessen Detail scheitert, fehlt still in „Aenderungen“.
      const details = await Promise.all(
        page.items.map((row) =>
          api.getSession(row.id).then(
            (detail) => detail.measures,
            () => [] as MeasureRead[],
          ),
        ),
      )
      if (!alive) return
      const measures = details.flat()
      setState((prev) => ({ ...prev, measures }))
      const wanted = new Map<string, Promise<string> | null>()
      for (const measure of measures) {
        if (measure.entity_id === null) continue
        const key = elementKey(measure.target, measure.entity_id)
        if (!wanted.has(key)) wanted.set(key, fetchElementName(api, measure.target, measure.entity_id))
      }
      const rows = await Promise.all(
        [...wanted.entries()].map(([key, job]) =>
          job === null
            ? Promise.resolve(null)
            : job.then(
                (name) => [key, name] as const,
                () => null,
              ),
        ),
      )
      if (!alive) return
      const names: Record<string, string> = {}
      for (const row of rows) if (row !== null) names[row[0]] = row[1]
      setState((prev) => ({ ...prev, names }))
    }
    run().catch(() => {
      if (alive) setState((prev) => ({ ...prev, loading: false, error: true, measures: [] }))
    })
    return () => {
      alive = false
    }
  }, [api, agentId, enabled])

  // Aktueller Agent/Client fuer „Weitere laden“: Eine Seite, die nach einem
  // Agentwechsel ankommt, gehoert zum alten Agenten und wird verworfen.
  const current = useRef({ api, agentId })
  useEffect(() => {
    current.current = { api, agentId }
  }, [api, agentId])

  const loadMore = useCallback(() => {
    const cursor = state.nextCursor
    if (cursor === null) return
    const stillCurrent = () => current.current.api === api && current.current.agentId === agentId
    setState((prev) => ({ ...prev, loadingMore: true }))
    api.listSessions({ agent_id: agentId }, { cursor, limit: EVOLUTION_REVIEW_LIMIT }).then(
      (page) => {
        if (!stillCurrent()) return
        setState((prev) => ({
          ...prev,
          items: [...prev.items, ...page.items],
          nextCursor: page.next_cursor,
          loadingMore: false,
        }))
      },
      () => {
        if (stillCurrent()) setState((prev) => ({ ...prev, loadingMore: false }))
      },
    )
  }, [api, agentId, state.nextCursor])

  return { ...state, loadMore }
}

interface StepCardProps {
  title: string
  loading: boolean
  head: string
  sub?: ReactNode
  /** „wartet auf dich“ als Wort; der `brand`-Rand ist nur Zusatz (§3.8). */
  waiting?: string
  actions?: ReactNode
  testId: string
}

/** Karte eines Schritts (§3.3): Ueberschrift `h3`, Kopfzahl, Unterzeile, Aktionen. */
function StepCard({ title, loading, head, sub, waiting, actions, testId }: StepCardProps) {
  return (
    <li
      className={cn(
        'flex min-w-0 flex-col gap-2 rounded-xl border bg-card p-4 text-card-foreground shadow-card',
        waiting !== undefined && 'border-brand/40 bg-brand/5',
      )}
      data-testid={testId}
    >
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      {loading ? (
        <div aria-busy="true" className="flex flex-col gap-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : (
        <>
          <p className="text-base font-semibold break-words" data-testid={`${testId}-head`}>
            {head}
          </p>
          {sub !== undefined && sub !== '' ? (
            <div className="text-sm break-words text-muted-foreground">{sub}</div>
          ) : null}
          {waiting !== undefined ? (
            <p className="flex items-center gap-1.5 text-xs font-semibold" data-testid={`${testId}-waiting`}>
              <span className="size-1.5 rounded-full bg-foreground" aria-hidden="true" />
              {waiting}
            </p>
          ) : null}
        </>
      )}
      {actions !== undefined ? (
        <div className="mt-auto flex flex-wrap gap-2 pt-2">{actions}</div>
      ) : null}
    </li>
  )
}

function joinParts(parts: string[]): string {
  return parts.join(' · ')
}

// ------------------------------------------------------------------ Tab

interface AgentEvolutionTabProps {
  agent: { id: string; name: string }
  /** Aufgaben-Zaehler des Agenten aus der Seite (eine Anfrage fuer Tab und ④). */
  inbox: { counts: InboxCounts | null; failed: boolean }
}

export function AgentEvolutionTab({ agent, inbox }: AgentEvolutionTabProps) {
  const role = useCurrentWorkspaceRole()
  if (role === null) return null
  if (role === 'viewer') return <ViewerEvolution agent={agent} />
  return <EditorEvolution agent={agent} inbox={inbox} />
}

// ------------------------------------------------------------------ viewer

function ViewerEvolution({ agent }: { agent: { id: string; name: string } }) {
  const { t } = useTranslation('sessions')
  const wsPath = useWorkspacePath()
  const loadCases = useCallback((api: Api) => api.countCases(agent.id), [agent.id])
  const cases = useLoaded<CaseCounts>(loadCases, `cases|${agent.id}`)

  const total =
    cases.status === 'ok' ? VIEWER_STATUSES.reduce((sum, s) => sum + num(cases.data[s]), 0) : 0
  const head =
    cases.status === 'ok' ? t('evolution.viewer.head', { count: total }) : '–'
  const sub =
    cases.status === 'error'
      ? t('evolution.unavailable')
      : cases.status === 'ok'
        ? joinParts(
            VIEWER_STATUSES.filter((s) => num(cases.data[s]) > 0).map((s) =>
              t(`evolution.viewer.status.${s}`, { count: num(cases.data[s]) }),
            ),
          )
        : undefined

  return (
    <div className="flex flex-col gap-6" data-testid="agent-evolution-viewer">
      <h2 className="sr-only">{t('evolution.title')}</h2>
      <ol aria-label={t('evolution.stepsAria')} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StepCard
          title={t('evolution.collect.title')}
          loading={cases.status === 'loading'}
          head={head}
          sub={sub}
          testId="evolution-step-collect"
          actions={
            <>
              <Button asChild variant="outline" className="min-h-11 md:min-h-10">
                <Link to={wsPath('/feedback')}>{t('evolution.viewer.mine')}</Link>
              </Button>
              <ReportCaseDialog agent={agent} variant="ghost" />
            </>
          }
        />
      </ol>
      <p className="rounded-xl border px-4 py-3 text-sm break-words" data-testid="evolution-viewer-explain">
        {t('evolution.viewer.explain')}
      </p>
    </div>
  )
}

// ------------------------------------------------------------------ editor

interface ChangeRow {
  measure: MeasureRead
  session: SessionListItem
  status: FollowUpStatus
}

function EditorEvolution({ agent, inbox }: AgentEvolutionTabProps) {
  const { t } = useTranslation(['sessions', 'feedback'])
  const wsPath = useWorkspacePath()
  const agentParam = encodeURIComponent(agent.id)
  const reviewPath = (sessionId: string, measureId?: string) =>
    wsPath(
      `/agents/${agentParam}/reviews/${encodeURIComponent(sessionId)}${
        measureId !== undefined ? `?change=${encodeURIComponent(measureId)}` : ''
      }`,
    )
  const preparePath = wsPath(`/agents/${agentParam}/reviews/prepare`)

  const loadCases = useCallback((api: Api) => api.countCases(agent.id), [agent.id])
  const loadPatterns = useCallback((api: Api) => api.listPatterns(agent.id), [agent.id])
  const cases = useLoaded<CaseCounts>(loadCases, `cases|${agent.id}`)
  const patterns = useLoaded<PatternListRead>(loadPatterns, `patterns|${agent.id}`)
  const reviews = useAgentReviews(agent.id, true)

  // Offene Aenderungen der geladenen Reviews (§3.4): faellige zuerst, dann
  // nach Datum der Nachkontrolle.
  const changes = useMemo<ChangeRow[] | null>(() => {
    if (reviews.measures === null) return null
    const byId = new Map(reviews.items.map((row) => [row.id, row]))
    const rows: ChangeRow[] = []
    for (const measure of reviews.measures) {
      const session = byId.get(measure.session_id)
      if (session === undefined) continue
      const status = followUpStatus(measure, session)
      if (status.kind === 'closed') continue
      rows.push({ measure, session, status })
    }
    return rows.sort((a, b) => {
      const due = Number(isDue(b.status)) - Number(isDue(a.status))
      return due !== 0 ? due : a.status.date.localeCompare(b.status.date)
    })
  }, [reviews.measures, reviews.items])

  // ① Sammeln
  const caseTotal =
    cases.status === 'ok' ? OPEN_CASE_STATUSES.reduce((sum, s) => sum + num(cases.data[s]), 0) : 0
  const collectSub = (() => {
    if (cases.status === 'error') return t('evolution.unavailable')
    if (cases.status !== 'ok') return undefined
    const parts: string[] = []
    const triaged = num(cases.data.triaged)
    const reopened = num(cases.data.reopened)
    if (triaged > 0) parts.push(t('evolution.collect.triaged', { count: triaged }))
    if (reopened > 0) parts.push(t('evolution.collect.reopened', { count: reopened }))
    if (patterns.status === 'ok' && Array.isArray(patterns.data.patterns)) {
      const n = patterns.data.patterns.length
      if (n > 0) parts.push(t('evolution.collect.patterns', { count: n }))
    }
    return joinParts(parts)
  })()
  const casesWaiting = num(inbox.counts?.cases_open)

  // ② Besprechen
  const latest = reviews.items[0]
  const triagedReady = cases.status === 'ok' ? num(cases.data.triaged) : 0

  // ③ Umsetzen
  const notActive = (changes ?? []).filter((row) => NOT_ACTIVE.has(row.status.state))
  const youngest = [...notActive].sort((a, b) =>
    b.measure.created_at.localeCompare(a.measure.created_at),
  )[0]

  // ④ Pruefen: Zahl vom Server; Ziel ist das faellige Review mit dem
  // aeltesten Termin (Server-`due_measure_count`), darin die faellige
  // Aenderung mit dem fruehesten Datum.
  const dueCount = inbox.counts === null ? null : num(inbox.counts.follow_ups_due)
  const dueSession = [...reviews.items]
    .filter((row) => row.due_measure_count > 0)
    .sort((a, b) => (a.next_follow_up_at ?? '').localeCompare(b.next_follow_up_at ?? ''))[0]
  const dueMeasure =
    dueSession === undefined
      ? undefined
      : (changes ?? [])
          .filter((row) => row.session.id === dueSession.id)
          .sort((a, b) => a.status.date.localeCompare(b.status.date))[0]
  const nextPlanned = reviews.items
    .map((row) => row.next_follow_up_at)
    .filter((day): day is string => day !== null)
    .sort()[0]
  const checkHead =
    dueCount === null
      ? '–'
      : dueCount > 0
        ? t('evolution.check.due', { count: dueCount })
        : nextPlanned !== undefined
          ? t('evolution.check.next', { date: formatDay(nextPlanned) })
          : t('evolution.check.none')
  const overdue =
    dueSession?.next_follow_up_at != null ? Math.max(daysSince(dueSession.next_follow_up_at), 0) : null

  // Datum der geladenen Reviews fuer „Warum: … (Review vom …)“ im Verlauf.
  const reviewDates = useMemo(
    () => Object.fromEntries(reviews.items.map((row) => [row.id, row.created_at])),
    [reviews.items],
  )

  return (
    <div className="flex flex-col gap-8" data-testid="agent-evolution">
      <h2 className="sr-only">{t('evolution.title')}</h2>
      <details className="group min-w-0 rounded-xl border px-4 py-3" data-testid="evolution-guide">
        <summary className="flex min-h-11 cursor-pointer items-center gap-1 text-sm md:min-h-9">
          <span className="font-semibold">{t('evolution.guide.summary')}</span>
          <span className="text-muted-foreground"> · {t('evolution.guide.steps')}</span>
        </summary>
        <p className="mt-2 text-sm break-words text-muted-foreground">{t('evolution.guide.body')}</p>
      </details>

      <ol aria-label={t('evolution.stepsAria')} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StepCard
          title={t('evolution.collect.title')}
          loading={cases.status === 'loading'}
          head={cases.status === 'ok' ? t('evolution.collect.head', { count: caseTotal }) : '–'}
          sub={collectSub}
          waiting={casesWaiting > 0 ? t('evolution.waiting', { count: casesWaiting }) : undefined}
          testId="evolution-step-collect"
          actions={
            <>
              <Button asChild variant="outline" className="min-h-11 md:min-h-10">
                <Link to={wsPath(`/feedback?tab=cases&agent=${agentParam}`)}>
                  {t('evolution.collect.view')}
                </Link>
              </Button>
              <ReportCaseDialog agent={agent} variant="ghost" />
            </>
          }
        />
        <StepCard
          title={t('evolution.discuss.title')}
          loading={reviews.loading}
          head={
            reviews.error
              ? '–'
              : latest !== undefined
                ? t('evolution.discuss.last', { date: formatDay(latest.created_at) })
                : t('evolution.discuss.none')
          }
          sub={
            reviews.error
              ? t('evolution.unavailable')
              : triagedReady > 0
                ? t('evolution.discuss.ready', { count: triagedReady })
                : undefined
          }
          testId="evolution-step-discuss"
          actions={
            <Button asChild variant="outline" className="min-h-11 md:min-h-10">
              <Link to={preparePath}>{t('evolution.prepare')}</Link>
            </Button>
          }
        />
        <StepCard
          title={t('evolution.implement.title')}
          loading={changes === null && !reviews.error}
          head={
            reviews.error
              ? '–'
              : notActive.length > 0
                ? t('evolution.implement.head', { count: notActive.length })
                : t('evolution.implement.none')
          }
          sub={
            reviews.error
              ? t('evolution.unavailable')
              : youngest !== undefined
                ? t(`evolution.implement.latest.${youngest.status.state}`)
                : undefined
          }
          testId="evolution-step-implement"
          actions={
            changes !== null && changes.length > 0 ? (
              <Button
                type="button"
                variant="outline"
                className="min-h-11 md:min-h-10"
                onClick={() => {
                  const target = document.getElementById('evolution-changes')
                  target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                  target?.focus({ preventScroll: true })
                }}
              >
                {t('evolution.implement.view')}
                <ArrowDown aria-hidden="true" />
              </Button>
            ) : undefined
          }
        />
        <StepCard
          title={t('evolution.check.title')}
          loading={inbox.counts === null && !inbox.failed}
          head={checkHead}
          sub={
            dueCount === null ? (
              t('evolution.unavailable')
            ) : dueCount > 0 && overdue !== null ? (
              <MetaPill tone="brand" icon={CalendarClock} className="whitespace-normal">
                <span data-testid="evolution-check-since">
                  {overdue === 0
                    ? t('evolution.check.today')
                    : t('evolution.check.since', { count: overdue })}
                </span>
              </MetaPill>
            ) : undefined
          }
          waiting={dueCount !== null && dueCount > 0 ? t('evolution.waiting', { count: dueCount }) : undefined}
          testId="evolution-step-check"
          actions={
            dueCount !== null && dueCount > 0 && dueSession !== undefined ? (
              <Button asChild className="min-h-11 md:min-h-10">
                <Link to={reviewPath(dueSession.id, dueMeasure?.measure.id)}>
                  {t('evolution.check.open')}
                </Link>
              </Button>
            ) : undefined
          }
        />
      </ol>

      {changes !== null && changes.length > 0 ? (
        <section
          id="evolution-changes"
          tabIndex={-1}
          className="flex min-w-0 scroll-mt-4 flex-col gap-3 focus-visible:outline-none"
          aria-labelledby="evolution-changes-title"
          data-testid="evolution-changes"
        >
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h2 id="evolution-changes-title" className="text-lg font-semibold">
              {t('evolution.changes.title')}
            </h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground/70 tabular-nums">
              {changes.length}
            </span>
            <span className="text-xs text-muted-foreground">{t('evolution.changes.subtitle')}</span>
          </div>
          <ul className="flex flex-col divide-y rounded-xl border bg-card shadow-card">
            {changes.map((row) => (
              <ChangeItem
                key={row.measure.id}
                row={row}
                names={reviews.names}
                href={reviewPath(row.session.id, row.measure.id)}
              />
            ))}
          </ul>
          {reviews.nextCursor !== null ? (
            <p className="text-xs text-muted-foreground">{t('evolution.changes.more')}</p>
          ) : null}
        </section>
      ) : null}

      <section
        className="flex min-w-0 flex-col gap-3"
        aria-labelledby="evolution-reviews-title"
        data-testid="evolution-reviews"
      >
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 id="evolution-reviews-title" className="text-lg font-semibold">
            {t('evolution.reviews.title')}
          </h2>
          {!reviews.loading && reviews.nextCursor === null && reviews.items.length > 0 ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground/70 tabular-nums">
              {reviews.items.length}
            </span>
          ) : null}
        </div>
        {reviews.loading ? (
          <div aria-busy="true" className="flex flex-col gap-2">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        ) : reviews.error ? (
          <p className="text-sm text-muted-foreground" role="alert">
            {t('evolution.reviews.loadError')}
          </p>
        ) : reviews.items.length === 0 ? (
          <div
            className="flex flex-col items-start gap-3 rounded-xl border border-dashed bg-muted/30 p-4"
            data-testid="evolution-reviews-empty"
          >
            <p className="text-sm break-words">{t('evolution.reviews.empty', { agent: agent.name })}</p>
            <Button asChild variant="outline" className="min-h-11 md:min-h-10">
              <Link to={preparePath}>{t('evolution.prepare')}</Link>
            </Button>
          </div>
        ) : (
          <>
            <ul className="flex flex-col divide-y rounded-xl border bg-card shadow-card">
              {reviews.items.map((row) => (
                <ReviewItem key={row.id} row={row} href={reviewPath(row.id)} />
              ))}
            </ul>
            {reviews.nextCursor !== null ? (
              <div>
                <Button
                  type="button"
                  variant="ghost"
                  className="min-h-11 md:min-h-10"
                  disabled={reviews.loadingMore}
                  onClick={reviews.loadMore}
                >
                  {t('evolution.reviews.more')}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </section>

      <EvolutionTimeline agentId={agent.id} changeHref={reviewPath} reviewDates={reviewDates} />
    </div>
  )
}

function ChangeItem({
  row,
  names,
  href,
}: {
  row: ChangeRow
  names: Record<string, string>
  href: string
}) {
  const { t } = useTranslation(['sessions', 'feedback'])
  const { measure, session, status } = row
  const kind = t(`feedback:cases.target.${measure.target}`)
  const name = measure.entity_id !== null ? names[elementKey(measure.target, measure.entity_id)] : undefined
  const title = name !== undefined ? `${kind} ${name}` : kind
  const due = isDue(status)
  const activated = [...measure.events].reverse().find((event) => event.event === 'activated')

  const meta: ReactNode[] = [
    <span key="summary" className="min-w-0 truncate">
      „{measure.change_summary}“
    </span>,
  ]
  if (activated !== undefined && !NOT_ACTIVE.has(status.state)) {
    meta.push(
      <time key="active" dateTime={dayOf(activated.created_at)}>
        {t('evolution.changes.activeSince', { date: formatDay(activated.created_at) })}
      </time>,
    )
  }
  if (!due) {
    meta.push(
      <time key="follow" dateTime={followUpDate(measure, session)}>
        {t('sessions:measure.followUpOn', { date: formatDay(status.date) })}
      </time>,
    )
  }
  meta.push(
    <time key="review" dateTime={dayOf(session.created_at)}>
      {t('evolution.changes.fromReview', { date: formatDay(session.created_at) })}
    </time>,
    <span key="cases">{t('sessions:detail.measureCases', { count: measure.case_ids.length })}</span>,
  )

  const action = due ? t('evolution.check.open') : t('evolution.changes.view')
  return (
    <li
      className="flex min-w-0 flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      data-testid="evolution-change"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="font-medium break-words">{title}</span>
          {due ? (
            <MetaPill tone="brand" icon={CalendarClock} className="whitespace-normal">
              <span data-testid="evolution-change-due">
                {t(status.kind === 'due_not_active' ? 'sessions:measure.dueNotActive' : 'sessions:measure.due')}
              </span>
            </MetaPill>
          ) : (
            <span className="text-xs text-muted-foreground" data-testid="evolution-change-state">
              {t(`sessions:measure.state.${status.state}`)}
            </span>
          )}
        </p>
        <p className="flex min-w-0 flex-wrap gap-x-1.5 text-xs text-muted-foreground">
          {meta.map((part, index) => (
            <span key={index} className="inline-flex min-w-0 gap-x-1.5">
              {index > 0 ? <span aria-hidden="true">·</span> : null}
              {part}
            </span>
          ))}
        </p>
      </div>
      <Button
        asChild
        variant={due ? 'default' : 'outline'}
        className="min-h-11 w-full shrink-0 sm:w-auto md:min-h-10"
      >
        <Link to={href} aria-label={t('evolution.changes.actionAria', { action, title })}>
          {action}
        </Link>
      </Button>
    </li>
  )
}

function ReviewItem({ row, href }: { row: SessionListItem; href: string }) {
  const { t } = useTranslation('sessions')
  const mark =
    row.due_measure_count > 0 ? (
      <MetaPill tone="brand" icon={CalendarClock} className="whitespace-normal">
        {t('evolution.reviews.mark.due')}
      </MetaPill>
    ) : row.superseded_by_id !== null ? (
      <span className="text-xs text-muted-foreground">{t('evolution.reviews.mark.replaced')}</span>
    ) : row.supersedes_id !== null ? (
      <span className="text-xs text-muted-foreground">{t('evolution.reviews.mark.corrects')}</span>
    ) : row.next_follow_up_at !== null ? (
      <time className="text-xs text-muted-foreground" dateTime={row.next_follow_up_at}>
        {t('measure.followUpOn', { date: formatDay(row.next_follow_up_at) })}
      </time>
    ) : null
  const meta = [
    t('evolution.reviews.cases', { count: row.case_count }),
    t('evolution.reviews.measures', { count: row.measure_count }),
    ...(row.submitted_by_kind !== 'human' ? [t('evolution.reviews.fromClient')] : []),
  ]
  return (
    <li className="relative min-w-0" data-testid="evolution-review">
      <div className="flex min-w-0 items-center gap-3 px-4 py-3 hover:bg-muted/40">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <Link
              to={href}
              className="font-medium break-words after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:rounded-xl focus-visible:after:ring-2 focus-visible:after:ring-ring"
            >
              {t('detail.title', { date: formatDay(row.created_at) })}
            </Link>
            <span className="text-xs text-muted-foreground">· {t(`trigger.${row.trigger}`)}</span>
            {mark}
          </p>
          {row.summary !== '' ? (
            <p className="line-clamp-1 text-xs break-words text-muted-foreground">„{row.summary}“</p>
          ) : null}
          <p className="text-xs text-muted-foreground">{joinParts(meta)}</p>
        </div>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" aria-hidden="true" />
      </div>
    </li>
  )
}

/** Zaehler am Tab-Reiter (§3.1): nur editor, bei 0 keiner. */
export function EvolutionTabCount({ counts }: { counts: InboxCounts | null }) {
  const { t } = useTranslation('sessions')
  const count = evolutionWaitingCount(counts)
  if (count === 0) return null
  return (
    <span
      className="rounded-full bg-muted px-1.5 py-0.5 text-xs font-medium text-foreground/70 tabular-nums"
      data-testid="evolution-tab-count"
    >
      <span aria-hidden="true">{count}</span>
      <span className="sr-only">, {t('evolution.waiting', { count })}</span>
    </span>
  )
}
