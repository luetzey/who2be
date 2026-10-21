import {
  Bot,
  CalendarClock,
  Copy,
  ExternalLink,
  MessageSquareWarning,
  MoreHorizontal,
  Trash2,
} from 'lucide-react'
import { type Ref, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  Agent,
  CaseDetail,
  CaseEvent,
  CaseEventKind,
  CaseStatus,
  CaseTarget,
  MeasureRead,
  SessionRead,
  TestCaseRead,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useSession } from '@/auth/session-context'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CaseActions } from '@/components/cases/CaseActions'
import { DetailHeader } from '@/components/data'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Container } from '@/components/layout/Container'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { CaseStatusDot } from '@/components/cases/CaseStatusDot'
import { MetaPill } from '@/components/data/MetaPill'
import { copyToClipboard } from '@/lib/clipboard'
import { type CaseMeasureRef, pickCaseMeasure } from '@/lib/caseNextStep'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

// Reine Nachkontroll-Logik, relativ importiert wie in `InboxPage` (E5j): das
// Cross-Feature-Gate sperrt Komponenten/Seiten, die Lib ist bewusst geteilt.
import { followUpStatusOf, formatDay, isClosedState, isDue } from '../../evolution/lib/followUp'

// Status mit Erklaersatz unter dem Kopf (E-Delta §6.1): beide setzt nur der
// Server, fuer alle Rollen sichtbar, ohne Link (die Links von E5h stehen in
// „Verknüpft“ und im Verlauf).
const EXPLAINED_STATUSES: ReadonlySet<CaseStatus> = new Set<CaseStatus>(['in_progress', 'verified'])

// Ereignisse mit eigenem Wort (Delta-Spec S8, E-Delta §6.1). Alles andere
// faellt auf `cases.history.event.unknown` zurueck und wird nie roh angezeigt.
const KNOWN_EVENTS: ReadonlySet<CaseEventKind> = new Set<CaseEventKind>([
  'reported',
  'triaged',
  'in_progress',
  'addressed',
  'verified',
  'dismissed',
  'reopened',
  'element_assigned',
  'element_unassigned',
  'statement',
])

// Ereignisse, deren Wort die Notiz schon enthaelt (`… : {{note}}`).
const NOTE_IN_LABEL: ReadonlySet<CaseEventKind> = new Set<CaseEventKind>(['dismissed', 'reopened'])

// Filter der Fall-Liste, die der Zeilen-Link mitgibt und der Rueckweg zurueckgibt.
const LIST_FILTER_KEYS = ['status', 'agent', 'target'] as const

// Listen-Pfad je versioniertem Element; `?tab=versions` nur, wo die Seite ihn kennt.
const ELEMENT_PATH: Record<VersionedEntityType, { segment: string; versionsTab: boolean }> = {
  persona: { segment: 'personas', versionsTab: true },
  playbook: { segment: 'playbooks', versionsTab: true },
  resource: { segment: 'resources', versionsTab: true },
  system_prompt_template: { segment: 'system-prompts', versionsTab: true },
  external_tool: { segment: 'tools', versionsTab: false },
}

function isVersioned(target: CaseTarget): target is VersionedEntityType {
  return target in ELEMENT_PATH
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

interface ResolvedVersion {
  name: string
  version: number
  path: string
}

interface CaseDetailData {
  detail: CaseDetail | null
  agents: Agent[]
  /** Elementnamen je `<target>:<entity_id>`; fehlt der Name, steht nur die Art. */
  names: Record<string, string>
  /** Version je `version_id` aus den `addressed`-Ereignissen. */
  versions: Record<string, ResolvedVersion>
  loading: boolean
  notFound: boolean
  error: string | null
  reload: () => void
}

const elementKey = (target: CaseTarget, entityId: string) => `${target}:${entityId}`

/**
 * `GET /cases/{id}` plus Agenten (Titel, Akteure) und die Namen der
 * zugeordneten Elemente. 404 ist fuer viewer auch der fremde Fall (der Server
 * unterscheidet das bewusst nicht).
 */
function useCaseDetail(caseId: string | undefined): CaseDetailData {
  const api = useApi()
  const wsPath = useWorkspacePath()
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [names, setNames] = useState<Record<string, string>>({})
  const [versions, setVersions] = useState<Record<string, ResolvedVersion>>({})
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (caseId === undefined) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setNotFound(false)
    api
      .getCase(caseId)
      .then((loaded) => {
        if (!cancelled) setDetail(loaded)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        if (cause instanceof ApiError && cause.status === 404) setNotFound(true)
        else setError(messageOf(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, caseId, nonce])

  useEffect(() => {
    let cancelled = false
    api
      .listAgents()
      .then((list) => {
        if (!cancelled) setAgents(list)
      })
      .catch(() => {
        if (!cancelled) setAgents([])
      })
    return () => {
      cancelled = true
    }
  }, [api])

  // Namen der Elemente aus Zuordnung und Verlauf. Scheitert ein Abruf (z. B.
  // geloeschtes Element), bleibt es bei der Art ohne Namen.
  useEffect(() => {
    if (detail === null) return
    let cancelled = false
    const wanted = new Map<string, { target: CaseTarget; id: string }>()
    for (const element of detail.elements) {
      if (element.entity_id !== null) {
        wanted.set(elementKey(element.target, element.entity_id), {
          target: element.target,
          id: element.entity_id,
        })
      }
    }
    for (const event of detail.events) {
      if (event.element_target !== null && event.element_entity_id !== null) {
        wanted.set(elementKey(event.element_target, event.element_entity_id), {
          target: event.element_target,
          id: event.element_entity_id,
        })
      }
    }
    const fetchName = (target: CaseTarget, id: string): Promise<string> | null => {
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
          // Gedaechtnis: der Eintrag kann personenbezogen sein, er erscheint
          // hier nur als Art.
          return null
      }
    }
    const jobs = [...wanted.entries()].map(([key, { target, id }]) => {
      const job = fetchName(target, id)
      return job === null
        ? Promise.resolve(null)
        : job.then(
            (name) => [key, name] as const,
            () => null,
          )
    })
    void Promise.all(jobs).then((results) => {
      if (cancelled) return
      const next: Record<string, string> = {}
      for (const entry of results) if (entry !== null) next[entry[0]] = entry[1]
      setNames(next)
    })
    return () => {
      cancelled = true
    }
  }, [api, detail])

  // Version eines `addressed`-Ereignisses: `CaseEvent` traegt nur Art und
  // Versions-ID. Gesucht wird in den Versionslisten der Elemente dieser Art,
  // die der Fall zugeordnet hat oder hatte.
  useEffect(() => {
    if (detail === null) return
    const addressed = detail.events.filter(
      (event) => event.event === 'addressed' && event.version_id !== null,
    )
    if (addressed.length === 0) return
    let cancelled = false
    const candidates = new Map<string, { type: VersionedEntityType; id: string }>()
    const consider = (target: CaseTarget | null, id: string | null) => {
      if (target === null || id === null || !isVersioned(target)) return
      candidates.set(elementKey(target, id), { type: target, id })
    }
    for (const element of detail.elements) consider(element.target, element.entity_id)
    for (const event of detail.events) consider(event.element_target, event.element_entity_id)
    const wantedTypes = new Set(addressed.map((event) => event.version_entity_type))

    const listVersions = (type: VersionedEntityType, id: string) => {
      switch (type) {
        case 'persona':
          return Promise.all([api.getPersona(id), api.listPersonaVersions(id)])
        case 'playbook':
          return Promise.all([api.getPlaybook(id), api.listPlaybookVersions(id)])
        case 'resource':
          return Promise.all([api.getResource(id), api.listResourceVersions(id)])
        case 'external_tool':
          return Promise.all([api.getExternalTool(id), api.listExternalToolVersions(id)])
        case 'system_prompt_template':
          return Promise.all([
            api.getSystemPromptTemplate(id),
            api.listSystemPromptTemplateVersions(id),
          ])
      }
    }
    const jobs = [...candidates.values()]
      .filter(({ type }) => wantedTypes.has(type))
      .map(({ type, id }) =>
        listVersions(type, id).then(
          ([entity, list]) => ({ type, id, name: entity.name, list }),
          () => null,
        ),
      )
    void Promise.all(jobs).then((results) => {
      if (cancelled) return
      const next: Record<string, ResolvedVersion> = {}
      for (const result of results) {
        if (result === null) continue
        const meta = ELEMENT_PATH[result.type]
        for (const version of result.list) {
          next[version.id] = {
            name: result.name,
            version: version.version,
            path: wsPath(
              `/${meta.segment}/${result.id}${meta.versionsTab ? '?tab=versions' : ''}`,
            ),
          }
        }
      }
      setVersions(next)
    })
    return () => {
      cancelled = true
    }
    // `wsPath` ist je Render neu, der Workspace aber derselbe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, detail])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { detail, agents, names, versions, loading, notFound, error, reload }
}

/**
 * Pruefaelle aus diesem Fall (`GET /test-cases?origin_case_id=`, Q5/D6-API2).
 * Nur editor (Spec S8: „Verknüpft“ ist editor-Sicht); `undefined` laedt nichts.
 */
function useLinkedTestCases(caseId: string | undefined) {
  const api = useApi()
  const [testCases, setTestCases] = useState<TestCaseRead[] | null>(null)
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    if (caseId === undefined) return
    let cancelled = false
    api.listTestCases({ origin_case_id: caseId }).then(
      (list) => {
        if (!cancelled) setTestCases(list)
      },
      () => {
        if (!cancelled) setTestCases([])
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, caseId, nonce])
  const reload = useCallback(() => setNonce((value) => value + 1), [])
  return { testCases, reload }
}

// Reviews zum Fall (E5h, wie Agent-Tab §3.4): hoechstens 10, je eines ein
// `getSession`, parallel. Kein Request je Element oder Ereignis.
const CASE_REVIEW_LIMIT = 10

/** Eine Aenderung, die diesen Fall enthaelt, mit ihrem Review. */
interface CaseChange {
  session: SessionRead
  measure: MeasureRead
}

/**
 * Aenderungen zum Fall aus `GET /feedback-sessions?case_id=` (QE1 a) und den
 * eingebetteten Aenderungen. Nur editor (Spec §6.2); `undefined` laedt nichts.
 * Uebernommen wird nur, was der Server selbst verknuepft: das Review gehoert
 * zum Agenten des Falls und nennt den Fall, die Aenderung gehoert zu diesem
 * Review und nennt den Fall. Scheitert ein Abruf, fehlt der Teil still.
 */
function useCaseChanges(caseId: string | undefined, agentId: string | undefined) {
  const api = useApi()
  const [changes, setChanges] = useState<CaseChange[] | null>(null)
  const [nonce, setNonce] = useState(0)
  useEffect(() => {
    if (caseId === undefined || agentId === undefined) return
    let cancelled = false
    const run = async () => {
      const page = await api.listSessions({ case_id: caseId }, { limit: CASE_REVIEW_LIMIT })
      const rows = page.items
        .slice(0, CASE_REVIEW_LIMIT)
        .filter((row) => row.agent_id === agentId && row.case_ids.includes(caseId))
      const details = await Promise.all(
        rows.map((row) =>
          api.getSession(row.id).then(
            (detail) => (detail.session.id === row.id ? detail : null),
            () => null,
          ),
        ),
      )
      const next: CaseChange[] = []
      for (const detail of details) {
        if (detail === null) continue
        for (const measure of detail.measures) {
          if (measure.session_id !== detail.session.id || !measure.case_ids.includes(caseId)) continue
          next.push({ session: detail.session, measure })
        }
      }
      if (!cancelled) setChanges(next)
    }
    run().catch(() => {
      if (!cancelled) setChanges([])
    })
    return () => {
      cancelled = true
    }
  }, [api, caseId, agentId, nonce])
  const reload = useCallback(() => setNonce((value) => value + 1), [])
  // Ohne Freigabe (viewer) nie alte Daten zeigen, auch nach Rollenwechsel.
  return { changes: caseId === undefined || agentId === undefined ? null : changes, reload }
}

/**
 * Faellig-Pill bzw. „Nachkontrolle am …“ einer Aenderung (wie `ChangeDueMark`
 * im Review-Ergebnis, dieselben Texte und dieselbe Funktion `followUpStatusOf`
 * mit dem Server-Zustand). Lokal, weil das Gate den Komponenten-Import aus
 * `features/evolution` sperrt.
 */
function CaseChangeDueMark({ change }: { change: CaseChange }) {
  const { t } = useTranslation('sessions')
  const status = followUpStatusOf(change.measure, change.session)
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

/** `source_ref` nur als Link, wenn es eine http(s)-Adresse ist (Spec S8). */
function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}

function StatusLabel({
  status,
  addressedTo,
  statusRef,
}: {
  status: CaseStatus
  addressedTo: ResolvedVersion | null
  statusRef?: Ref<HTMLSpanElement>
}) {
  const { t } = useTranslation('feedback')
  const label =
    status === 'addressed'
      ? addressedTo !== null
        ? t('cases.status.addressed', { element: addressedTo.name, version: addressedTo.version })
        : t('cases.status.addressedShort')
      : t(`cases.status.${status}`)
  return (
    // Nach einem Uebergang landet der Fokus hier, `aria-live` meldet den
    // neuen Status (Spec Barrierefreiheit).
    <span
      ref={statusRef}
      tabIndex={-1}
      aria-live="polite"
      className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      data-testid="case-status"
    >
      <CaseStatusDot status={status} />
      {label}
    </span>
  )
}

function DetailSkeleton() {
  const { t } = useTranslation('data')
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-live="polite">
      <span className="sr-only">{t('loading')}</span>
      <div className="flex items-center gap-4">
        <Skeleton className="size-12 rounded-xl" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-7 w-2/3 max-w-sm" />
          <Skeleton className="h-4 w-1/3 max-w-40" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3].map((index) => (
          <Skeleton key={index} className="h-32 w-full rounded-xl" data-testid="case-detail-skeleton" />
        ))}
      </div>
    </div>
  )
}

function DeleteCaseDialog({
  open,
  onOpenChange,
  fromLesson,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  fromLesson: boolean
  onConfirm: () => Promise<void>
}) {
  const { t } = useTranslation(['feedback', 'common'])
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      await onConfirm()
    } catch {
      // Review-Nit N2 (D6c): eigener Text statt der rohen Server-Meldung.
      notify.error(t('feedback:cases.delete.error'))
      setBusy(false)
    }
  }
  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent data-testid="case-delete-dialog">
        <DialogHeader>
          <DialogTitle>{t('feedback:cases.delete.title')}</DialogTitle>
          <DialogDescription>{t('feedback:cases.delete.body')}</DialogDescription>
        </DialogHeader>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted-foreground">
          {fromLesson ? <li>{t('feedback:cases.delete.lesson')}</li> : null}
          <li>{t('feedback:cases.delete.testCases')}</li>
        </ul>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy}
            aria-busy={busy}
            onClick={() => void submit()}
          >
            {t('feedback:cases.delete.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * „Verknüpft“ (Spec S8, nur editor): Pruefaelle aus diesem Fall, die Quelle
 * (Lernvorschlag → Memory-Sheet, Alt-Feedback → Feedback-Detail) und der
 * Link zum Lauf. `source_ref` wird nur bei http(s) ein Link, sonst Text.
 */
function LinkedSection({
  testCases,
  changes,
  changeElement,
  sourceMemoryId,
  sourceFeedbackId,
  sourceRef,
  agentId,
}: {
  testCases: TestCaseRead[] | null
  changes: CaseChange[] | null
  changeElement: (measure: MeasureRead) => string
  sourceMemoryId: string | null
  sourceFeedbackId: string | null
  sourceRef: string | null
  agentId: string
}) {
  const { t } = useTranslation(['feedback', 'sessions'])
  const wsPath = useWorkspacePath()
  const refUrl = sourceRef !== null ? safeHttpUrl(sourceRef) : null
  const rows =
    (testCases ?? []).length +
    (changes ?? []).length +
    (sourceMemoryId ? 1 : 0) +
    (sourceFeedbackId ? 1 : 0) +
    (sourceRef ? 1 : 0)
  if (rows === 0) return null
  const link = 'font-medium break-words text-brand hover:underline'
  return (
    <Card data-testid="case-linked">
      <CardHeader>
        <CardTitle>{t('cases.detail.linked.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2 text-sm">
          {/* Je Aenderung zwei Zeilen (Spec §6.2): Review, dann Aenderung mit
              Zustand vom Server und Faellig-Pill bzw. Termin. */}
          {(changes ?? []).flatMap(({ session, measure }) => {
            const reviewPath = wsPath(`/agents/${session.agent_id}/reviews/${session.id}`)
            return [
              <li key={`${measure.id}:review`} className="min-w-0" data-testid="case-linked-review">
                <Link to={reviewPath} className={link}>
                  {t('cases.detail.linked.session', { date: formatDay(session.created_at) })}
                </Link>
              </li>,
              <li
                key={`${measure.id}:change`}
                className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1"
                data-testid="case-linked-change"
              >
                <Link to={`${reviewPath}?change=${encodeURIComponent(measure.id)}`} className={link}>
                  {t('cases.detail.linked.measure', {
                    element: changeElement(measure),
                    state: t(`sessions:measure.state.${measure.state}`),
                  })}
                </Link>
                <CaseChangeDueMark change={{ session, measure }} />
              </li>,
            ]
          })}
          {(testCases ?? []).map((testCase) => (
            <li key={testCase.id} className="min-w-0">
              <Link to={wsPath(`/agents/${agentId}#tests`)} className={link}>
                {t('cases.detail.linked.testCase', { title: testCase.title })}
              </Link>
            </li>
          ))}
          {sourceMemoryId ? (
            <li className="min-w-0">
              <Link
                to={wsPath(`/memory?entry=${encodeURIComponent(sourceMemoryId)}`)}
                className={link}
              >
                {t('cases.detail.linked.lesson')}
              </Link>
            </li>
          ) : null}
          {sourceFeedbackId ? (
            <li className="min-w-0">
              <Link
                to={wsPath(`/feedback/item/${encodeURIComponent(sourceFeedbackId)}`)}
                className={link}
              >
                {t('cases.detail.linked.feedback')}
              </Link>
            </li>
          ) : null}
          {sourceRef ? (
            <li className="flex min-w-0 flex-col gap-0.5" data-testid="case-source-ref">
              <span className="text-xs text-muted-foreground">{t('cases.detail.linked.sourceRef')}</span>
              {refUrl !== null ? (
                // RR7-`Link` erkennt absolute URLs und rendert sie als normalen
                // externen Link (Lint verbietet rohes <a>).
                <Link
                  to={refUrl}
                  reloadDocument
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(link, 'inline-flex items-center gap-1 wrap-anywhere')}
                >
                  {sourceRef}
                  <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                </Link>
              ) : (
                <span className="wrap-anywhere">{sourceRef}</span>
              )}
            </li>
          ) : null}
        </ul>
      </CardContent>
    </Card>
  )
}

function Actor({ event, agents, userId }: { event: CaseEvent; agents: Agent[]; userId: string | null }) {
  const { t } = useTranslation('learning')
  if (event.actor_kind === 'system') return <span>{t('history.actor.system')}</span>
  if (event.actor_kind === 'agent') {
    const name = agents.find((agent) => agent.id === event.actor_id)?.name ?? null
    return (
      <span className="inline-flex min-w-0 items-center gap-1 break-words">
        <Bot className="size-3.5 shrink-0" aria-hidden="true" />
        {name !== null ? t('history.actor.by', { name }) : t('history.actor.agentUnknown')}
      </span>
    )
  }
  // Mitglieder-Namen liest nur admin (`GET /members`); deshalb ohne Namen.
  if (event.actor_id !== null && event.actor_id === userId) return <span>{t('history.actor.you')}</span>
  return <span>{t('history.actor.humanUnknown')}</span>
}

/**
 * Fall-Detail lesend (Delta-Spec S8, ADR-0053 D6c). Kopf mit Status, SBI im
 * 2×2-Raster ab `md`, Schilderung des Agenten, Zuordnung (nur editor) und
 * Verlauf. Triage-Aktionen und „Verknüpft“ folgen mit D6d. „Fall löschen…“
 * ab editor (Q6, `DELETE /cases/{id}`): Hard-Delete samt Verlauf.
 */
export function CaseDetailPage() {
  const { t, i18n } = useTranslation(['feedback', 'learning', 'common'])
  const { caseId } = useParams<{ caseId: string }>()
  const [params] = useSearchParams()
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const { me } = useSession()
  const isEditor = role === 'editor' || role === 'admin'
  const data = useCaseDetail(caseId)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const historyId = useId()
  const statusRef = useRef<HTMLSpanElement>(null)
  const focusStatus = useRef(false)
  const linked = useLinkedTestCases(isEditor ? caseId : undefined)
  // Einzige Rollen-Sperre fuer E5h: viewer laden nichts, also gibt es fuer
  // sie weder Aenderungen noch Pill noch Verlauf-Links.
  const caseChanges = useCaseChanges(
    isEditor ? caseId : undefined,
    isEditor ? data.detail?.case.agent_id : undefined,
  )
  const changes = caseChanges.changes
  // Aenderung je ID, nur aus den geladenen Reviews (Verlauf-Link „Zur Änderung“).
  const changeById = useMemo(
    () => new Map((changes ?? []).map((change) => [change.measure.id, change])),
    [changes],
  )
  const followUpDue = (changes ?? []).some(({ measure, session }) =>
    isDue(followUpStatusOf(measure, session)),
  )
  // Ziel von „Zur Änderung“ im Verlauf; `null` = kein Link, weil die Aenderung
  // in keinem geladenen Review steckt. viewer laden keine Reviews und sehen
  // deshalb nie einen Link; die Rollen-Sperre sitzt an genau einer Stelle
  // (`useCaseChanges` oben).
  const historyChangePath = (event: CaseEvent): string | null => {
    if (event.measure_id === null) return null
    const change = changeById.get(event.measure_id)
    if (change === undefined) return null
    const { session, measure } = change
    return wsPath(
      `/agents/${session.agent_id}/reviews/${session.id}?change=${encodeURIComponent(measure.id)}`,
    )
  }

  // Nach einem Uebergang: Fokus auf das Status-Wort, sobald der neue Stand da ist.
  const detailForFocus = data.detail
  useEffect(() => {
    if (!focusStatus.current || data.loading || detailForFocus === null) return
    focusStatus.current = false
    statusRef.current?.focus()
  }, [detailForFocus, data.loading])

  const onChanged = (transitioned: boolean) => {
    if (transitioned) focusStatus.current = true
    data.reload()
    caseChanges.reload()
  }

  // Rueckweg auf die Liste mit den Filtern, mit denen man gekommen ist.
  const backHref = useMemo(() => {
    const back = new URLSearchParams({ tab: 'cases' })
    for (const key of LIST_FILTER_KEYS) {
      for (const value of params.getAll(key)) back.append(key, value)
    }
    return wsPath(`/feedback?${back.toString()}`)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  const detail = data.detail
  const item = detail?.case ?? null
  const agentName =
    item !== null
      ? (data.agents.find((agent) => agent.id === item.agent_id)?.name ??
        t('learning:approval.unknownAgent'))
      : ''

  const elementLabel = (target: CaseTarget | null, entityId: string | null): string => {
    if (target === null) return ''
    const kind = t(`feedback:cases.target.${target}`)
    const name = entityId !== null ? data.names[elementKey(target, entityId)] : undefined
    return name !== undefined ? `${kind}: ${name}` : kind
  }

  // Wie im Review-Ergebnis: Art und Name, Name nur aus den schon geladenen
  // Namen des Falls (kein Request je Aenderung).
  const changeElement = (measure: MeasureRead): string => {
    const kind = t(`feedback:cases.target.${measure.target}`)
    const name =
      measure.entity_id !== null ? data.names[elementKey(measure.target, measure.entity_id)] : undefined
    return name !== undefined ? `${kind} „${name}“` : kind
  }

  const latestAddressed =
    detail !== null
      ? [...detail.events].reverse().find((event) => event.event === 'addressed') ?? null
      : null
  const addressedTo =
    latestAddressed?.version_id != null ? (data.versions[latestAddressed.version_id] ?? null) : null

  // Aenderung fuer den naechsten Schritt (E-Delta §6.3, E5i): nur aus den
  // vom Server verknuepften Aenderungen (`useCaseChanges`), „offen“ aus dem
  // Server-Zustand `measure.state`, nicht aus den Events nachgerechnet.
  const caseMeasure = useMemo((): CaseMeasureRef | null => {
    if (detail === null || changes === null) return null
    const eventMeasureIds = [...detail.events]
      .reverse()
      .map((event) => event.measure_id)
      .filter((id): id is string => id !== null)
    return pickCaseMeasure(
      detail.case.status,
      eventMeasureIds,
      changes.map(({ session, measure }) => ({
        sessionId: session.id,
        measureId: measure.id,
        open: !isClosedState(measure.state),
      })),
    )
  }, [detail, changes])

  const eventLabel = (event: CaseEvent): string => {
    if (!KNOWN_EVENTS.has(event.event)) return t('feedback:cases.history.event.unknown')
    // Folgen der Nachkontrolle bzw. der Aktivierung setzt der Server (ADR-0053
    // 3.3, F3 a): eigene Woerter, damit sie nicht wie ein Handgriff aussehen.
    const bySystem = event.actor_kind === 'system'
    if (event.event === 'addressed') {
      const version = event.version_id !== null ? data.versions[event.version_id] : undefined
      return version !== undefined
        ? t(
            bySystem
              ? 'feedback:cases.history.event.addressedOnActivation'
              : 'feedback:cases.history.event.addressed',
            { element: version.name, version: version.version },
          )
        : t('feedback:cases.status.addressedShort')
    }
    if (event.event === 'reopened' && bySystem && event.measure_id !== null) {
      return t('feedback:cases.history.event.reopenedByFollowUp', { note: event.note ?? '' })
    }
    if (event.event === 'element_assigned' || event.event === 'element_unassigned') {
      return t(`feedback:cases.history.event.${event.event}`, {
        element: elementLabel(event.element_target, event.element_entity_id),
      })
    }
    if (NOTE_IN_LABEL.has(event.event)) {
      return t(`feedback:cases.history.event.${event.event}`, { note: event.note ?? '' })
    }
    return t(`feedback:cases.history.event.${event.event}`)
  }

  const onCopyId = () => {
    if (item === null) return
    void copyToClipboard(item.id)
      .then(() => notify.success(t('feedback:cases.detail.idCopied')))
      .catch((cause: unknown) => notify.error(messageOf(cause)))
  }

  const onDelete = async () => {
    if (item === null) return
    await api.deleteCase(item.id)
    notify.success(t('feedback:cases.delete.success'))
    navigate(backHref)
  }

  if (data.loading && detail === null) {
    return (
      <Container>
        <DetailSkeleton />
      </Container>
    )
  }

  if (data.notFound || caseId === undefined) {
    return (
      <Container>
        <EmptyState
          icon={MessageSquareWarning}
          title={t('feedback:cases.detail.notFound')}
          action={
            <Button asChild variant="outline">
              <Link to={backHref}>{t('feedback:cases.detail.toList')}</Link>
            </Button>
          }
        />
      </Container>
    )
  }

  if (item === null || detail === null) {
    return (
      <Container>
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert message={data.error ?? ''} />
          <Button type="button" variant="outline" onClick={data.reload}>
            {t('common:actions.retry')}
          </Button>
        </div>
      </Container>
    )
  }

  const blocks = [
    { key: 'situation', text: item.situation },
    { key: 'behavior', text: item.behavior },
    { key: 'expected', text: item.expected_behavior },
    { key: 'impact', text: item.impact },
  ].filter((block): block is { key: string; text: string } => (block.text ?? '').trim() !== '')

  // Die neueste Schilderung gilt (append-only, Server sortiert absteigend).
  const statement = detail.statements[0] ?? null
  const statementRows = statement
    ? [
        { key: 'followed', text: statement.followed_instruction },
        { key: 'missing', text: statement.missing_information },
        { key: 'conflict', text: statement.conflict },
      ].filter((row) => row.text.trim() !== '')
    : []

  const newestFirst = [...detail.events].reverse()
  const reportedOn = new Date(item.created_at).toLocaleDateString(i18n.language, {
    dateStyle: 'long',
  })

  return (
    <Container>
      <div className="flex flex-col gap-6">
        <DetailHeader
          icon={MessageSquareWarning}
          iconTone="catalog"
          title={t('feedback:cases.detail.title', { agent: agentName })}
          backHref={backHref}
          backLabel={t('feedback:cases.detail.back')}
          status={
            <>
              <StatusLabel status={item.status} addressedTo={addressedTo} statusRef={statusRef} />
              {/* Spec §6.2: Nachkontrolle ist editor-Aufgabe. viewer laden keine
                  Aenderungen (`useCaseChanges`), also auch keine Pill. */}
              {followUpDue ? (
                <MetaPill tone="brand" icon={CalendarClock}>
                  <span data-testid="case-follow-up-due">{t('sessions:measure.due')}</span>
                </MetaPill>
              ) : null}
            </>
          }
          badges={
            // Rueckweg zum Agenten (Neuschnitt §6), fuer editor und viewer.
            <Link
              to={wsPath(`/agents/${item.agent_id}?tab=evolution`)}
              className="text-xs font-medium break-words text-brand hover:underline"
              data-testid="case-to-evolution"
            >
              {t('feedback:cases.detail.toEvolution', { agent: agentName })}
            </Link>
          }
          description={t('feedback:cases.detail.reported', { date: reportedOn })}
          actions={
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="size-11 md:size-9"
                  aria-label={t('feedback:cases.detail.actions')}
                  data-testid="case-overflow"
                >
                  <MoreHorizontal aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={onCopyId}>
                  <Copy aria-hidden="true" />
                  {t('feedback:cases.detail.copyId')}
                </DropdownMenuItem>
                {isEditor ? (
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onSelect={() => setDeleteOpen(true)}
                  >
                    <Trash2 aria-hidden="true" />
                    {t('feedback:cases.delete.action')}
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          }
        />

        {EXPLAINED_STATUSES.has(item.status) ? (
          <p className="-mt-3 text-sm text-muted-foreground" data-testid="case-status-explain">
            {t(`feedback:cases.status.explain.${item.status}`)}
          </p>
        ) : null}

        {/* Erst rendern, wenn Prueffaelle und Aenderungen da sind: sonst
            springt die Hauptaktion nach dem Laden (z. B. Zur Version →
            Zur Nachkontrolle). */}
        {isEditor && linked.testCases !== null && changes !== null ? (
          <CaseActions
            detail={detail}
            agent={data.agents.find((agent) => agent.id === item.agent_id) ?? null}
            names={data.names}
            addressedPath={addressedTo?.path ?? null}
            hasTestCase={linked.testCases.length > 0}
            measure={caseMeasure}
            onChanged={onChanged}
            onTestCaseCreated={linked.reload}
          />
        ) : null}

        <section className="flex flex-col gap-3" aria-label={t('feedback:cases.detail.contentAria')}>
          <div className="grid gap-4 md:grid-cols-2">
            {blocks.map((block) => (
              <Card key={block.key} data-testid={`case-block-${block.key}`}>
                <CardHeader>
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {t(`feedback:cases.detail.block.${block.key}`)}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm wrap-anywhere whitespace-pre-wrap">{block.text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t('feedback:cases.detail.immutable')}</p>
        </section>

        {statement !== null ? (
          <Card data-testid="case-statement">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2">
                {t('feedback:cases.detail.statement.title')}
                <Badge variant="secondary">{t('feedback:cases.detail.statement.badge')}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="flex flex-col gap-3 text-sm">
                {statementRows.map((row) => (
                  <div key={row.key} className="flex min-w-0 flex-col gap-1">
                    <dt className="text-xs font-medium text-muted-foreground">
                      {t(`feedback:cases.detail.statement.${row.key}`)}
                    </dt>
                    <dd className="wrap-anywhere whitespace-pre-wrap">{row.text}</dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        ) : null}

        {isEditor ? (
          <Card data-testid="case-assignment">
            <CardHeader>
              <CardTitle>{t('feedback:cases.detail.assignment.title')}</CardTitle>
            </CardHeader>
            <CardContent>
              {detail.elements.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t('feedback:cases.detail.assignment.none')}
                </p>
              ) : (
                <ul className="flex flex-wrap gap-2">
                  {detail.elements.map((element) => (
                    <li key={element.id}>
                      <Badge variant="outline" className="max-w-full wrap-anywhere whitespace-normal">
                        {elementLabel(element.target, element.entity_id)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        ) : null}

        {isEditor ? (
          <LinkedSection
            testCases={linked.testCases}
            changes={changes}
            changeElement={changeElement}
            sourceMemoryId={item.source_memory_id}
            sourceFeedbackId={item.source_feedback_id}
            sourceRef={item.source_ref}
            agentId={item.agent_id}
          />
        ) : null}

        <Card>
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
            <CardTitle>{t('feedback:cases.history.title')}</CardTitle>
            {/* Unter `md` ist der Verlauf eingeklappt (Spec S8, 390 px). */}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="min-h-11 md:hidden"
              aria-expanded={historyOpen}
              aria-controls={historyId}
              onClick={() => setHistoryOpen((value) => !value)}
            >
              {historyOpen ? t('common:actions.showLess') : t('common:actions.showMore')}
            </Button>
          </CardHeader>
          <CardContent id={historyId} className={cn(historyOpen ? 'block' : 'hidden', 'md:block')}>
            <ol className="flex flex-col gap-4" data-testid="case-history">
              {newestFirst.map((event) => (
                <li
                  key={event.id}
                  className="flex min-w-0 flex-col gap-1 border-l-2 border-border pl-3"
                  data-testid="case-history-item"
                >
                  <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 text-sm">
                    <time
                      dateTime={event.created_at}
                      className="text-xs text-muted-foreground tabular-nums"
                    >
                      {new Date(event.created_at).toLocaleString(i18n.language, {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}
                    </time>
                    {event.event === 'addressed' &&
                    event.version_id !== null &&
                    data.versions[event.version_id] !== undefined ? (
                      <Link
                        to={data.versions[event.version_id].path}
                        className="font-medium break-words text-brand hover:underline"
                      >
                        {eventLabel(event)}
                      </Link>
                    ) : (
                      <span className="font-medium break-words">{eventLabel(event)}</span>
                    )}
                    {/* E5h: nur editor und nur, wenn die Aenderung in den
                        geladenen Reviews steckt; sonst kein toter Link. */}
                    {historyChangePath(event) !== null ? (
                      <Link
                        to={historyChangePath(event) ?? ''}
                        className="text-xs font-medium text-brand hover:underline"
                        data-testid="case-history-to-change"
                      >
                        {t('feedback:cases.history.toMeasure')}
                      </Link>
                    ) : null}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <Actor event={event} agents={data.agents} userId={me?.user_id ?? null} />
                  </p>
                  {event.note !== null && event.note !== '' && !NOTE_IN_LABEL.has(event.event) ? (
                    <p className="text-xs break-words text-muted-foreground">{event.note}</p>
                  ) : null}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {isEditor ? (
        <DeleteCaseDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          fromLesson={item.source_memory_id !== null}
          onConfirm={onDelete}
        />
      ) : null}
    </Container>
  )
}
