import {
  CalendarClock,
  Copy,
  ExternalLink,
  MessagesSquare,
  MonitorSmartphone,
  MoreHorizontal,
  Replace,
} from 'lucide-react'
import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type {
  Agent,
  CaseRead,
  CaseStatus,
  Member,
  MeasureRead,
  MeasureTarget,
  SessionDetail,
  SessionParticipantKind,
  SessionRead,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner, DetailHeader } from '@/components/data'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { BuilderPromptCopy } from '@/features/evolution/components/BuilderPromptCopy'
import { followUpStatus, isDue, parseDay } from '@/features/evolution/lib/followUp'
import { CaseStatusDot } from '@/components/cases/CaseStatusDot'
import { copyToClipboard } from '@/lib/clipboard'
import { formatDate, formatDateTime } from '@/lib/dates'
import { notify } from '@/lib/feedback'
import { safeInternalPath } from '@/lib/safePath'
import { cn } from '@/lib/utils'

// Review-Ergebnis (Neuschnitt §2, §4; E5-Delta §2). Code-Namen bleiben bei der
// API (Session = Review-Ergebnis, Measure = Aenderung), die Texte folgen A4a.
//
// Rechte (E5-Delta §0.3): Lesen ab `editor`. Ein viewer bekommt per Deep-Link
// dieselbe Darstellung wie ein unbekanntes Review (QE3 `session_not_found`).
// Fuer ihn wird nichts geladen, damit kein Inhalt aufblitzt.
//
// Korrektur (ADR-0053 3.5): `supersedes_id` steht am Review-Ergebnis; den
// umgekehrten Verweis `superseded_by_id` liefert nur die Liste (QE2 a,
// `SessionListItem`). Die Seite liest ihn deshalb aus `listSessions` des
// Agenten (neueste zuerst). Der Nachfolger ist neuer und steht damit vor der
// eigenen Zeile. Gezeigt werden nur direkter Vorgaenger und Nachfolger.

// Seiten der Liste, die fuer den Nachfolger hoechstens gelesen werden
// (`limit` = Server-Hoechstwert 200): 1 000 Reviews eines Agenten.
const SUCCESSOR_PAGE_LIMIT = 200
const SUCCESSOR_MAX_PAGES = 5

// Kalendertag als „25.09.2026“ (Skizze `review-ergebnis-*`).
const DAY_FORMAT: Intl.DateTimeFormatOptions = { day: '2-digit', month: '2-digit', year: 'numeric' }

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

/** `YYYY-MM-DD` (lokal) bzw. ISO-Zeitstempel als Datum der Oberflaeche. */
function formatDay(value: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? formatDate(parseDay(value), DAY_FORMAT)
    : formatDate(value, DAY_FORMAT)
}

/** `standard_ref` nur bei http(s) als Link (E5-Delta §2). */
function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}

interface Successor {
  id: string
  created_at: string
}

interface ReviewData {
  detail: SessionDetail | null
  agents: Agent[] | null
  members: Member[] | null
  /** Direkter Vorgaenger (`supersedes_id`), `null` = keiner oder nicht ladbar. */
  predecessor: SessionRead | null
  /** `undefined` = noch nicht ermittelt, `null` = nicht ersetzt. */
  successor: Successor | null | undefined
  cases: CaseRead[] | null
  testCaseTitles: Record<string, string>
  elementNames: Record<string, string>
  loading: boolean
  notFound: boolean
  error: string | null
  reload: () => void
}

const elementKey = (target: MeasureTarget, entityId: string) => `${target}:${entityId}`

/**
 * `GET /feedback-sessions/{id}` plus alles, was die Seite aufloest: Agenten
 * und Mitglieder (Teilnehmende), Vorgaenger, Nachfolger, Rueckmeldungen,
 * Prueffall-Titel und Elementnamen. `enabled = false` laedt nichts (viewer).
 */
function useReviewDetail(sessionId: string | undefined, enabled: boolean): ReviewData {
  const api = useApi()
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [agents, setAgents] = useState<Agent[] | null>(null)
  const [members, setMembers] = useState<Member[] | null>(null)
  const [predecessor, setPredecessor] = useState<SessionRead | null>(null)
  const [successor, setSuccessor] = useState<Successor | null | undefined>(undefined)
  const [cases, setCases] = useState<CaseRead[] | null>(null)
  const [testCaseTitles, setTestCaseTitles] = useState<Record<string, string>>({})
  const [elementNames, setElementNames] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  // Die Seite montiert je `sessionId` neu (`key`, s. `ReviewDetailPage`);
  // Effekte setzen deshalb nichts zurueck, nur `reload` tut es im Handler.
  useEffect(() => {
    if (!enabled || sessionId === undefined) return
    let cancelled = false
    api
      .getSession(sessionId)
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
  }, [api, sessionId, enabled, nonce])

  // Namen der Teilnehmenden: Agenten und Mitglieder (`GET /members` ab
  // viewer). Scheitert ein Abruf, greifen die Fallbacks.
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api.listAgents().then(
      (list) => {
        if (!cancelled) setAgents(list)
      },
      () => {
        if (!cancelled) setAgents([])
      },
    )
    api.listMembers().then(
      (list) => {
        if (!cancelled) setMembers(list)
      },
      () => {
        if (!cancelled) setMembers([])
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, enabled])

  const session = detail?.session ?? null

  // Vorgaenger: ein Abruf, nur fuer sein Datum.
  useEffect(() => {
    if (session?.supersedes_id == null) return
    let cancelled = false
    api.getSession(session.supersedes_id).then(
      (loaded) => {
        if (!cancelled) setPredecessor(loaded.session)
      },
      () => undefined,
    )
    return () => {
      cancelled = true
    }
  }, [api, session?.supersedes_id])

  // Nachfolger aus der Liste des Agenten (s. Kopf).
  useEffect(() => {
    if (session === null) return
    let cancelled = false
    const scan = async (): Promise<Successor | null> => {
      const seen = new Map<string, string>()
      let cursor: string | undefined
      for (let page = 0; page < SUCCESSOR_MAX_PAGES; page += 1) {
        const result = await api.listSessions(
          { agent_id: session.agent_id },
          { cursor, limit: SUCCESSOR_PAGE_LIMIT },
        )
        for (const row of result.items) {
          seen.set(row.id, row.created_at)
          if (row.id === session.id) {
            const nextId = row.superseded_by_id
            if (nextId === null) return null
            return { id: nextId, created_at: seen.get(nextId) ?? row.created_at }
          }
        }
        if (result.next_cursor === null) return null
        cursor = result.next_cursor
      }
      return null
    }
    scan().then(
      (found) => {
        if (!cancelled) setSuccessor(found)
      },
      () => {
        // Ohne Liste bleibt der Nachfolger unbekannt; der Korrektur-Block
        // erscheint dann trotzdem (ein doppelter Auftrag an den Builder ist
        // harmlos, ein fehlender Weg zur Korrektur nicht).
        if (!cancelled) setSuccessor(null)
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, session])

  // Rueckmeldungen: geloeschte (404) fehlen still (PM-6 kappt die Verknuepfung).
  useEffect(() => {
    if (session === null) return
    let cancelled = false
    void Promise.all(
      session.case_ids.map((id) =>
        api.getCase(id).then(
          (loaded) => loaded.case,
          () => null,
        ),
      ),
    ).then((rows) => {
      if (!cancelled) setCases(rows.filter((row): row is CaseRead => row !== null))
    })
    return () => {
      cancelled = true
    }
  }, [api, session])

  // Prueffall-Titel und Elementnamen der Aenderungen.
  useEffect(() => {
    if (detail === null) return
    let cancelled = false
    const testIds = [...new Set(detail.measures.map((measure) => measure.test_case_id))]
    void Promise.all(
      testIds.map((id) =>
        api.getTestCase(id).then(
          (testCase) => [id, testCase.title] as const,
          () => null,
        ),
      ),
    ).then((rows) => {
      if (cancelled) return
      const next: Record<string, string> = {}
      for (const row of rows) if (row !== null) next[row[0]] = row[1]
      setTestCaseTitles(next)
    })

    const fetchName = (target: MeasureTarget, id: string): Promise<string> | null => {
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
    const wanted = new Map<string, Promise<string> | null>()
    for (const measure of detail.measures) {
      if (measure.entity_id === null) continue
      const key = elementKey(measure.target, measure.entity_id)
      if (!wanted.has(key)) wanted.set(key, fetchName(measure.target, measure.entity_id))
    }
    void Promise.all(
      [...wanted.entries()].map(([key, job]) =>
        job === null
          ? Promise.resolve(null)
          : job.then(
              (name) => [key, name] as const,
              () => null,
            ),
      ),
    ).then((rows) => {
      if (cancelled) return
      const next: Record<string, string> = {}
      for (const row of rows) if (row !== null) next[row[0]] = row[1]
      setElementNames(next)
    })
    return () => {
      cancelled = true
    }
  }, [api, detail])

  const reload = useCallback(() => {
    setLoading(true)
    setError(null)
    setNotFound(false)
    setNonce((value) => value + 1)
  }, [])

  return {
    detail,
    agents,
    members,
    predecessor,
    successor,
    cases,
    testCaseTitles,
    elementNames,
    loading,
    notFound,
    error,
    reload,
  }
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
      {[0, 1, 2].map((index) => (
        <Skeleton key={index} className="h-28 w-full rounded-xl" data-testid="review-detail-skeleton" />
      ))}
    </div>
  )
}

function Section({
  title,
  count,
  testId,
  children,
}: {
  title: string
  count?: number
  testId: string
  children: ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col gap-3" data-testid={testId}>
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        {title}
        {count !== undefined ? (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium tabular-nums">
            {count}
          </span>
        ) : null}
      </h2>
      {children}
    </section>
  )
}

/** Freitext aus dem Client: immer Textknoten, nie Markdown oder HTML (E5-Delta §0.5). */
function FreeText({ text, className }: { text: string; className?: string }) {
  return <p className={cn('text-sm break-words whitespace-pre-wrap', className)}>{text}</p>
}

/** Markierung der Nachkontrolle an einer Aenderung (Neuschnitt §1). */
function FollowUpMark({ measure, session }: { measure: MeasureRead; session: SessionRead }) {
  const { t } = useTranslation('sessions')
  // Faellig nach lokalem Kalendertag ueber `followUp.ts` (PM 2026-10-14: an
  // der einzelnen Aenderung gibt es keinen Serverwert).
  const status = followUpStatus(measure, session)
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

/**
 * Review-Ergebnis am Agenten: `/w/:ws/agents/:agentId/reviews/:sessionId`
 * (Neuschnitt §2, Weiche N4 a). Nur lesend; das Aenderung-Sheet
 * (`?change=<id>`) rendert E5d.
 */
export function ReviewDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  // Frischer Zustand je Review-Ergebnis (Vorgaenger/Nachfolger-Links).
  return <ReviewDetailView key={sessionId} />
}

function ReviewDetailView() {
  const { t } = useTranslation(['sessions', 'feedback', 'common'])
  const { agentId, sessionId } = useParams<{ agentId: string; sessionId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const isEditor = role === 'editor' || role === 'admin'
  const data = useReviewDetail(sessionId, isEditor)

  const session = data.detail?.session ?? null

  // Alte Lesezeichen: passt die Agent-ID nicht, `replace` auf die richtige URL.
  useEffect(() => {
    if (session === null || agentId === undefined || session.agent_id === agentId) return
    navigate(
      {
        pathname: wsPath(`/agents/${session.agent_id}/reviews/${session.id}`),
        search: location.search,
      },
      { replace: true, state: location.state as unknown },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, agentId])

  const agentById = useMemo(
    () => new Map((data.agents ?? []).map((agent) => [agent.id, agent.name])),
    [data.agents],
  )
  const memberById = useMemo(
    () => new Map((data.members ?? []).map((member) => [member.user_id, member.email ?? null])),
    [data.members],
  )

  const evolutionHref = wsPath(`/agents/${session?.agent_id ?? agentId ?? ''}?tab=evolution`)
  const from = safeInternalPath((location.state as { from?: string } | null)?.from ?? null)
  const backHref = from ?? evolutionHref

  // Role noch unbekannt: nichts zeigen, damit fuer viewer nichts aufblitzt.
  if (role === null) {
    return (
      <Container>
        <DetailSkeleton />
      </Container>
    )
  }

  if (!isEditor || data.notFound || sessionId === undefined) {
    return (
      <Container>
        <EmptyState
          icon={MessagesSquare}
          title={t('sessions:detail.notFound')}
          action={
            <Button asChild variant="outline">
              <Link to={evolutionHref}>{t('sessions:detail.toList')}</Link>
            </Button>
          }
        />
      </Container>
    )
  }

  if (data.loading && session === null) {
    return (
      <Container>
        <DetailSkeleton />
      </Container>
    )
  }

  if (session === null || data.detail === null) {
    return (
      <Container>
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert message={data.error ?? ''} title={t('sessions:detail.loadError')} />
          <Button type="button" variant="outline" onClick={data.reload}>
            {t('common:actions.retry')}
          </Button>
        </div>
      </Container>
    )
  }

  const measures = data.detail.measures
  const agentName =
    agentById.get(session.agent_id) ??
    (data.agents === null ? '' : t('sessions:detail.participant.deletedAgent'))

  const participantName = (kind: SessionParticipantKind, id: string): string => {
    if (kind === 'builder') return t('sessions:detail.participant.builder')
    if (kind === 'agent') {
      return agentById.get(id) ?? t('sessions:detail.participant.deletedAgent')
    }
    return memberById.get(id) ?? t('sessions:detail.participant.formerMember')
  }

  const trigger = t(`sessions:trigger.${session.trigger}`)
  const fromClient = session.submitted_by_kind !== 'human'
  const subtitle = t(fromClient ? 'sessions:detail.subtitleClient' : 'sessions:detail.subtitle', {
    agent: agentName,
    trigger,
  })
  const submittedAt = formatDateTime(session.created_at, { dateStyle: 'short', timeStyle: 'short' })
  const origin = fromClient
    ? t('sessions:detail.fromClient', {
        who:
          agentById.get(session.submitted_by) ?? t('sessions:detail.participant.builder'),
        datetime: submittedAt,
      })
    : t('sessions:detail.byHuman', {
        name: memberById.get(session.submitted_by) ?? t('sessions:detail.participant.formerMember'),
        datetime: submittedAt,
      })

  const reviewPath = (id: string) => wsPath(`/agents/${session.agent_id}/reviews/${id}`)
  const successor = data.successor
  const replaced = successor !== undefined && successor !== null

  // Kopiertext nur mit IDs und Namen, nie mit Inhalten (D-Delta S5).
  const correctionPrompt = t('sessions:copy.correction', {
    sessionId: session.id,
    agent: agentName,
    agentId: session.agent_id,
  })

  const elementLabel = (measure: MeasureRead): string => {
    const kind = t(`feedback:cases.target.${measure.target}`)
    const name =
      measure.entity_id !== null
        ? data.elementNames[elementKey(measure.target, measure.entity_id)]
        : undefined
    return name !== undefined ? `${kind} „${name}“` : kind
  }

  const onCopyId = () => {
    void copyToClipboard(session.id)
      .then(() => notify.success(t('sessions:detail.idCopied')))
      .catch((cause: unknown) => notify.error(messageOf(cause)))
  }

  const [refBefore, refAfter] = t('sessions:detail.standardRef', { ref: '\u0000' }).split('\u0000')

  const changeHref = (measureId: string) => {
    const params = new URLSearchParams(location.search)
    params.set('change', measureId)
    return `${location.pathname}?${params.toString()}`
  }

  const caseStatusWord = (status: CaseStatus) =>
    status === 'addressed'
      ? t('feedback:cases.status.addressedShort')
      : t(`feedback:cases.status.${status}`)

  return (
    <Container>
      <div className="flex flex-col gap-8">
        <DetailHeader
          icon={MessagesSquare}
          iconTone="catalog"
          title={t('sessions:detail.title', { date: formatDay(session.created_at) })}
          backHref={backHref}
          backLabel={t('sessions:detail.back', { agent: agentName })}
          description={subtitle}
          badges={
            <>
              <MetaPill icon={CalendarClock}>
                <time dateTime={session.follow_up_at}>
                  {t('sessions:detail.followUpOn', { date: formatDay(session.follow_up_at) })}
                </time>
              </MetaPill>
              {session.supersedes_id !== null ? (
                <Link
                  to={reviewPath(session.supersedes_id)}
                  className="text-xs font-medium break-words text-brand hover:underline"
                  data-testid="review-corrects"
                >
                  {data.predecessor !== null
                    ? t('sessions:supersede.corrects', {
                        date: formatDay(data.predecessor.created_at),
                      })
                    : t('sessions:supersede.corrects', { date: '…' })}
                </Link>
              ) : null}
            </>
          }
          actions={
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="size-11 md:size-9"
                  aria-label={t('sessions:detail.actions')}
                  data-testid="review-overflow"
                >
                  <MoreHorizontal aria-hidden="true" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={onCopyId}>
                  <Copy aria-hidden="true" />
                  {t('sessions:detail.copyId')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          }
        />

        <p
          className="-mt-5 flex min-w-0 items-start gap-1.5 text-sm text-muted-foreground"
          data-testid="review-origin"
        >
          {fromClient ? (
            <MonitorSmartphone className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          ) : null}
          <span className="min-w-0 break-words">{origin}</span>
        </p>

        {replaced ? (
          <div data-testid="review-replaced">
            <AttentionBanner
              variant="brand"
              icon={Replace}
              // 390 px: Text bekommt die Zeile, der Knopf bricht darunter um.
              className="[&>div:last-child]:w-full sm:[&>div:last-child]:w-auto [&>div:nth-child(2)]:basis-48"
              title={t('sessions:supersede.replacedBy', { date: formatDay(successor.created_at) })}
              description={t('sessions:supersede.measuresStay')}
              actions={
                <Button asChild variant="outline" className="min-h-11 w-full sm:w-auto md:min-h-9">
                  <Link to={reviewPath(successor.id)}>{t('sessions:supersede.toNew')}</Link>
                </Button>
              }
            />
          </div>
        ) : null}

        <Section title={t('sessions:detail.participants')} testId="review-participants">
          <ul className="flex flex-col gap-1 text-sm md:flex-row md:flex-wrap md:gap-x-4">
            {session.participants.map((participant, index) => (
              <li key={`${participant.kind}:${participant.id}:${index}`} className="min-w-0 break-words">
                <span className="font-medium">{participantName(participant.kind, participant.id)}</span>{' '}
                <span className="text-muted-foreground">({participant.role})</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title={t('sessions:detail.summary')} testId="review-summary">
          <FreeText text={session.summary} />
        </Section>

        <Section title={t('sessions:detail.decisions')} testId="review-decisions">
          {session.decisions.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('sessions:detail.decisionsEmpty')}</p>
          ) : (
            <ul className="flex list-disc flex-col gap-2 pl-5">
              {session.decisions.map((decision, index) => {
                const ref = decision.standard_ref
                const url = ref !== null ? safeHttpUrl(ref) : null
                return (
                  <li key={index} className="min-w-0">
                    <FreeText text={decision.text} />
                    {ref !== null ? (
                      <p className="text-xs break-words text-muted-foreground" data-testid="decision-ref">
                        {refBefore}
                        {url !== null ? (
                          <Link
                            to={url}
                            reloadDocument
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-medium wrap-anywhere text-brand hover:underline"
                          >
                            {ref}
                            <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                          </Link>
                        ) : (
                          <code className="font-mono wrap-anywhere">{ref}</code>
                        )}
                        {refAfter}
                      </p>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          )}
        </Section>

        <Section title={t('sessions:detail.dissent')} testId="review-dissent">
          {session.dissent.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('sessions:detail.dissentEmpty')}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {session.dissent.map((entry, index) => (
                <li key={index} className="min-w-0 text-sm break-words whitespace-pre-wrap">
                  <span className="font-medium">
                    {participantName(entry.participant_kind, entry.participant_id)}:
                  </span>{' '}
                  {entry.text}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section
          title={t('sessions:detail.cases')}
          count={data.cases?.length}
          testId="review-cases"
        >
          {data.cases === null ? (
            <Skeleton className="h-10 w-full" />
          ) : data.cases.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('sessions:detail.casesEmpty')}</p>
          ) : (
            <ul className="flex flex-col divide-y rounded-xl border">
              {data.cases.map((item) => (
                <li key={item.id} className="min-w-0" data-testid="review-case">
                  <Link
                    to={wsPath(`/feedback/cases/${item.id}`)}
                    className="flex min-h-11 min-w-0 flex-col gap-1 px-4 py-2 hover:bg-muted/40 sm:flex-row sm:items-center sm:gap-3"
                  >
                    <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                      <CaseStatusDot status={item.status} />
                      {caseStatusWord(item.status)}
                    </span>
                    <span className="min-w-0 truncate text-sm">
                      {t('feedback:cases.row.expected', { text: item.expected_behavior })}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title={t('sessions:detail.measures')} count={measures.length} testId="review-measures">
          {measures.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('sessions:detail.measuresEmpty')}</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {measures.map((measure, index) => {
                const label = t('sessions:detail.measureLabel', {
                  n: index + 1,
                  element: elementLabel(measure),
                })
                const title = data.testCaseTitles[measure.test_case_id]
                return (
                  <li
                    key={measure.id}
                    className="flex min-w-0 flex-col gap-3 rounded-xl border bg-card p-4 shadow-card sm:flex-row sm:items-start sm:justify-between"
                    data-testid="review-measure"
                  >
                    <div className="flex min-w-0 flex-col gap-1.5">
                      <h3 className="text-sm font-semibold break-words">{label}</h3>
                      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="text-xs font-medium" data-testid="measure-state">
                          {t(`sessions:measure.state.${measure.state}`)}
                        </span>
                        <FollowUpMark measure={measure} session={session} />
                      </p>
                      <FreeText text={measure.change_summary} className="line-clamp-2" />
                      <p className="text-xs break-words text-muted-foreground">
                        {title !== undefined ? `${t('sessions:detail.testCase', { title })} · ` : ''}
                        {t('sessions:detail.measureCases', { count: measure.case_ids.length })}
                      </p>
                    </div>
                    <Button
                      asChild
                      variant="outline"
                      className="min-h-11 w-full shrink-0 sm:min-h-9 sm:w-auto"
                    >
                      <Link
                        to={changeHref(measure.id)}
                        aria-label={t('sessions:detail.openMeasureAria', { label })}
                      >
                        {t('sessions:detail.openMeasure')}
                      </Link>
                    </Button>
                  </li>
                )
              })}
            </ol>
          )}
        </Section>

        {/* Korrektur (QE9 a): Kopierblock an den Builder, zugeklappt. Bei
            einem ersetzten Ergebnis entfaellt er; solange der Nachfolger
            nicht ermittelt ist, ebenso. */}
        {successor === null ? (
          <details className="group min-w-0 rounded-xl border p-4" data-testid="review-correction">
            <summary className="flex min-h-11 cursor-pointer items-center md:min-h-9">
              <h2 className="text-lg font-semibold">{t('sessions:copy.correctionTitle')}</h2>
            </summary>
            <div className="mt-3 flex min-w-0 flex-col gap-3">
              <p className="text-sm text-muted-foreground">{t('sessions:copy.correctionIntro')}</p>
              <BuilderPromptCopy prompt={correctionPrompt} testId="review-correction-copy" />
            </div>
          </details>
        ) : null}
      </div>
    </Container>
  )
}
