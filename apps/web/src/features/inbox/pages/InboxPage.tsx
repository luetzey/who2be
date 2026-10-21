import {
  ArrowRight,
  Brain,
  CalendarClock,
  CircleCheck,
  ClipboardCheck,
  MessageSquareWarning,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import type { Api } from '@/api/client'
import type { Agent, InboxCounts, MemoryFilter, SessionListItem, VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { LoadingState } from '@/components/data/LoadingState'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { versionDiffSearch } from '@/components/version/versionDeepLink'
import { useInboxCounts } from '@/hooks/useInboxCounts'
import type { StatusChipOption } from '@/lib/listFilter'
import { cn } from '@/lib/utils'

import { daysSince, formatDay } from '../../evolution/lib/followUp'

import {
  INBOX_ROWS_PER_KIND,
  InboxLookSection,
  type InboxLookRow,
  type InboxRow,
  InboxSection,
} from '../components/InboxSection'

// Arten in der Reihenfolge aus Spec §2.2: erst was einen Termin hat, dann
// was wirksam werden will, dann was neu hereinkommt. `versions` ist nur fuer
// admin eine Aufgabe; fuer editor steht sie unter „Zum Anschauen“.
const KINDS = ['followUps', 'memory', 'versions', 'cases'] as const
type Kind = (typeof KINDS)[number]
type KindFilter = Kind | 'all'

function isKind(value: string | null): value is Kind {
  return value !== null && (KINDS as readonly string[]).includes(value)
}

type VersionType = 'persona' | 'playbook' | 'resource' | 'systemPrompt'
const VERSION_TYPES: readonly VersionType[] = ['persona', 'playbook', 'resource', 'systemPrompt']
const VERSION_PATH: Record<VersionType, string> = {
  persona: '/personas',
  playbook: '/playbooks',
  resource: '/resources',
  systemPrompt: '/system-prompts',
}

interface VersionItem {
  type: VersionType
  id: string
  name: string
  version: number
}

interface Listed {
  id: string
  name: string
  current_version: number
  current_status?: VersionStatus
}

/** Alle Versionen „zur Freigabe“ aus den vier Listen (ohne Paging der Server). */
async function loadReviewVersions(api: Api): Promise<VersionItem[]> {
  const loaders: Record<VersionType, () => Promise<Listed[]>> = {
    persona: () => api.listPersonas(),
    playbook: () => api.listPlaybooks(),
    resource: () => api.listResources(),
    systemPrompt: () => api.listSystemPromptTemplates(),
  }
  const perType = await Promise.all(
    VERSION_TYPES.map((type) =>
      loaders[type]().then((items) =>
        items
          .filter((item) => item.current_status === 'review')
          .map((item) => ({ type, id: item.id, name: item.name, version: item.current_version })),
      ),
    ),
  )
  return perType.flat()
}

interface SectionState<T> {
  api: Api
  key: string
  items: T[] | null
  failed: boolean
}

/**
 * Zeilen eines Abschnitts. Geladen wird nur, wenn die Art etwas zu zeigen hat
 * (`count > 0`), und neu, sobald sich ihre Zahl aendert — die Zahl kommt aus
 * der EINEN `useInboxCounts`-Instanz der Seite und folgt damit Weiche N5 a
 * (Laden, Workspace-Wechsel, Tab-Rueckkehr, eigene Aktionen; kein Polling).
 * `key` muss alles enthalten, wovon `load` abhaengt (ausser `api`).
 */
function useSectionRows<T>(
  api: Api,
  enabled: boolean,
  key: string,
  load: (api: Api) => Promise<T[]>,
): { items: T[] | null; loading: boolean; failed: boolean; retry: () => void } {
  const [state, setState] = useState<SectionState<T> | null>(null)
  const [nonce, setNonce] = useState(0)
  const fullKey = `${key}#${nonce}`
  // Die Ladefunktion entsteht je Render neu; massgeblich ist der Schluessel.
  const loadRef = useRef(load)
  useEffect(() => {
    loadRef.current = load
  })

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    loadRef
      .current(api)
      .then((items) => {
        if (!cancelled) setState({ api, key: fullKey, items, failed: false })
      })
      .catch(() => {
        if (!cancelled) setState({ api, key: fullKey, items: null, failed: true })
      })
    return () => {
      cancelled = true
    }
  }, [api, enabled, fullKey])

  // Zeilen aus einem anderen Workspace gelten nie.
  const sameApi = state !== null && state.api === api
  const fresh = sameApi && state.key === fullKey
  // Beim Nachladen nach einer Zahl-Aenderung bleiben die alten Zeilen stehen
  // (kein Flackern); sie gehoeren zum selben Abschnitt.
  const items = sameApi ? state.items : null
  return {
    items: enabled ? items : null,
    loading: enabled && !fresh,
    failed: enabled && fresh && state.failed,
    retry: () => setNonce((value) => value + 1),
  }
}

interface FollowUpPageState {
  api: Api
  key: string
  items: SessionListItem[] | null
  cursor: string | null
  failed: boolean
}

/**
 * Nachkontroll-Zeilen (Neuschnitt §5): Reviews mit faelliger Aenderung aus
 * `listSessions({ due: true })`, je Seite hoechstens fuenf. Ob etwas faellig
 * ist, entscheidet der Server (QE2 a, Leitplanke „eine Quelle je Ansicht“) —
 * das Web filtert nicht nach. „Weitere laden“ haengt die naechste Seite an;
 * solange sie laedt, loest ein zweiter Klick keinen zweiten Request aus.
 */
function useFollowUpRows(api: Api, enabled: boolean, key: string, agentId: string | undefined) {
  const [state, setState] = useState<FollowUpPageState | null>(null)
  const [nonce, setNonce] = useState(0)
  const [more, setMore] = useState<{ key: string; loading: boolean; failed: boolean } | null>(null)
  const moreInFlight = useRef(false)
  const fullKey = `${key}#${nonce}`

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    api
      .listSessions({ due: true, ...(agentId ? { agent_id: agentId } : {}) }, { limit: INBOX_ROWS_PER_KIND })
      .then((page) => {
        if (!cancelled)
          setState({ api, key: fullKey, items: page.items, cursor: page.next_cursor, failed: false })
      })
      .catch(() => {
        if (!cancelled) setState({ api, key: fullKey, items: null, cursor: null, failed: true })
      })
    return () => {
      cancelled = true
    }
  }, [api, enabled, fullKey, agentId])

  const sameApi = state !== null && state.api === api
  const fresh = sameApi && state.key === fullKey
  const cursor = fresh ? state.cursor : null

  const loadMore = () => {
    if (moreInFlight.current || cursor === null) return
    moreInFlight.current = true
    const forKey = fullKey
    setMore({ key: forKey, loading: true, failed: false })
    api
      .listSessions(
        { due: true, ...(agentId ? { agent_id: agentId } : {}) },
        { cursor, limit: INBOX_ROWS_PER_KIND },
      )
      .then((page) => {
        setState((prev) => {
          if (prev === null || prev.api !== api || prev.key !== forKey || prev.items === null) return prev
          const known = new Set(prev.items.map((item) => item.id))
          return {
            ...prev,
            items: [...prev.items, ...page.items.filter((item) => !known.has(item.id))],
            cursor: page.next_cursor,
          }
        })
        setMore({ key: forKey, loading: false, failed: false })
      })
      .catch(() => setMore({ key: forKey, loading: false, failed: true }))
      .finally(() => {
        moreInFlight.current = false
      })
  }

  const moreFresh = more !== null && more.key === fullKey
  return {
    items: enabled && sameApi ? state.items : null,
    loading: enabled && !fresh,
    failed: enabled && fresh && state.failed,
    retry: () => setNonce((value) => value + 1),
    hasMore: enabled && cursor !== null,
    loadingMore: enabled && moreFresh && more.loading,
    moreFailed: enabled && moreFresh && more.failed,
    loadMore,
  }
}

/** „vor 3 Stunden“ — kurz, in der Sprache der Oberflaeche. */
function useAge(): (iso: string) => string {
  const { i18n } = useTranslation()
  return useCallback(
    (iso: string) => {
      const format = new Intl.RelativeTimeFormat(i18n.language, { numeric: 'auto' })
      const seconds = (new Date(iso).getTime() - Date.now()) / 1000
      const abs = Math.abs(seconds)
      if (abs < 3600) return format.format(Math.round(seconds / 60), 'minute')
      if (abs < 86400) return format.format(Math.round(seconds / 3600), 'hour')
      return format.format(Math.round(seconds / 86400), 'day')
    },
    [i18n.language],
  )
}

function countFor(counts: InboxCounts, kind: Kind, isAdmin: boolean): number | null {
  switch (kind) {
    case 'followUps':
      return counts.follow_ups_due
    case 'memory':
      return counts.memory_approval
    case 'versions':
      // Aufgabe nur fuer admin (nur admin darf `review -> active`, §2.2).
      if (!isAdmin || counts.versions_review === null) return null
      return counts.versions_review + (counts.system_prompts_review ?? 0)
    case 'cases':
      return counts.cases_open
  }
}

/**
 * Seite „Zu erledigen“ (Navigation & Transparenz W1-b, Spec §2.4): alle
 * offenen Aufgaben nach Art gruppiert, je Art hoechstens fuenf Zeilen, jede
 * Zeile springt mit genau einer Aktion zur Fachseite (N7 a — erledigt wird
 * dort, mit Kontext). Keine Suche (N6 a). Filter `?kind=` und `?agent=`;
 * `?agent=` ist zugleich der Einstieg vom Agenten aus.
 */
export function InboxPage() {
  const { t } = useTranslation(['inbox', 'data'])
  const api = useApi()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const age = useAge()
  const [params, setParams] = useSearchParams()

  const canTriage = role !== null && role !== 'viewer'
  const isAdmin = role === 'admin'
  const rawKind = params.get('kind')
  const kind: KindFilter = isKind(rawKind) ? rawKind : 'all'
  const agent = canTriage ? (params.get('agent') ?? '') : ''
  const agentId = agent === '' ? undefined : agent

  // EINE Instanz je Seite (Review W1-a): jede weitere Instanz loest je
  // Mutation einen eigenen GET aus.
  const { counts, failed: countsFailed, reload: reloadCounts } = useInboxCounts(agentId)

  const [agents, setAgents] = useState<{ api: Api; list: Agent[] } | null>(null)
  useEffect(() => {
    if (!canTriage) return
    let cancelled = false
    api
      .listAgents()
      .then((list) => {
        if (!cancelled) setAgents({ api, list })
      })
      .catch(() => {
        if (!cancelled) setAgents({ api, list: [] })
      })
    return () => {
      cancelled = true
    }
  }, [api, canTriage])
  const agentList = useMemo(
    () => (agents !== null && agents.api === api ? agents.list : []),
    [agents, api],
  )
  const agentName = (id: string | null | undefined) =>
    agentList.find((entry) => entry.id === id)?.name ?? t('inbox:unknownAgent')

  const setParam = (key: string, value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (value === '' || (key === 'kind' && value === 'all')) next.delete(key)
        else next.set(key, value)
        return next
      },
      { replace: true },
    )
  const reset = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('kind')
        next.delete('agent')
        return next
      },
      { replace: true },
    )

  const count = (k: Kind) => (counts === null ? null : countFor(counts, k, isAdmin))
  const shows = (k: Kind) => (kind === 'all' || kind === k) && (count(k) ?? 0) > 0

  // --- Zeilen je Art -------------------------------------------------------
  // Nachkontrollen: Zeilen sind Reviews (Server `due=true`), die Abschnittszahl
  // bleibt `follow_ups_due` (Aenderungen). viewer fragt nie (ab editor).
  const followUpsCount = count('followUps') ?? 0
  const followUps = useFollowUpRows(
    api,
    canTriage && shows('followUps'),
    `${agent}|${followUpsCount}`,
    agentId,
  )
  const memoryCount = count('memory') ?? 0
  const memory = useSectionRows(
    api,
    shows('memory'),
    `${role}|${agent}|${memoryCount}`,
    (client) => {
      const filter: MemoryFilter = { status: 'pending' }
      if (!canTriage) filter.scope = 'user'
      if (agentId) filter.agent_id = agentId
      return client.listMemories(filter, { limit: INBOX_ROWS_PER_KIND }).then((page) => page.items)
    },
  )
  const casesCount = count('cases') ?? 0
  const cases = useSectionRows(api, shows('cases'), `${agent}|${casesCount}`, (client) =>
    client
      .listCases(
        { status: ['open', 'reopened'], ...(agentId ? { agent_id: agentId } : {}) },
        { limit: INBOX_ROWS_PER_KIND },
      )
      .then((page) => page.items),
  )
  // Versionen: admin als Aufgabe, editor unter „Zum Anschauen“. Mit Agent-
  // Filter liefert `/inbox/counts` `null` (eine Version gehoert keinem Agenten).
  const versionsTotal =
    counts === null || counts.versions_review === null
      ? 0
      : counts.versions_review + (counts.system_prompts_review ?? 0)
  const versionsWanted = canTriage && versionsTotal > 0 && (isAdmin ? shows('versions') : kind === 'all')
  const versions = useSectionRows(
    api,
    versionsWanted,
    `${role}|${versionsTotal}`,
    loadReviewVersions,
  )

  // --- Darstellung ---------------------------------------------------------
  const followUpRows: InboxRow[] | null =
    followUps.items?.map((item) => {
      const title = t('inbox:followUps.row', {
        date: formatDay(item.created_at),
        agent: agentName(item.agent_id),
      })
      // Nur die Pill rechnet lokal (Tage seit dem Server-Termin); ob die Zeile
      // faellig ist, sagt allein der Server. Liegt sein Termin nach dem lokalen
      // Kalendertag (UTC-Stichtag, PM 2026-10-14), heisst sie „heute fällig“.
      const days =
        item.next_follow_up_at !== null ? Math.max(daysSince(item.next_follow_up_at), 0) : null
      return {
        id: item.id,
        title,
        badge:
          days !== null && !Number.isNaN(days) ? (
            <MetaPill tone="brand" icon={CalendarClock} className="whitespace-normal">
              {days === 0
                ? t('inbox:followUps.today')
                : t('inbox:followUps.since', { count: days })}
            </MetaPill>
          ) : null,
        meta: [
          t('inbox:followUps.changes', { count: item.due_measure_count }),
          ...(item.next_follow_up_at !== null
            ? [t('inbox:followUps.term', { date: formatDay(item.next_follow_up_at) })]
            : []),
        ].join(' · '),
        actionLabel: t('inbox:followUps.open'),
        actionAriaLabel: t('inbox:followUps.openAria', { title }),
        href: wsPath(
          `/agents/${encodeURIComponent(item.agent_id)}/reviews/${encodeURIComponent(item.id)}?change=first-due`,
        ),
      }
    }) ?? null
  const memoryHref = () =>
    wsPath(`/memory?tab=approval${agent !== '' ? `&agent=${encodeURIComponent(agent)}` : ''}`)
  const memoryRows: InboxRow[] | null =
    memory.items?.map((item) => {
      const owner =
        item.scope === 'user' ? t('inbox:memory.userMemory') : agentName(item.agent_id)
      return {
        id: item.id,
        title: t('inbox:quoted', { text: item.fact }),
        meta: [owner, age(item.created_at)].join(' · '),
        actionLabel: t('inbox:action.review'),
        actionAriaLabel: t('inbox:action.reviewAria', { text: item.fact }),
        href: wsPath(`/memory?tab=approval&entry=${encodeURIComponent(item.id)}`),
      }
    }) ?? null

  const caseRows: InboxRow[] | null =
    cases.items?.map((item) => ({
      id: item.id,
      title: item.behavior,
      meta: [
        agentName(item.agent_id),
        age(item.created_at),
        ...(item.status === 'reopened' ? [t('inbox:cases.reopened')] : []),
      ].join(' · '),
      actionLabel: t('inbox:action.triage'),
      actionAriaLabel: t('inbox:action.triageAria', { text: item.behavior }),
      href: wsPath(`/feedback/cases/${item.id}`),
    })) ?? null

  const versionItems = versions.items ?? []
  const versionRows: InboxRow[] | null =
    versions.items === null
      ? null
      : versionItems.slice(0, INBOX_ROWS_PER_KIND).map((item) => ({
          id: `${item.type}-${item.id}`,
          title: t('inbox:versions.row', { name: item.name, version: item.version }),
          meta: t(`inbox:versions.type.${item.type}`),
          actionLabel: t('inbox:action.open'),
          actionAriaLabel: t('inbox:action.openVersionAria', {
            name: item.name,
            version: item.version,
          }),
          href: wsPath(`${VERSION_PATH[item.type]}/${item.id}${versionDiffSearch(item.version)}`),
        }))
  const versionTypeCounts = VERSION_TYPES.map((type) => ({
    type,
    count: versionItems.filter((item) => item.type === type).length,
  })).filter((entry) => entry.count > 0)
  const firstVersionList =
    versionTypeCounts.length > 0
      ? wsPath(`${VERSION_PATH[versionTypeCounts[0].type]}?status=review`)
      : wsPath('/personas?status=review')

  // „Zum Anschauen“: zaehlt nicht in die Glocke (§2.4).
  const lookRows: InboxLookRow[] = []
  if (canTriage && kind === 'all' && counts !== null) {
    const patterns = counts.patterns ?? 0
    if (patterns > 0) {
      lookRows.push({
        id: 'patterns',
        title: t('inbox:look.patterns', { count: patterns }),
        description: t('inbox:look.patternsHint'),
        href: wsPath('/feedback?tab=patterns'),
      })
    }
    if (!isAdmin && versionsTotal > 0) {
      lookRows.push({
        id: 'versions',
        title: t('inbox:look.versions', { count: versionsTotal }),
        description:
          versionTypeCounts.length > 0
            ? `${versionTypeCounts
                .map((entry) => t(`inbox:versions.typeCount.${entry.type}`, { count: entry.count }))
                .join(' · ')} – ${t('inbox:kind.versionsEditorHint')}`
            : t('inbox:kind.versionsEditorHint'),
        href: firstVersionList,
      })
    }
  }

  const statusOptions: StatusChipOption[] = [
    { value: 'all', label: t('data:filter.all'), count: counts?.total ?? null, keepWhenZero: true },
    ...KINDS.filter((k) => count(k) !== null).map((k) => ({
      value: k,
      label: t(`inbox:chip.${k}`),
      count: count(k),
    })),
  ]
  const filterActive = kind !== 'all' || agent !== ''
  const visibleTotal = KINDS.filter(shows).reduce((sum, k) => sum + (count(k) ?? 0), 0)

  const showAll = (total: number, shown: number, href: string) =>
    total > shown ? { label: t('inbox:showAll', { count: total }), href } : null

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader title={t('inbox:page.title')} description={t('inbox:page.description')} />

        {counts === null && countsFailed ? (
          <div className="flex flex-col items-start gap-3">
            <ErrorAlert message={t('inbox:loadError')} />
            <Button type="button" variant="outline" onClick={reloadCounts}>
              {t('inbox:retry')}
            </Button>
          </div>
        ) : counts === null || role === null ? (
          <LoadingState rows={3} />
        ) : (
          <>
            {canTriage ? (
              <ListFilterBar
                statusOptions={statusOptions}
                status={kind}
                onStatusChange={(value) => setParam('kind', value)}
                agents={[...agentList]
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map((entry) => ({ id: entry.id, name: entry.name }))}
                agent={agent}
                onAgentChange={(value) => setParam('agent', value)}
                active={filterActive}
                onReset={reset}
                resultCount={kind === 'all' ? counts.total : count(kind)}
                idPrefix="inbox-filter"
              />
            ) : null}

            {shows('followUps') ? (
              <div className="flex flex-col gap-3">
                <InboxSection
                  kind="followUps"
                  icon={CalendarClock}
                  title={t('inbox:kind.followUps')}
                  count={followUpsCount}
                  hint={t('inbox:kind.followUpsHint')}
                  rows={followUpRows}
                  loading={followUps.loading}
                  failed={followUps.failed}
                  onRetry={followUps.retry}
                  primary
                />
                {followUps.hasMore || followUps.moreFailed || agentId !== undefined ? (
                  <div
                    className="flex flex-wrap items-center gap-x-4 gap-y-2"
                    data-testid="inbox-followups-more"
                  >
                    {followUps.hasMore ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="min-h-11 md:min-h-0"
                        disabled={followUps.loadingMore}
                        aria-busy={followUps.loadingMore}
                        onClick={followUps.loadMore}
                      >
                        {followUps.loadingMore
                          ? t('inbox:followUps.loadingMore')
                          : t('inbox:followUps.loadMore')}
                      </Button>
                    ) : null}
                    {followUps.moreFailed ? (
                      <p role="alert" className="text-sm text-destructive">
                        {t('inbox:sectionError')}
                      </p>
                    ) : null}
                    {agentId !== undefined ? (
                      <Link
                        to={wsPath(`/agents/${encodeURIComponent(agentId)}?tab=evolution`)}
                        className={cn(
                          'inline-flex min-h-11 items-center gap-1 rounded-sm text-sm font-medium underline-offset-4 hover:underline md:min-h-0',
                          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
                        )}
                      >
                        {t('inbox:followUps.atAgent', { agent: agentName(agentId) })}
                        <ArrowRight className="size-4" aria-hidden="true" />
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            {shows('memory') ? (
              <InboxSection
                kind="memory"
                icon={Brain}
                title={t('inbox:kind.memory')}
                count={memoryCount}
                hint={t('inbox:kind.memoryHint')}
                rows={memoryRows}
                loading={memory.loading}
                failed={memory.failed}
                onRetry={memory.retry}
                showAll={showAll(memoryCount, memoryRows?.length ?? 0, memoryHref())}
              />
            ) : null}

            {isAdmin && shows('versions') ? (
              <InboxSection
                kind="versions"
                icon={ClipboardCheck}
                title={t('inbox:kind.versions')}
                count={versionsTotal}
                hint={t('inbox:kind.versionsHint')}
                rows={versionRows}
                loading={versions.loading}
                failed={versions.failed}
                onRetry={versions.retry}
                showAll={showAll(versionsTotal, versionRows?.length ?? 0, firstVersionList)}
              />
            ) : null}

            {shows('cases') ? (
              <InboxSection
                kind="cases"
                icon={MessageSquareWarning}
                title={t('inbox:kind.cases')}
                count={casesCount}
                hint={t('inbox:kind.casesHint')}
                rows={caseRows}
                loading={cases.loading}
                failed={cases.failed}
                onRetry={cases.retry}
                showAll={showAll(
                  casesCount,
                  caseRows?.length ?? 0,
                  wsPath(`/feedback?tab=cases${agent !== '' ? `&agent=${encodeURIComponent(agent)}` : ''}`),
                )}
              />
            ) : null}

            {visibleTotal === 0 ? (
              filterActive ? (
                <EmptyState
                  title={t('data:filter.emptyFilteredTitle')}
                  description={t('inbox:empty.filtered')}
                  action={
                    <Button type="button" variant="outline" onClick={reset}>
                      {t('data:filter.reset')}
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={CircleCheck}
                  title={t('inbox:empty.title')}
                  description={t('inbox:empty.description')}
                />
              )
            ) : null}

            <InboxLookSection rows={lookRows} />
          </>
        )}
      </Stack>
    </Container>
  )
}
