import { Bot, Repeat, User, Wrench, type LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import type { Agent, CaseCounts, CaseRead, CaseStatus, CaseTarget } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ReportCaseDialog } from '@/components/cases/ReportCaseForm'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { MetaPill } from '@/components/data/MetaPill'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { StatusChipOption } from '@/lib/listFilter'

// Chip-Werte (Filter-Standard §3.2). „Offen“ ist ein Sammel-Chip aus `open`
// und `reopened`; „In Arbeit“ und „Bestätigt“ gibt es in Phase D nicht.
type StatusChip = 'all' | 'open' | 'triaged' | 'addressed' | 'dismissed'
const STATUS_CHIPS: readonly StatusChip[] = ['all', 'open', 'triaged', 'addressed', 'dismissed']
const DEFAULT_STATUS: StatusChip = 'open'

const CHIP_STATUSES: Record<Exclude<StatusChip, 'all'>, readonly CaseStatus[]> = {
  open: ['open', 'reopened'],
  triaged: ['triaged'],
  addressed: ['addressed'],
  dismissed: ['dismissed'],
}

const CHIP_TOKEN: Record<Exclude<StatusChip, 'all'>, string> = {
  open: 'draft',
  triaged: 'review',
  addressed: 'active',
  dismissed: 'inactive',
}

// Punkt-Token je Fall-Status (Delta-Spec §0). `in_progress`/`verified` gibt es
// in Phase D nicht; kommen sie doch, steht nur das Wort da.
const STATUS_TOKEN: Partial<Record<CaseStatus, string>> = {
  open: 'draft',
  reopened: 'draft',
  triaged: 'review',
  addressed: 'active',
  dismissed: 'inactive',
}

const TARGETS: readonly CaseTarget[] = [
  'persona',
  'playbook',
  'resource',
  'external_tool',
  'system_prompt_template',
  'tool_policy',
  'memory',
  'model_limit',
]

function isStatusChip(value: string | null): value is StatusChip {
  return value !== null && (STATUS_CHIPS as readonly string[]).includes(value)
}

function isTarget(value: string | null): value is CaseTarget {
  return value !== null && (TARGETS as readonly string[]).includes(value)
}

function chipCount(counts: CaseCounts, chip: StatusChip): number {
  if (chip === 'all') return Object.values(counts).reduce((sum, value) => sum + value, 0)
  return CHIP_STATUSES[chip].reduce((sum, status) => sum + (counts[status] ?? 0), 0)
}

interface CaseQuery {
  status: StatusChip
  agent: string
  target: CaseTarget | ''
}

interface CaseListData {
  items: CaseRead[]
  nextCursor: string | null
  counts: CaseCounts | null
  countsError: boolean
  agents: Agent[]
  loading: boolean
  loadingMore: boolean
  error: string | null
  loadMore: () => void
  reload: () => void
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

/**
 * Eine Seite `GET /cases` (Cursor aus `X-Next-Cursor`) plus Chip-Zaehler aus
 * `GET /cases/counts`. Gefiltert wird nur serverseitig, damit Liste und
 * Zaehler zusammenpassen (Delta-Spec S7). Eine Generation verwirft spaete
 * Antworten nach einem Filterwechsel.
 */
function useCaseList(query: CaseQuery): CaseListData {
  const api = useApi()
  const [items, setItems] = useState<CaseRead[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [counts, setCounts] = useState<CaseCounts | null>(null)
  const [countsError, setCountsError] = useState(false)
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const generation = useRef(0)

  const filters = useMemo(
    () => ({
      agent_id: query.agent === '' ? undefined : query.agent,
      status: query.status === 'all' ? undefined : CHIP_STATUSES[query.status],
      target: query.target === '' ? undefined : query.target,
    }),
    [query.agent, query.status, query.target],
  )

  useEffect(() => {
    const current = ++generation.current
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .listCases(filters)
      .then((page) => {
        if (cancelled) return
        setItems(page.items)
        setNextCursor(page.next_cursor)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(messageOf(cause))
      })
      .finally(() => {
        if (!cancelled && current === generation.current) setLoading(false)
      })
    api
      .countCases(filters.agent_id)
      .then((result) => {
        if (cancelled) return
        setCounts(result)
        setCountsError(false)
      })
      .catch(() => {
        if (cancelled) return
        setCounts(null)
        setCountsError(true)
      })
    return () => {
      cancelled = true
    }
  }, [api, filters, nonce])

  // Agenten fuer Titel und Facette (`GET /agents`, ab viewer). Scheitert der
  // Abruf, bleibt die Liste nutzbar: Titel fallen auf „Unbekannter Agent“.
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

  const loadMore = useCallback(() => {
    if (nextCursor === null) return
    const current = generation.current
    setLoadingMore(true)
    api
      .listCases(filters, { cursor: nextCursor })
      .then((page) => {
        if (current !== generation.current) return
        setItems((previous) => [...previous, ...page.items])
        setNextCursor(page.next_cursor)
      })
      .catch((cause: unknown) => {
        if (current === generation.current) setError(messageOf(cause))
      })
      .finally(() => setLoadingMore(false))
  }, [api, filters, nextCursor])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return {
    items,
    nextCursor,
    counts,
    countsError,
    agents,
    loading,
    loadingMore,
    error,
    loadMore,
    reload,
  }
}

function StatusLabel({ status }: { status: CaseStatus }) {
  const { t } = useTranslation('feedback')
  const token = STATUS_TOKEN[status]
  // `CaseRead` traegt weder Element noch Version — die Liste zeigt bei
  // „Umgesetzt“ nur das Wort, das Ziel steht im Fall-Detail (D6c).
  const label = status === 'addressed' ? t('cases.status.addressedShort') : t(`cases.status.${status}`)
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground">
      {token ? (
        <span
          className={
            status === 'addressed'
              ? 'inline-block size-2 rounded-full border-2'
              : 'inline-block size-2 rounded-full'
          }
          style={
            status === 'addressed'
              ? { borderColor: `var(--status-${token})` }
              : { backgroundColor: `var(--status-${token})` }
          }
          aria-hidden="true"
        />
      ) : null}
      {label}
    </span>
  )
}

function CaseRow({ item, agents }: { item: CaseRead; agents: Agent[] }) {
  const { t } = useTranslation(['feedback', 'learning'])
  const wsPath = useWorkspacePath()
  const agentName = (id: string | null) => agents.find((agent) => agent.id === id)?.name
  const title = agentName(item.agent_id) ?? t('learning:approval.unknownAgent')

  let SourceIcon: LucideIcon = User
  let source = t('feedback:itemDetail.history.actorHuman')
  if (item.reporter_kind === 'pattern') {
    SourceIcon = Repeat
    source = t('feedback:cases.row.fromPattern')
  } else if (item.reporter_kind === 'builder') {
    SourceIcon = Wrench
    source = t('feedback:cases.row.builder')
  } else if (item.reporter_kind === 'agent') {
    SourceIcon = Bot
    source = agentName(item.reporter_agent_id) ?? t('feedback:panel.agent')
  }
  const selfReported = item.reporter_agent_id !== null && item.reporter_agent_id === item.agent_id

  return (
    <EntityCard
      icon={Bot}
      iconTone="catalog"
      title={title}
      href={wsPath(`/feedback/cases/${item.id}`)}
      status={<StatusLabel status={item.status} />}
      meta={
        <>
          {/* „Erwartet“ zuerst (der umsetzbare Teil), darunter die Lage.
              Unter `md` ist „Erwartet“ zweizeilig und die Lage entfaellt
              (Delta-Spec S7, 390 px). `basis-full` stellt beide Zeilen ueber
              die Meta-Pillen. */}
          <p className="line-clamp-2 basis-full text-sm wrap-anywhere text-foreground md:line-clamp-1">
            {t('feedback:cases.row.expected', { text: item.expected_behavior })}
          </p>
          <p className="hidden basis-full truncate text-sm text-muted-foreground md:block">
            {t('feedback:cases.row.situation', { text: item.situation })}
          </p>
          <MetaPill icon={SourceIcon}>
            {source}
            {selfReported ? ` ${t('feedback:cases.row.selfReported')}` : ''} ·{' '}
            {new Date(item.created_at).toLocaleDateString()}
          </MetaPill>
          {item.signal !== null ? <MetaPill>{t(`feedback:signal.${item.signal}`)}</MetaPill> : null}
          {item.severity === 'high' ? (
            <MetaPill tone="destructive">{t('feedback:cases.report.severity.high')}</MetaPill>
          ) : null}
        </>
      }
    />
  )
}

function CaseSkeletons() {
  const { t } = useTranslation('data')
  return (
    <div className="flex flex-col gap-3" aria-live="polite" aria-busy="true">
      <span className="sr-only">{t('loading')}</span>
      {[0, 1, 2].map((index) => (
        <Skeleton key={index} className="h-28 w-full rounded-xl" data-testid="case-skeleton" />
      ))}
    </div>
  )
}

interface CaseListProps {
  /** viewer: „Meine Fälle“ — nur eigene Faelle, ohne „Zugeordnet zu“. */
  viewer: boolean
}

/**
 * Fall-Liste im Feedback-Hub (Delta-Spec S7, Filter-Standard §3.2): Status-
 * Chips mit Zaehlern, Facetten Agent und „Zugeordnet zu“ (nur editor) ueber
 * die gemeinsame `ListFilterBar`, Zeilen als `EntityCard` mit Link auf das
 * Fall-Detail. Filter stehen in der URL (`status`, `agent`, `target`, per
 * `replace`); der Standard „Offen“ steht nicht darin.
 */
export function CaseList({ viewer }: CaseListProps) {
  const { t } = useTranslation(['feedback', 'data', 'common'])
  const [params, setParams] = useSearchParams()

  const rawStatus = params.get('status')
  const status: StatusChip = isStatusChip(rawStatus) ? rawStatus : DEFAULT_STATUS
  const agent = params.get('agent') ?? ''
  const rawTarget = params.get('target')
  const target: CaseTarget | '' = !viewer && isTarget(rawTarget) ? rawTarget : ''
  const query = useMemo(() => ({ status, agent, target }), [status, agent, target])

  const data = useCaseList(query)

  const setParam = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value === '' || (key === 'status' && value === DEFAULT_STATUS)) next.delete(key)
        else next.set(key, value)
        return next
      },
      { replace: true },
    )

  const reset = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('status')
        next.delete('agent')
        next.delete('target')
        return next
      },
      { replace: true },
    )

  const active = status !== DEFAULT_STATUS || agent !== '' || target !== ''

  // `/cases/counts` kennt `target` nicht: solange es gesetzt ist, zeigen die
  // Chips keine Zahl (Filter-Standard §2.3 „die Zahl zeigt, was ein Klick ergaebe“).
  const counts = target === '' ? data.counts : null
  const statusOptions: StatusChipOption[] = STATUS_CHIPS.map((chip) => ({
    value: chip,
    label:
      chip === 'all'
        ? t('data:filter.all')
        : chip === 'addressed'
          ? t('feedback:cases.status.addressedShort')
          : t(`feedback:cases.status.${chip}`),
    count: counts === null ? null : chipCount(counts, chip),
    token: chip === 'all' ? undefined : CHIP_TOKEN[chip],
    keepWhenZero: chip === 'all' || chip === DEFAULT_STATUS,
  }))

  const agentOptions = [...data.agents]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((entry) => ({ id: entry.id, name: entry.name }))

  const targetFacet = viewer
    ? []
    : [
        {
          key: 'target',
          label: t('feedback:cases.filter.target'),
          allLabel: t('feedback:cases.filter.allTargets'),
          options: TARGETS.map((value) => ({ value, label: t(`feedback:cases.target.${value}`) })),
          value: target,
          onChange: (value: string) => setParam('target', value),
        },
      ]

  const total = data.counts === null ? null : chipCount(data.counts, 'all')
  // Keine Daten ueberhaupt: die Seite zeigt ihren Leerzustand, die Leiste
  // entfaellt (Filter-Standard §2.3).
  const nothingAtAll = !active && total === 0 && !data.loading && data.items.length === 0

  let empty = null
  if (!data.loading && data.error === null && data.items.length === 0) {
    if (active) {
      empty = (
        <EmptyState
          title={t('data:filter.emptyFilteredTitle')}
          description={t('feedback:cases.list.emptyFiltered')}
          action={
            <Button type="button" variant="outline" onClick={reset}>
              {t('data:filter.reset')}
            </Button>
          }
        />
      )
    } else if (viewer && (total === null || total === 0)) {
      empty = (
        <EmptyState
          title={t('feedback:cases.list.emptyViewerTitle')}
          description={t('feedback:cases.list.emptyViewerDescription')}
          action={<ReportCaseDialog variant="brand" />}
        />
      )
    } else {
      empty = (
        <EmptyState
          title={t('feedback:cases.list.emptyOpenTitle')}
          description={t('feedback:cases.list.emptyOpenDescription')}
        />
      )
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {nothingAtAll ? null : (
        <ListFilterBar
          statusOptions={statusOptions}
          status={status}
          onStatusChange={(value) => setParam('status', value)}
          agents={agentOptions}
          agent={agent}
          onAgentChange={(value) => setParam('agent', value)}
          facets={targetFacet}
          active={active}
          onReset={reset}
          countsUnavailable={data.countsError}
          resultCount={counts === null ? null : chipCount(counts, status)}
          idPrefix="cases-filter"
        />
      )}

      {data.loading ? (
        <CaseSkeletons />
      ) : data.error !== null && data.items.length === 0 ? (
        <div className="flex flex-col items-start gap-3">
          <ErrorAlert title={t('feedback:cases.list.loadError')} message={data.error} />
          <Button type="button" variant="outline" onClick={data.reload}>
            {t('common:actions.retry')}
          </Button>
        </div>
      ) : empty !== null ? (
        empty
      ) : (
        <div className="flex flex-col gap-3">
          <ul className="flex flex-col gap-3">
            {data.items.map((item) => (
              <li key={item.id}>
                <CaseRow item={item} agents={data.agents} />
              </li>
            ))}
          </ul>
          {data.error !== null ? (
            <ErrorAlert title={t('feedback:cases.list.loadError')} message={data.error} />
          ) : null}
          {data.nextCursor !== null ? (
            <Button
              type="button"
              variant="outline"
              className="min-h-11 self-center"
              onClick={data.loadMore}
              disabled={data.loadingMore}
              aria-busy={data.loadingMore}
            >
              {t('feedback:cases.list.loadMore')}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  )
}
