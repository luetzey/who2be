import {
  Activity,
  Brain,
  ChevronRight,
  FolderLock,
  FolderOpen,
  MessageSquareWarning,
  Repeat,
  SquareCheckBig,
  ThumbsUp,
  type LucideIcon,
} from 'lucide-react'
import { useCallback, useEffect, useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { Api } from '@/api/client'
import type {
  Agent,
  AgentUsageStats,
  AgentWorkArea,
  CaseCounts,
  FeedbackOverview,
  MemoryCounts,
  PatternListRead,
  TestCaseRead,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EntityIcon, type EntityTone } from '@/components/data/EntityIcon'
import { InboxSummary } from '@/components/data/InboxSummary'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useInboxCounts } from '@/hooks/useInboxCounts'

// Zeitraum der Kachel „Feedback zu seinen Bausteinen“ (Spec §3.2: „30 Tage“).
export const FEEDBACK_WINDOW_DAYS = 30

// Fenster der Kachel „Nutzung“ — fest im Server (`uses_30d`, Konzept §5.2).
const USAGE_WINDOW_DAYS = 30

// Rueckmeldungen, die noch auf jemanden warten (Spec §3.2, Kachel 1).
const OPEN_CASE_STATUSES = ['open', 'reopened', 'triaged', 'in_progress'] as const

type Loaded<T> = { status: 'loading' } | { status: 'ok'; data: T } | { status: 'error' }

/**
 * Laedt einen Wert, solange `load` gesetzt ist. Ergebnisse gelten nur fuer
 * denselben API-Client (Workspace/Token) und Schluessel; eine spaetere
 * Antwort ueberholt nie eine juengere Anfrage.
 */
function useLoaded<T>(
  load: ((api: Api) => Promise<T>) | null,
  key: string,
): [Loaded<T>, () => void] {
  const api = useApi()
  const [nonce, setNonce] = useState(0)
  const [result, setResult] = useState<{
    api: Api
    key: string
    nonce: number
    value: Loaded<T>
  } | null>(null)

  useEffect(() => {
    if (load === null) return
    let alive = true
    // Ueber `Promise.resolve().then`: auch ein synchroner Wurf beim
    // Anfragebau landet im Fehlerzweig der Kachel, nie auf der Seite.
    Promise.resolve()
      .then(() => load(api))
      .then(
        (data) => {
          if (alive) setResult({ api, key, nonce, value: { status: 'ok', data } })
        },
        () => {
          if (alive) setResult({ api, key, nonce, value: { status: 'error' } })
        },
      )
    return () => {
      alive = false
    }
  }, [api, key, nonce, load])

  const retry = useCallback(() => setNonce((n) => n + 1), [])
  const fresh =
    result !== null && result.api === api && result.key === key && result.nonce === nonce
  return [fresh ? result.value : { status: 'loading' }, retry]
}

// --------------------------------------------------------------- Kacheln

interface KpiTileProps {
  label: string
  icon: LucideIcon
  tone: EntityTone
  /** Ziel der Kachel; ohne Ziel ist sie kein Link (Spec §3.2 Nutzung: „–“). */
  href?: string
  state: Loaded<{ value: number; subtitle: string }>
  testId: string
}

/**
 * Kennzahl-Kachel als Link (Spec §3.2, `KpiCard`-Optik erweitert um
 * Untertitel und Ziel). Die ganze Kachel ist ein Link; der zugaengliche Name
 * traegt Bezeichnung und Zahl, der Untertitel kommt per `aria-describedby`
 * (Spec §8). Ohne Ziel steht dieselbe Kachel als benannte Gruppe ohne Pfeil.
 * Fehler: „–“ und „Nicht verfuegbar“, kein Banner.
 */
function KpiTile({ label, icon, tone, href, state, testId }: KpiTileProps) {
  const { t } = useTranslation('agents')
  const subtitleId = useId()
  const value = state.status === 'ok' ? String(state.data.value) : '–'
  const subtitle =
    state.status === 'ok'
      ? state.data.subtitle
      : state.status === 'error'
        ? t('overview.kpi.unavailable')
        : ''

  const shared = {
    'data-testid': testId,
    'aria-label':
      state.status === 'loading' ? label : t('overview.kpi.linkLabel', { label, value }),
    'aria-describedby': subtitle !== '' ? subtitleId : undefined,
    'aria-busy': state.status === 'loading' ? true : undefined,
  }
  const frame =
    'relative flex min-w-0 flex-col items-start gap-2 rounded-lg border border-border/40 bg-card p-4 text-card-foreground shadow-card sm:flex-row sm:gap-3'

  const content = (
    <>
      {/* Unter sm steht das Icon ueber dem Text: zwei Spalten auf 390 px
          lassen neben Icon und Pfeil sonst nur ~80 px fuer die Bezeichnung. */}
      <EntityIcon icon={icon} tone={tone} size="sm" />
      <div className={href === undefined ? 'w-full min-w-0 flex-1' : 'w-full min-w-0 flex-1 pr-5 sm:pr-6'}>
        <div className="text-sm wrap-anywhere hyphens-auto text-muted-foreground">{label}</div>
        <div className="text-2xl font-semibold tracking-tight tabular-nums">
          {state.status === 'loading' ? (
            <span className="inline-block h-7 w-8 animate-pulse rounded-md bg-muted" aria-hidden="true" />
          ) : (
            value
          )}
        </div>
        {subtitle !== '' ? (
          <p id={subtitleId} className="mt-1 text-xs wrap-anywhere hyphens-auto text-muted-foreground">
            {subtitle}
          </p>
        ) : null}
      </div>
      {href !== undefined ? (
        <ChevronRight
          className="absolute top-4 right-4 size-4 text-muted-foreground/60 group-hover:text-muted-foreground"
          aria-hidden="true"
        />
      ) : null}
    </>
  )

  if (href === undefined) {
    return (
      <div role="group" {...shared} className={frame}>
        {content}
      </div>
    )
  }
  return (
    <Link
      to={href}
      {...shared}
      className={`group ${frame} transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none`}
    >
      {content}
    </Link>
  )
}

/**
 * Ergebnis auf Kachelwerte abbilden. Eine unerwartete Antwortform wird wie
 * ein Ladefehler behandelt (Kachel „–“), statt die ganze Seite zu reissen.
 */
function mapLoaded<T, R>(state: Loaded<T>, map: (data: T) => R): Loaded<R> {
  if (state.status !== 'ok') return state
  try {
    return { status: 'ok', data: map(state.data) }
  } catch {
    return { status: 'error' }
  }
}

function joinParts(parts: string[]): string {
  return parts.join(' · ')
}

/**
 * „vor 2 Stunden“ in der Sprache der Oberflaeche (wie „Zu erledigen“).
 * Mindestens eine Minute, damit Uhrabweichung nie „in 1 Minute“ zeigt.
 */
function formatAge(iso: string, language: string, now: number = Date.now()): string {
  const format = new Intl.RelativeTimeFormat(language, { numeric: 'auto' })
  const seconds = Math.min((new Date(iso).getTime() - now) / 1000, -60)
  if (Number.isNaN(seconds)) throw new Error('invalid date')
  const abs = Math.abs(seconds)
  if (abs < 3600) return format.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return format.format(Math.round(seconds / 3600), 'hour')
  return format.format(Math.round(seconds / 86400), 'day')
}

/** Zaehlbeginn `YYYY-MM-DD` als Datum der Oberflaeche („08.10.2026“). */
function formatCountingSince(day: string, language: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) throw new Error('invalid date')
  return new Intl.DateTimeFormat(language, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

// ---------------------------------------------------------- Arbeitsbereiche

function AgentWorkAreas({ agentId }: { agentId: string }) {
  const { t } = useTranslation('agents')
  const { t: tc } = useTranslation('common')
  const wsPath = useWorkspacePath()
  const [areas, retry] = useLoaded<AgentWorkArea[]>(
    useCallback((api: Api) => api.listAgentWorkAreas(agentId), [agentId]),
    `work-areas|${agentId}`,
  )
  const headingId = useId()

  let body: ReactNode
  if (areas.status === 'loading') {
    body = <LoadingState rows={2} />
  } else if (areas.status === 'error' || !Array.isArray(areas.data)) {
    body = (
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground" role="alert">
        <span>{t('overview.workAreas.error')}</span>
        <Button type="button" variant="link" className="min-h-11 px-0 md:min-h-0" onClick={retry}>
          {tc('actions.retry')}
        </Button>
      </div>
    )
  } else if (areas.data.length === 0) {
    body = (
      <p className="text-sm text-muted-foreground" data-testid="agent-work-areas-empty">
        {t('overview.workAreas.empty')}
      </p>
    )
  } else {
    body = (
      <ul className="flex flex-col gap-1.5" aria-labelledby={headingId}>
        {areas.data.map((area) => {
          const others = Math.max(area.agent_count - 1, 0)
          const meta = area.owner
            ? t('overview.workAreas.own')
            : joinParts([
                t('overview.workAreas.shared', {
                  level: t(`overview.workAreas.level.${area.level}`),
                }),
                ...(others > 0 ? [t('overview.workAreas.moreAgents', { count: others })] : []),
              ])
          const Icon = area.scope === 'private' ? FolderLock : FolderOpen
          return (
            <li key={area.id} data-testid="agent-work-area">
              <div className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-0.5 rounded-md px-2 py-1.5 hover:bg-muted/50 md:min-h-0">
                <Icon
                  className={
                    area.scope === 'private'
                      ? 'size-4 flex-none text-pill-persona-fg'
                      : 'size-4 flex-none text-muted-foreground'
                  }
                  aria-hidden="true"
                />
                <Link
                  to={wsPath(`/workarea/areas/${area.id}`)}
                  className="line-clamp-2 min-w-0 flex-1 rounded-sm text-sm font-medium wrap-anywhere text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  {area.name}
                </Link>
                <span className="basis-full pl-7 text-xs text-muted-foreground sm:basis-auto sm:pl-0">
                  {meta}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    )
  }

  return (
    <Card data-testid="agent-work-areas">
      <CardContent className="flex flex-col gap-4 pt-6">
        <h2
          id={headingId}
          className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
        >
          {t('overview.workAreas.title')}
        </h2>
        {body}
        <p className="text-xs text-muted-foreground">{t('overview.workAreas.hint')}</p>
      </CardContent>
    </Card>
  )
}

// ------------------------------------------------------------------ Ueberblick

interface AgentOverviewProps {
  agent: Agent
  /** Die Zusammensetzung (`AgentHierarchyView`), steht ab `lg` neben den Arbeitsbereichen. */
  composition: ReactNode
}

/**
 * Tab „Überblick“ der Agent-Seite (Navigation & Transparenz W2-b, Spec §3.2):
 * Aufgaben-Zeile, Kennzahl-Kacheln als Links, Zusammensetzung und
 * Arbeitsbereiche.
 *
 * Rollen je Kachel (Tabelle §3.2): Rückmeldungen ab viewer (der Server
 * zaehlt fuer viewer nur eigene); Feedback, Gedaechtnis, Muster und
 * Pruefaelle ab editor — der Server verlangt dort editor, eine Kachel ohne
 * Recht entfaellt (kein Schloss). Nutzung (U4a) ab viewer, ohne Ziel.
 */
export function AgentOverview({ agent, composition }: AgentOverviewProps) {
  const { t, i18n } = useTranslation('agents')
  const language = i18n.language
  const { t: tf } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  // Solange die Rolle laedt, nur die viewer-Kacheln (kein Aufblitzen fremder Rechte).
  const isEditor = role !== null && role !== 'viewer'
  const agentId = agent.id
  const agentParam = encodeURIComponent(agentId)

  // 1. Aufgaben-Zeile: dieselbe Quelle wie Glocke und Dashboard, je Agent.
  // Bei 0 entfaellt sie hier ganz; waehrend des Ladens und bei Fehlern auch
  // (kein Springen der Kacheln, kein Fehler am Agenten).
  const inbox = useInboxCounts(agentId)

  // 2. Kacheln — jede laedt fuer sich; scheitert eine, bleiben die anderen.
  // Editor-Kacheln fragen erst an, wenn die Rolle feststeht (sonst 403).
  const loadCases = useCallback((api: Api) => api.countCases(agentId), [agentId])
  const loadFeedback = useCallback(
    (api: Api) => api.getFeedbackOverview({ agent_id: agentId, days: FEEDBACK_WINDOW_DAYS }),
    [agentId],
  )
  const loadMemory = useCallback(
    (api: Api) => api.countMemories({ agent_id: agentId, status: 'active' }, ['status', 'health']),
    [agentId],
  )
  const loadPatterns = useCallback((api: Api) => api.listPatterns(agentId), [agentId])
  const loadTests = useCallback(
    (api: Api) => api.listTestCases({ agent_id: agentId, status: 'active' }),
    [agentId],
  )
  const [cases] = useLoaded<CaseCounts>(loadCases, `cases|${agentId}`)
  const loadUsage = useCallback((api: Api) => api.getAgentUsage(agentId), [agentId])
  const [usage] = useLoaded<AgentUsageStats>(loadUsage, `usage|${agentId}`)
  const [feedback] = useLoaded<FeedbackOverview>(
    isEditor ? loadFeedback : null,
    `feedback|${agentId}|${isEditor}`,
  )
  const [memory] = useLoaded<MemoryCounts>(
    isEditor ? loadMemory : null,
    `memory|${agentId}|${isEditor}`,
  )
  const [patterns] = useLoaded<PatternListRead>(
    isEditor ? loadPatterns : null,
    `patterns|${agentId}|${isEditor}`,
  )
  const [tests] = useLoaded<TestCaseRead[]>(
    isEditor ? loadTests : null,
    `tests|${agentId}|${isEditor}`,
  )
  const none = t('overview.kpi.none')

  const casesTile = mapLoaded(cases, (counts) => {
    const value = OPEN_CASE_STATUSES.reduce((sum, status) => sum + (counts[status] ?? 0), 0)
    const parts: string[] = []
    if (counts.reopened > 0) parts.push(t('overview.kpi.casesReopened', { count: counts.reopened }))
    if (counts.in_progress > 0)
      parts.push(t('overview.kpi.casesInProgress', { count: counts.in_progress }))
    return { value, subtitle: value === 0 ? none : joinParts(parts) }
  })

  const feedbackTile = mapLoaded(feedback, (overview) => {
    const value = overview.items.reduce((sum, item) => sum + item.feedback_count, 0)
    const negative = overview.items.reduce((sum, item) => sum + item.negative_count, 0)
    return {
      value,
      subtitle:
        value === 0
          ? none
          : t('overview.kpi.feedbackSub', { count: negative, days: FEEDBACK_WINDOW_DAYS }),
    }
  })

  const memoryTile = mapLoaded(memory, (counts) => {
    const pending = counts.groups?.status?.pending ?? 0
    const expiring = counts.groups?.health?.expiring_soon ?? 0
    const parts: string[] = []
    if (pending > 0) parts.push(t('overview.kpi.memoryPending', { count: pending }))
    if (expiring > 0) parts.push(t('overview.kpi.memoryExpiring', { count: expiring }))
    return {
      value: counts.total,
      subtitle: counts.total === 0 && parts.length === 0 ? none : joinParts(parts),
    }
  })

  const patternsTile = mapLoaded(patterns, (list) => {
    const strongest = list.patterns.reduce<PatternListRead['patterns'][number] | null>(
      (best, pattern) => (best === null || pattern.count > best.count ? pattern : best),
      null,
    )
    if (strongest === null) return { value: 0, subtitle: none }
    const element =
      strongest.source === 'lesson'
        ? t('overview.kpi.patternLesson')
        : strongest.element !== null
          ? tf(`cases.target.${strongest.element.target}`)
          : t('overview.kpi.patternCase')
    return {
      value: list.patterns.length,
      subtitle: t('overview.kpi.patternTop', { element, count: strongest.count }),
    }
  })

  const testsTile = mapLoaded(tests, (list) => ({
    value: list.length,
    subtitle: list.length === 0 ? none : t('overview.kpi.testsActive'),
  }))

  // Nutzung (U4a): Auslieferungen an diesen Agenten in 30 Tagen. Ohne je eine
  // Auslieferung nennt der Untertitel den Zaehlbeginn, sonst wirkt alles
  // Aeltere ungenutzt (Konzept §5.1).
  const usageTile = mapLoaded(usage, (stats) => {
    if (typeof stats.uses_30d !== 'number') throw new Error('unexpected usage')
    return {
      value: stats.uses_30d,
      subtitle:
        stats.last_used_at !== null
          ? t('overview.kpi.usageLast', {
              age: formatAge(stats.last_used_at, language),
              days: USAGE_WINDOW_DAYS,
            })
          : t('overview.kpi.usageNever', {
              date: formatCountingSince(stats.counting_since, language),
            }),
    }
  })

  const agentPath = (tab: string) => wsPath(`/agents/${agentParam}?tab=${tab}`)

  return (
    <div className="flex flex-col gap-6" data-testid="agent-overview">
      {inbox.counts !== null && inbox.counts.total > 0 ? (
        <InboxSummary
          counts={inbox.counts}
          failed={false}
          isAdmin={role === 'admin'}
          href={wsPath(`/inbox?agent=${agentParam}`)}
        />
      ) : null}

      <section aria-labelledby="agent-overview-glance" className="flex flex-col gap-3">
        <h2
          id="agent-overview-glance"
          className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
        >
          {t('overview.glance')}
        </h2>
        <div className="grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 lg:grid-cols-3">
          <KpiTile
            testId="agent-kpi-cases"
            label={t('overview.kpi.cases')}
            icon={MessageSquareWarning}
            tone="playbook"
            href={wsPath(`/feedback?tab=cases&agent=${agentParam}`)}
            state={casesTile}
          />
          {isEditor ? (
            <>
              <KpiTile
                testId="agent-kpi-feedback"
                label={t('overview.kpi.feedback')}
                icon={ThumbsUp}
                tone="resource"
                href={wsPath(`/feedback?tab=signals&agent=${agentParam}`)}
                state={feedbackTile}
              />
              <KpiTile
                testId="agent-kpi-memory"
                label={t('overview.kpi.memory')}
                icon={Brain}
                tone="persona"
                href={agentPath('memory')}
                state={memoryTile}
              />
              <KpiTile
                testId="agent-kpi-patterns"
                label={t('overview.kpi.patterns')}
                icon={Repeat}
                tone="date"
                href={wsPath(`/feedback?tab=patterns&agent=${agentParam}`)}
                state={patternsTile}
              />
              <KpiTile
                testId="agent-kpi-tests"
                label={t('overview.kpi.tests')}
                icon={SquareCheckBig}
                tone="catalog"
                href={agentPath('tests')}
                state={testsTile}
              />
            </>
          ) : null}
          <KpiTile
            testId="agent-kpi-usage"
            label={t('overview.kpi.usage')}
            icon={Activity}
            tone="tools"
            state={usageTile}
          />
        </div>
      </section>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        {composition}
        <AgentWorkAreas agentId={agentId} />
      </div>
    </div>
  )
}
