import { CalendarClock, MonitorSmartphone } from 'lucide-react'
import { type ReactNode, type RefObject, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  CaseRead,
  CaseStatus,
  FollowUpReport,
  FollowUpVersionReport,
  MeasureEvent,
  MeasureRead,
  SessionRead,
  TestCaseRead,
  VersionStatus,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CaseStatusDot } from '@/components/cases/CaseStatusDot'
import { MetaPill } from '@/components/data/MetaPill'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { ChangeActions } from '@/features/evolution/components/ChangeActions'
import {
  followUpDate,
  followUpStatusOf,
  formatDay,
  hasFollowUpFigures,
  isClosedState,
  isDue,
  isKnownMeasureEvent,
} from '@/features/evolution/lib/followUp'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { uiLocale } from '@/lib/dates'
import { cn } from '@/lib/utils'

// Aenderung-Sheet, nur lesend (Neuschnitt §1, §4; E5-Delta §4.1, §4.3, §8).
// Code-Namen nach der API (Measure = Aenderung), Texte nach A4a. Aktionen
// (Entwurf verknuepfen, „Hat es gewirkt?“, Zurueckziehen) folgen mit E5e.
//
// Eine Quelle je Ansicht (PM 2026-10-14): Den Zustand liefert der Server
// (`measure.state`); Sheet und Liste rechnen ihn nicht aus den Events nach.
// Nur die Faellig-Markierung braucht den lokalen Kalendertag, weil es an der
// einzelnen Aenderung keinen Serverwert dafuer gibt.

/** Pill „Nachkontrolle faellig …“ bzw. Meta „Nachkontrolle am …“; nichts, wenn abgeschlossen. */
export function ChangeDueMark({
  measure,
  session,
}: {
  measure: Pick<MeasureRead, 'state' | 'follow_up_at'>
  session: Pick<SessionRead, 'follow_up_at'>
}) {
  const { t } = useTranslation('sessions')
  const status = followUpStatusOf(measure, session)
  if (status.kind === 'closed') return null
  if (isDue(status)) {
    return (
      <MetaPill tone="brand" icon={CalendarClock} className="whitespace-normal">
        <span data-testid="measure-due">
          {t(status.kind === 'due_not_active' ? 'measure.dueNotActive' : 'measure.due')}
        </span>
      </MetaPill>
    )
  }
  return (
    <span className="text-xs text-muted-foreground">
      <time dateTime={status.date}>{t('measure.followUpOn', { date: formatDay(status.date) })}</time>
    </span>
  )
}


// --- Elemente und Versionen ---------------------------------------------

const VERSIONED: Record<VersionedEntityType, { segment: string; versionsTab: boolean }> = {
  persona: { segment: 'personas', versionsTab: true },
  playbook: { segment: 'playbooks', versionsTab: true },
  resource: { segment: 'resources', versionsTab: true },
  system_prompt_template: { segment: 'system-prompts', versionsTab: true },
  external_tool: { segment: 'tools', versionsTab: false },
}

function isVersionedTarget(target: string): target is VersionedEntityType {
  return target in VERSIONED
}

interface LinkedVersion {
  version: number
  status: VersionStatus | null
}

/** Juengstes Event einer Art (die API liefert aelteste zuerst). */
function latest(events: readonly MeasureEvent[], kind: MeasureEvent['event']): MeasureEvent | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].event === kind) return events[index]
  }
  return null
}

/**
 * Versionsliste des Ziels, nur wenn ein Entwurf verknuepft ist: Nummer und
 * Status je `version_id` fuer Feld „Entwurf“ und Verlauf.
 */
function useLinkedVersions(measure: MeasureRead): Record<string, LinkedVersion> | null {
  const api = useApi()
  const [versions, setVersions] = useState<Record<string, LinkedVersion> | null>(null)
  const linked = latest(measure.events, 'draft_linked')
  const type = linked?.version_entity_type ?? null
  const entityId = measure.entity_id

  useEffect(() => {
    if (type === null || entityId === null) return
    let cancelled = false
    const load = () => {
      switch (type) {
        case 'persona':
          return api.listPersonaVersions(entityId)
        case 'playbook':
          return api.listPlaybookVersions(entityId)
        case 'resource':
          return api.listResourceVersions(entityId)
        case 'external_tool':
          return api.listExternalToolVersions(entityId)
        case 'system_prompt_template':
          return api.listSystemPromptTemplateVersions(entityId)
      }
    }
    load().then(
      (list) => {
        if (cancelled) return
        const next: Record<string, LinkedVersion> = {}
        for (const row of list) next[row.id] = { version: row.version, status: row.status ?? null }
        setVersions(next)
      },
      () => {
        if (!cancelled) setVersions({})
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, type, entityId])

  return type === null || entityId === null ? {} : versions
}

// --- Kennzahlen -----------------------------------------------------------

type FollowUpData =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'ready'; report: FollowUpReport }
  | { kind: 'error' }

/** `GET /measures/{id}/follow-up` nur, wenn `enabled`; `state` laedt nach einer Aktion neu. */
function useFollowUp(measureId: string, enabled: boolean, state: string, onGone: () => void) {
  const api = useApi()
  const [data, setData] = useState<FollowUpData>({ kind: enabled ? 'loading' : 'idle' })
  const [nonce, setNonce] = useState(0)
  const goneRef = useRef(onGone)
  useLayoutEffect(() => {
    goneRef.current = onGone
  })

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api.getFollowUp(measureId).then(
      (report) => {
        if (!cancelled) setData({ kind: 'ready', report })
      },
      (cause: unknown) => {
        if (cancelled) return
        if (cause instanceof ApiError && cause.status === 404) goneRef.current()
        else setData({ kind: 'error' })
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, measureId, enabled, state, nonce])

  const retry = () => {
    setData({ kind: 'loading' })
    setNonce((value) => value + 1)
  }
  return { data, retry }
}

type Direction = 'lower' | 'higher' | 'same'

function directionOf(before: number, after: number): Direction {
  if (after === before) return 'same'
  return after < before ? 'lower' : 'higher'
}

/** Rate „je 100 Nutzungen“ mit einer Nachkommastelle; `null` ohne Nutzung oder Zahl. */
function ratePer100(side: FollowUpVersionReport | null): number | null {
  if (side === null || side.cases === null || side.uses <= 0) return null
  return Math.round((side.cases / side.uses) * 1000) / 10
}

function passShare(side: FollowUpVersionReport | null): number | null {
  const run = side?.test_run ?? null
  if (run === null || run.runs_total <= 0) return null
  return run.runs_passed / run.runs_total
}

interface FigureRow {
  id: 'passRate' | 'caseRate' | 'recurrence'
  label: string
  before: ReactNode
  after: ReactNode
}

function FollowUpFigures({ report }: { report: FollowUpReport }) {
  const { t } = useTranslation('sessions')
  const decimal = new Intl.NumberFormat(uiLocale(), {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  const integer = new Intl.NumberFormat(uiLocale())
  const { before, after } = report

  const word = (direction: Direction | null) =>
    direction === null ? null : (
      <span className="text-muted-foreground" data-testid="figure-direction">
        {' '}
        {t(`followUp.direction.${direction}`)}
      </span>
    )

  const runs = (side: FollowUpVersionReport | null): ReactNode => {
    const run = side?.test_run ?? null
    if (run === null) return '–'
    return t(run.attestation === 'client_self_report' ? 'followUp.runsClient' : 'followUp.runs', {
      passed: integer.format(run.runs_passed),
      total: integer.format(run.runs_total),
    })
  }
  const rate = (side: FollowUpVersionReport | null): ReactNode => {
    const value = ratePer100(side)
    if (value === null || side === null) return '–'
    return t('followUp.rate', { rate: decimal.format(value), uses: integer.format(side.uses) })
  }

  const shareBefore = passShare(before)
  const shareAfter = passShare(after)
  const rateBefore = ratePer100(before)
  const rateAfter = ratePer100(after)

  const rows: FigureRow[] = [
    {
      id: 'passRate',
      label: t('followUp.row.passRate'),
      before: runs(before),
      after: (
        <>
          {runs(after)}
          {shareBefore !== null && shareAfter !== null ? word(directionOf(shareBefore, shareAfter)) : null}
        </>
      ),
    },
    {
      id: 'caseRate',
      label: t('followUp.row.caseRate'),
      before: rate(before),
      after: (
        <>
          {rate(after)}
          {/* Unter der Mindestnutzung keine Richtung (QE8 a: der Server entscheidet). */}
          {!report.insufficient && rateBefore !== null && rateAfter !== null
            ? word(directionOf(rateBefore, rateAfter))
            : null}
        </>
      ),
    },
    {
      id: 'recurrence',
      label: t('followUp.row.recurrence'),
      before: '–',
      after:
        report.recurrence === null ? '–' : t('followUp.recurrenceCount', { count: report.recurrence }),
    },
  ]

  const beforeHead =
    before !== null ? t('followUp.before', { version: before.version }) : t('followUp.beforePlain')
  const afterHead =
    after !== null ? t('followUp.after', { version: after.version }) : t('followUp.afterPlain')
  const selfReported = [before, after].some(
    (side) => side?.test_run?.attestation === 'client_self_report',
  )

  return (
    <div className="flex min-w-0 flex-col gap-3" data-testid="follow-up-figures">
      {report.insufficient && after !== null ? (
        <p className="text-sm" role="note" data-testid="follow-up-too-few">
          {t('followUp.tooFewUses', { count: after.uses })}
        </p>
      ) : null}

      {/* Ab md eine echte Tabelle (E5-Delta §8). */}
      <table className="hidden w-full table-fixed text-sm md:table" data-testid="follow-up-table">
        <caption className="sr-only">{t('followUp.caption')}</caption>
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground">
            <th scope="col" className="w-2/5 py-2 pr-3 font-medium">
              <span className="sr-only">{t('followUp.metric')}</span>
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              {beforeHead}
            </th>
            <th scope="col" className="py-2 font-medium">
              {afterHead}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b last:border-b-0" data-testid={`figure-${row.id}`}>
              <th scope="row" className="py-2 pr-3 text-left align-top font-medium break-words">
                {row.label}
              </th>
              <td className="py-2 pr-3 align-top break-words tabular-nums">{row.before}</td>
              <td className="py-2 align-top break-words tabular-nums">{row.after}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Unter md drei Karten mit sichtbaren Labels (E5-Delta §4.3, 390 px). */}
      <ul className="flex flex-col gap-2 md:hidden" data-testid="follow-up-cards">
        {rows.map((row) => (
          <li key={row.id} className="min-w-0 rounded-lg border p-3">
            <p className="text-sm font-medium break-words">{row.label}</p>
            <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted-foreground">{beforeHead}</dt>
              <dd className="min-w-0 break-words tabular-nums">{row.before}</dd>
              <dt className="text-muted-foreground">{afterHead}</dt>
              <dd className="min-w-0 break-words tabular-nums">{row.after}</dd>
            </dl>
          </li>
        ))}
      </ul>

      {selfReported ? (
        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <MonitorSmartphone className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {t('followUp.selfReport')}
        </p>
      ) : null}
    </div>
  )
}

function FollowUpSection({
  measure,
  data,
  retry,
}: {
  measure: MeasureRead
  data: FollowUpData
  retry: () => void
}) {
  const { t } = useTranslation(['sessions', 'common'])
  const enabled = hasFollowUpFigures(measure)

  let body: ReactNode
  if (!enabled) {
    body = (
      <p className="text-sm text-muted-foreground" data-testid="follow-up-not-yet">
        {t('sessions:followUp.notYet')}
      </p>
    )
  } else if (data.kind === 'ready') {
    body = <FollowUpFigures report={data.report} />
  } else if (data.kind === 'error') {
    // Kennzahlen-Fehler: der Rest des Sheets bleibt (E5-Delta §4.3).
    body = (
      <div className="flex flex-col items-start gap-2" role="alert" data-testid="follow-up-error">
        <p className="text-sm">{t('sessions:followUp.loadError')}</p>
        <Button type="button" variant="outline" className="min-h-11 md:min-h-9" onClick={retry}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  } else {
    body = <Skeleton className="h-24 w-full" data-testid="follow-up-skeleton" />
  }

  return (
    <section className="flex min-w-0 flex-col gap-3" aria-labelledby="change-follow-up-heading">
      <h3 id="change-follow-up-heading" className="text-base font-semibold">
        {t('sessions:followUp.title')}
      </h3>
      {body}
    </section>
  )
}

// --- Verlauf --------------------------------------------------------------

interface People {
  agentById: ReadonlyMap<string, string>
  memberById: ReadonlyMap<string, string | null>
}

function ActorWord({ event, people }: { event: MeasureEvent; people: People }) {
  const { t } = useTranslation('learning')
  const { me } = useSession()
  if (event.actor_kind === 'system') return <>{t('history.actor.system')}</>
  if (event.actor_kind === 'agent') {
    const name = event.actor_id !== null ? people.agentById.get(event.actor_id) : undefined
    return <>{name !== undefined ? t('history.actor.by', { name }) : t('history.actor.agentUnknown')}</>
  }
  if (event.actor_id !== null && event.actor_id === me?.user_id) return <>{t('history.actor.you')}</>
  const email = event.actor_id !== null ? people.memberById.get(event.actor_id) : undefined
  return <>{email ? t('history.actor.by', { name: email }) : t('history.actor.humanUnknown')}</>
}

function eventCount(event: MeasureEvent): number | null {
  const count = event.metrics?.count
  return typeof count === 'number' && Number.isFinite(count) ? count : null
}

function History({
  measure,
  element,
  versions,
  people,
}: {
  measure: MeasureRead
  element: string
  versions: Record<string, LinkedVersion> | null
  people: People
}) {
  const { t } = useTranslation('sessions')
  // Neueste zuerst; bei gleicher Zeit die spaetere Listenposition zuerst.
  const ordered = measure.events
    .map((event, index) => ({ event, index }))
    .sort((a, b) => {
      const diff = Date.parse(b.event.created_at) - Date.parse(a.event.created_at)
      return diff !== 0 && !Number.isNaN(diff) ? diff : b.index - a.index
    })
    .map(({ event }) => event)

  const label = (event: MeasureEvent): string => {
    if (!isKnownMeasureEvent(event.event)) return t('history.event.unknown')
    switch (event.event) {
      case 'draft_linked': {
        const version = event.version_id !== null ? versions?.[event.version_id]?.version : undefined
        return t('history.event.draft_linked', { element, version: version ?? '…' })
      }
      case 'activated': {
        const count = eventCount(event)
        return count === null
          ? t('history.event.activatedNoCount')
          : t('history.event.activated', { count })
      }
      case 'follow_up_prepared':
        return t('history.event.follow_up_prepared')
      case 'reviewed':
        return t('history.event.reviewed', {
          verdict: event.verdict !== null ? t(`measure.state.${event.verdict}`) : '–',
        })
      case 'withdrawn':
        return t('history.event.withdrawn', { note: event.note ?? '' })
    }
  }

  return (
    <section className="flex min-w-0 flex-col gap-3" aria-labelledby="change-history-heading">
      <h3 id="change-history-heading" className="text-base font-semibold">
        {t('history.title')}
      </h3>
      {ordered.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t('history.empty')}</p>
      ) : (
        <ol className="flex flex-col gap-3" data-testid="change-history">
          {ordered.map((event) => (
            <li key={event.id} className="flex min-w-0 flex-col gap-0.5 text-sm" data-testid="change-history-item">
              <p className="break-words whitespace-pre-wrap">{label(event)}</p>
              {event.event === 'reviewed' && event.note ? (
                <p className="break-words whitespace-pre-wrap text-muted-foreground">{event.note}</p>
              ) : null}
              <p className="text-xs text-muted-foreground">
                <time dateTime={event.created_at}>{formatDay(event.created_at)}</time>
                {' · '}
                <ActorWord event={event} people={people} />
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

// --- Felder ---------------------------------------------------------------

function Field({ label, children, testId }: { label: string; children: ReactNode; testId?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5" data-testid={testId}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm break-words">{children}</dd>
    </div>
  )
}

/** Freitext aus dem Client: Textknoten, nie Markdown oder HTML (E5-Delta §0.5). */
function FreeText({ text }: { text: string }) {
  return text.trim() === '' ? (
    <span className="text-muted-foreground">–</span>
  ) : (
    <span className="whitespace-pre-wrap">{text}</span>
  )
}

const LINK = 'font-medium wrap-anywhere text-brand hover:underline'

export interface ChangeSheetData {
  measure: MeasureRead
  /** Position im Review-Ergebnis (M1, M2, …). */
  index: number
  session: SessionRead
  agentName: string
  /** „Playbook „Name““ bzw. nur die Art. */
  element: string
  /** `undefined` = laedt noch, `null` = nicht ladbar. */
  testCase: TestCaseRead | null | undefined
  /** Rueckmeldungen des Review-Ergebnisses; `null` = laedt noch. */
  cases: CaseRead[] | null
  people: People
}

interface ChangeSheetProps {
  /** `null` schliesst das Sheet. */
  data: ChangeSheetData | null
  onClose: () => void
  /** Die Aenderung gibt es nicht (mehr): Sheet zu, Toast (E5-Delta §4.3). */
  onGone: () => void
  /** Nach einer Aktion: Review-Ergebnis samt Rueckmeldungen neu laden (E5e). */
  onChanged?: () => void
  /** Fokusziel beim Schliessen ohne Ausloeser (Deep-Link), je Aenderungs-ID. */
  fallbackFocus: (measureId: string) => HTMLElement | null
}

function ChangeBody({
  data,
  titleRef,
  onGone,
  onChanged,
}: {
  data: ChangeSheetData
  titleRef: RefObject<HTMLHeadingElement>
  onGone: () => void
  onChanged: () => void
}) {
  const { t } = useTranslation(['sessions', 'feedback', 'common'])
  const wsPath = useWorkspacePath()
  const { measure, session } = data
  const versions = useLinkedVersions(measure)
  const stateRef = useRef<HTMLSpanElement>(null)
  const versioned = isVersionedTarget(measure.target)
  const closed = isClosedState(measure.state)
  // Kennzahlen ab Aktiviert; bei Zielen ohne Versionen offen auch vorher,
  // weil nur der Bericht sagt, ob schon geantwortet werden darf (QE6).
  const { data: followUp, retry } = useFollowUp(
    measure.id,
    hasFollowUpFigures(measure) || (!versioned && !closed),
    measure.state,
    onGone,
  )
  // QE6: eine Bedingung vom Server (`FollowUpReport.reviewable`). Ohne
  // Bericht (Fehler, laedt) nur der Zustand: versioniert ab Aktiviert —
  // die Antwort bleibt bei einem Kennzahlen-Fehler moeglich (E5-Delta §4.3).
  const reviewable =
    followUp.kind === 'ready'
      ? followUp.report.reviewable
      : followUp.kind === 'error' &&
        versioned &&
        (measure.state === 'activated' || measure.state === 'follow_up_prepared')

  const caseStatusWord = (status: CaseStatus) =>
    status === 'addressed'
      ? t('feedback:cases.status.addressedShort')
      : t(`feedback:cases.status.${status}`)

  // Ziel: Element-Detail; Werkzeugrechte → Agent, Gedaechtnis → Gedaechtnis des Agenten.
  let target: ReactNode
  if (measure.target === 'tool_policy') {
    target = (
      <Link to={wsPath(`/agents/${encodeURIComponent(measure.agent_id)}?tab=settings`)} className={LINK}>
        {t('feedback:cases.assign.tool_policy')}
      </Link>
    )
  } else if (measure.target === 'memory') {
    target = (
      <Link to={wsPath(`/memory?agent=${encodeURIComponent(measure.agent_id)}`)} className={LINK}>
        {t('feedback:cases.assign.memory')}
      </Link>
    )
  } else if (isVersionedTarget(measure.target) && measure.entity_id !== null) {
    target = (
      <Link to={wsPath(`/${VERSIONED[measure.target].segment}/${measure.entity_id}`)} className={LINK}>
        {data.element}
      </Link>
    )
  } else {
    target = data.element
  }

  let testCase: ReactNode
  if (data.testCase === undefined) {
    testCase = <Skeleton className="h-4 w-40" />
  } else if (data.testCase === null) {
    testCase = (
      <span className="text-muted-foreground" data-testid="change-test-case-unavailable">
        {t('sessions:measure.testCaseUnavailable')}
      </span>
    )
  } else {
    testCase = (
      <span className="inline-flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <Link
          to={wsPath(`/agents/${encodeURIComponent(data.testCase.agent_id)}?tab=tests`)}
          className={LINK}
        >
          {data.testCase.title}
        </Link>
        {data.testCase.status === 'retired' ? (
          <MetaPill>
            <span data-testid="change-test-case-retired">{t('sessions:measure.testCaseRetired')}</span>
          </MetaPill>
        ) : null}
      </span>
    )
  }

  // Entwurf: der juengste `draft_linked` (QE4 a) mit Version und Status.
  const linked = latest(measure.events, 'draft_linked')
  const linkedType = linked?.version_entity_type ?? null
  const draftPath =
    linked !== null && linked.version_id !== null && linkedType !== null && measure.entity_id !== null
      ? wsPath(
          `/${VERSIONED[linkedType].segment}/${measure.entity_id}${VERSIONED[linkedType].versionsTab ? '?tab=versions' : ''}`,
        )
      : null
  let draft: ReactNode
  if (linked === null || linked.version_id === null) {
    draft = <span className="text-muted-foreground">{t('sessions:measure.noDraft')}</span>
  } else {
    const version = versions?.[linked.version_id]
    const path = draftPath
    const activatedAt = measure.events.find(
      (event) => event.event === 'activated' && event.version_id === linked.version_id,
    )?.created_at
    let status = ''
    if (version?.status === 'active') {
      status =
        activatedAt !== undefined
          ? t('sessions:measure.versionState.active', { date: formatDay(activatedAt) })
          : t('common:status.active')
    } else if (version?.status === 'draft') {
      status = t('sessions:measure.versionState.draft')
    } else if (version?.status === 'review') {
      status = t('sessions:measure.versionState.review')
    } else if (version?.status === 'inactive') {
      status = t('common:status.inactive')
    }
    const text =
      version === undefined
        ? data.element
        : `${data.element} v${version.version}${status !== '' ? ` · ${status}` : ''}`
    draft =
      path !== null ? (
        <Link to={path} className={LINK} data-testid="change-draft">
          {text}
        </Link>
      ) : (
        <span data-testid="change-draft">{text}</span>
      )
  }

  // Rueckmeldungen der Aenderung; geloeschte fehlen (PM-6).
  const caseIds = new Set(measure.case_ids)
  const cases = data.cases?.filter((item) => caseIds.has(item.id)) ?? null
  const date = followUpDate(measure, session)

  return (
    <>
      <SheetHeader className="sticky top-0 z-10 gap-2 border-b bg-background p-4 pr-12 text-left">
        <SheetTitle ref={titleRef} tabIndex={-1} className="break-words outline-none" data-testid="change-title">
          {t('sessions:measure.title', { n: data.index, element: data.element })}
        </SheetTitle>
        <SheetDescription className="break-words">
          {t('sessions:measure.from', { agent: data.agentName, date: formatDay(session.created_at) })}
        </SheetDescription>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span
            ref={stateRef}
            tabIndex={-1}
            className="text-xs font-semibold outline-none"
            data-testid="change-state"
          >
            {t(`sessions:measure.state.${measure.state}`)}
          </span>
          <ChangeDueMark measure={measure} session={session} />
        </p>
      </SheetHeader>

      <div className="flex min-w-0 flex-1 flex-col gap-6 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        <dl className="flex min-w-0 flex-col gap-3" data-testid="change-fields">
          <Field label={t('sessions:measure.field.change')}>
            <FreeText text={measure.change_summary} />
          </Field>
          <Field label={t('sessions:measure.field.target')} testId="change-target">
            {target}
          </Field>
          <Field label={t('sessions:measure.field.testCase')} testId="change-test-case">
            {testCase}
          </Field>
          <Field label={t('sessions:measure.field.criterion')}>
            <FreeText text={measure.success_criterion} />
          </Field>
          <Field label={t('sessions:measure.field.counterposition')}>
            <FreeText text={measure.counterposition} />
          </Field>
          <Field label={t('sessions:measure.field.followUp')} testId="change-follow-up-at">
            <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
              <time dateTime={date}>{formatDay(date)}</time>
              {followUpStatusOf(measure, session).kind === 'scheduled' ? null : (
                <ChangeDueMark measure={measure} session={session} />
              )}
            </span>
          </Field>
          <Field label={t('sessions:measure.field.draft')} testId="change-draft-field">
            {draft}
          </Field>
          <Field label={t('sessions:measure.field.cases')} testId="change-cases">
            {cases === null ? (
              <Skeleton className="h-4 w-40" />
            ) : cases.length === 0 ? (
              <span className="text-muted-foreground">{t('sessions:detail.casesEmpty')}</span>
            ) : (
              <ul className="flex min-w-0 flex-col gap-1">
                {cases.map((item) => (
                  <li key={item.id} className="min-w-0">
                    <Link
                      to={wsPath(`/feedback/cases/${item.id}`)}
                      className="flex min-h-11 min-w-0 flex-col gap-0.5 rounded-md py-1 hover:bg-muted/40 sm:flex-row sm:items-center sm:gap-2 md:min-h-9"
                    >
                      <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                        <CaseStatusDot status={item.status} />
                        {caseStatusWord(item.status)}
                      </span>
                      <span className="min-w-0 truncate">
                        {t('feedback:cases.row.expected', { text: item.expected_behavior })}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Field>
        </dl>

        <FollowUpSection measure={measure} data={followUp} retry={retry} />

        <ChangeActions
          measure={measure}
          element={data.element}
          versionedType={versioned ? (measure.target as VersionedEntityType) : null}
          elementPath={
            versioned && measure.entity_id !== null
              ? wsPath(`/${VERSIONED[measure.target as VersionedEntityType].segment}/${measure.entity_id}`)
              : null
          }
          draftPath={draftPath}
          reviewable={reviewable}
          cases={data.cases}
          onChanged={onChanged}
          onGone={onGone}
          onReviewed={() => stateRef.current?.focus()}
        >
          <History measure={measure} element={data.element} versions={versions} people={data.people} />
        </ChangeActions>
      </div>
    </>
  )
}

/**
 * Sheet „Änderung M{{n}}“ ueber dem Review-Ergebnis (`?change=<id>`). Ab `md`
 * rechts (max. 40 rem), darunter Bottom-Sheet in voller Hoehe. Fokus: beim
 * Oeffnen auf den Titel, beim Schliessen zurueck auf „Änderung öffnen“.
 */
export function ChangeSheet({
  data,
  onClose,
  onGone,
  onChanged = () => undefined,
  fallbackFocus,
}: ChangeSheetProps) {
  const mobile = useIsMobile()
  const titleRef = useRef<HTMLHeadingElement>(null)
  const open = data !== null
  // Letzten Inhalt behalten, damit das Sheet beim Schliessen nicht leer ausblendet.
  const [shown, setShown] = useState<ChangeSheetData | null>(data)
  if (data !== null && data !== shown) setShown(data)

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent
        side={mobile ? 'bottom' : 'right'}
        data-testid="change-sheet"
        className={cn(
          // Der Schliessen-Knopf liegt absolut und muss ueber dem fixierten Kopf bleiben.
          'gap-0 overflow-x-hidden overflow-y-auto overscroll-contain p-0 [&>button]:z-20',
          mobile ? 'h-[100svh] rounded-none' : 'w-full sm:max-w-[40rem]',
        )}
        onOpenAutoFocus={(event) => {
          event.preventDefault()
          titleRef.current?.focus()
        }}
        onCloseAutoFocus={(event) => {
          // Zurueck auf „Änderung öffnen“ derselben Aenderung, auch nach Deep-Link.
          const target = shown !== null ? fallbackFocus(shown.measure.id) : null
          if (target !== null) {
            event.preventDefault()
            target.focus()
          }
        }}
      >
        {shown !== null ? (
          <ChangeBody
            key={shown.measure.id}
            data={shown}
            titleRef={titleRef}
            onGone={onGone}
            onChanged={onChanged}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
