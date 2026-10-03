import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useSearchParams } from 'react-router-dom'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { MemoryDetailSheet } from '@/components/memory/MemoryDetailSheet'
import {
  ActiveFilterChips,
  FilterSheetButton,
  MemoryFacetColumn,
} from '@/components/memory/MemoryFacets'
import { MemoryList } from '@/components/memory/MemoryList'
import type { MemoryEntryState } from '@/components/memory/MemoryRow'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAgents } from '@/hooks/useAgents'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

import { ApprovalQueue } from '../components/ApprovalQueue'
import {
  ENTRY_FACETS,
  entryFiltersFrom,
  useMemoryEntries,
  useMemoryTabCounts,
  type EntryFacet,
} from '../hooks/useMemoryApi'

type MemoryTab = 'approval' | 'entries'

/**
 * Gedaechtnis-Seite (Spec §4, §11.2). Tabs „Zur Freigabe“ (C5a) und
 * „Eintraege“ (C5b-1, nur editor+); „Mein Gedaechtnis“ folgt mit C5d.
 * `?tab=` ist die Quelle des aktiven Tabs; Suche (`q`) und Filter stehen in
 * der URL, damit Links stabil sind. Ein Viewer, der `?tab=entries` oeffnet,
 * landet still auf `approval` — fuer ihn gibt es den Tab nicht (Spec §3).
 * `?entry=<id>` oeffnet das Detail-Sheet (C5c-1) ueber beiden Tabs.
 */
export function MemoryPage() {
  const { t, i18n } = useTranslation('learning')
  const role = useCurrentWorkspaceRole()
  const canManageAgents = role !== null && role !== 'viewer'
  const [params, setParams] = useSearchParams()
  const searchId = useId()
  const [countNonce, setCountNonce] = useState(0)

  const requested = params.get('tab')
  const tab: MemoryTab = requested === 'entries' && canManageAgents ? 'entries' : 'approval'

  const [query, setQuery] = useState(params.get('q') ?? '')
  const debouncedQuery = useDebouncedValue(query.trim())

  // Fehlendes oder (fuer diese Rolle) unbekanntes `tab` korrigieren. Solange
  // die Rolle noch laedt, bleibt `entries` stehen — sonst verlöre ein
  // Deep-Link beim ersten Rendern seinen Tab.
  useEffect(() => {
    if (requested === tab) return
    if (requested === 'entries' && role === null) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('tab', tab)
        return next
      },
      { replace: true },
    )
  }, [requested, tab, role, setParams])

  useEffect(() => {
    if ((params.get('q') ?? '') === debouncedQuery) return
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        if (debouncedQuery === '') next.delete('q')
        else next.set('q', debouncedQuery)
        return next
      },
      { replace: true },
    )
  }, [debouncedQuery, params, setParams])

  const setParam = (key: string, value: string) =>
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (value === '') next.delete(key)
      else next.set(key, value)
      return next
    })

  const resetFilters = () => {
    setQuery('')
    setParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('q')
      for (const facet of ENTRY_FACETS) next.delete(facet)
      return next
    })
  }

  // Tabwechsel per Klick: nur `tab` bleibt, Filter gelten je Tab.
  const switchTab = (value: string) => {
    setQuery('')
    setParams(new URLSearchParams({ tab: value }))
    setCountNonce((value) => value + 1)
  }

  const counts = useMemoryTabCounts(canManageAgents, countNonce)
  const format = new Intl.NumberFormat(i18n.language)

  // Detail-Sheet (C5c-1): `?entry=<id>`; der Eintrag kommt, wenn vorhanden,
  // aus der Liste im Router-State mit.
  const location = useLocation()
  const entryId = params.get('entry')
  const entryState = (location.state as Partial<MemoryEntryState> | null)?.memory ?? null
  const [listNonce, setListNonce] = useState(0)
  const closeEntry = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('entry')
        return next
      },
      { replace: true },
    )
  const entryChanged = () => {
    setCountNonce((value) => value + 1)
    setListNonce((value) => value + 1)
  }
  const sheet = (
    <MemoryDetailSheet
      entryId={entryId}
      initial={entryState}
      onClose={closeEntry}
      onChanged={entryChanged}
      fallbackFocus={() => document.querySelector<HTMLElement>('[data-memory-tab-heading]')}
    />
  )

  const search = (placeholder: string) => (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <Label htmlFor={searchId}>{t('approval.search')}</Label>
      <Input
        id={searchId}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={placeholder}
      />
    </div>
  )

  const approval = (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        {search(t('approval.searchPlaceholder'))}
        {canManageAgents ? (
          <AgentFilter value={params.get('agent') ?? ''} onChange={(id) => setParam('agent', id)} />
        ) : null}
      </div>
      <ApprovalQueue
        key={listNonce}
        q={params.get('q') ?? ''}
        agentId={canManageAgents ? (params.get('agent') ?? '') : ''}
        onShowAgent={(id) => setParam('agent', id)}
        onResetFilters={resetFilters}
      />
    </div>
  )

  if (!canManageAgents) {
    // Viewer: ein Tab — keine Leiste, nur die Ueberschrift (bis C5d).
    return (
      <Container>
        <PageHeader title={t('page.title')} description={t('page.description')} />
        <div className="mt-6 flex flex-col gap-6">
          <h2 className="text-lg font-semibold outline-none" tabIndex={-1} data-memory-tab-heading>
            {t('page.tabs.approval')}
          </h2>
          {approval}
        </div>
        {sheet}
      </Container>
    )
  }

  const tabLabel = (key: MemoryTab, count: number | null) => (
    <>
      <span>{t(`page.tabs.${key}`)}</span>
      {count !== null ? (
        <span className="text-muted-foreground tabular-nums" data-testid={`tab-count-${key}`}>
          <span aria-hidden="true">{format.format(count)}</span>
          <span className="sr-only">
            , {t('entries.resultCount', { count, formatted: format.format(count) })}
          </span>
        </span>
      ) : null}
    </>
  )

  return (
    <Container>
      <PageHeader title={t('page.title')} description={t('page.description')} />
      <Tabs value={tab} onValueChange={switchTab} className="mt-6">
        <TabsList aria-label={t('page.tabsAria')}>
          <TabsTrigger value="approval">{tabLabel('approval', counts.approval)}</TabsTrigger>
          <TabsTrigger value="entries">{tabLabel('entries', counts.entries)}</TabsTrigger>
        </TabsList>
        <TabsContent value="approval">
          {/* Ueberschriftenfolge h1 → h2 → h3 (Gruppenkoepfe) auch mit Tabs. */}
          <h2 className="sr-only" tabIndex={-1} data-memory-tab-heading>
            {t('page.tabs.approval')}
          </h2>
          {approval}
        </TabsContent>
        <TabsContent value="entries">
          <h2 className="sr-only" tabIndex={-1} data-memory-tab-heading>
            {t('page.tabs.entries')}
          </h2>
          <EntriesTab
            params={params}
            reloadNonce={listNonce}
            search={search(
              counts.entries !== null
                ? t('entries.searchPlaceholder', {
                    count: counts.entries,
                    formatted: format.format(counts.entries),
                  })
                : t('entries.searchPlaceholderPlain'),
            )}
            onFilter={setParam}
            onResetFilters={resetFilters}
            onChanged={() => setCountNonce((value) => value + 1)}
          />
        </TabsContent>
      </Tabs>
      {sheet}
    </Container>
  )
}

interface EntriesTabProps {
  params: URLSearchParams
  // Erhoeht sich nach einer Aenderung im Detail-Sheet → Liste neu laden.
  reloadNonce: number
  search: ReactNode
  onFilter: (key: string, value: string) => void
  onResetFilters: () => void
  onChanged: () => void
}

/** Tab „Eintraege“ (S2′): Facetten links ab `lg`, sonst Filter-Sheet. */
function EntriesTab({
  params,
  reloadNonce,
  search,
  onFilter,
  onResetFilters,
  onChanged,
}: EntriesTabProps) {
  const { t } = useTranslation('learning')
  const sortId = useId()
  // `entry` (Detail-Sheet) ist kein Filter: oeffnen/schliessen laedt nichts neu.
  const key = useMemo(() => {
    const next = new URLSearchParams(params)
    next.delete('entry')
    return next.toString()
  }, [params])
  // Wertgleichheit der URL: neue Filter nur, wenn sich die Parameter aendern.
  const filters = useMemo(() => entryFiltersFrom(new URLSearchParams(key)), [key])
  const data = useMemoryEntries(filters, true)
  const { reload } = data
  useEffect(() => {
    if (reloadNonce > 0) reload()
  }, [reload, reloadNonce])
  const setFacet = (facet: EntryFacet, value: string) => onFilter(facet, value)
  const facetProps = {
    filters,
    counts: data.counts,
    countsError: data.countsError,
    agents: data.agents,
    onChange: setFacet,
  }

  return (
    <div className="flex min-w-0 flex-col gap-6 lg:flex-row lg:items-start">
      <MemoryFacetColumn {...facetProps} />
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          {search}
          <div className="flex flex-wrap items-end gap-2">
            <FilterSheetButton
              {...facetProps}
              total={data.counts?.total ?? null}
              onReset={onResetFilters}
            />
            <div className="flex flex-col gap-1">
              <Label htmlFor={sortId}>{t('entries.sort.label')}</Label>
              <Select
                id={sortId}
                value={filters.sort}
                className="min-h-11 md:min-h-10"
                onChange={(event) =>
                  onFilter('sort', event.target.value === 'oldest' ? 'oldest' : '')
                }
              >
                <option value="newest">{t('entries.sort.newest')}</option>
                <option value="oldest">{t('entries.sort.oldest')}</option>
              </Select>
            </div>
          </div>
        </div>
        <ActiveFilterChips filters={filters} agents={data.agents} onChange={setFacet} />
        <MemoryList
          data={data}
          filters={filters}
          onFilter={setFacet}
          onResetFilters={onResetFilters}
          onChanged={onChanged}
          detailLinks
        />
      </div>
    </div>
  )
}

function AgentFilter({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useTranslation('learning')
  const { agents } = useAgents()
  const selectId = useId()
  return (
    <div className="flex flex-col gap-1 md:w-64">
      <Label htmlFor={selectId}>{t('approval.agentFilter')}</Label>
      <Select id={selectId} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('approval.allAgents')}</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name}
          </option>
        ))}
      </Select>
    </div>
  )
}
