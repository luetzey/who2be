import { Brain, MoreHorizontal, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { EmptyState } from '@/components/data/EmptyState'
import { MemoryDetailSheet } from '@/components/memory/MemoryDetailSheet'
import { ActiveFilterChips, FilterSheetButton } from '@/components/memory/MemoryFacets'
import { MemoryList } from '@/components/memory/MemoryList'
import type { MemoryEntryState } from '@/components/memory/MemoryRow'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { notify } from '@/lib/feedback'

import {
  ENTRY_FACETS,
  useMemoryEntries,
  type EntryFacet,
  type EntryFilters,
} from '@/features/memory/hooks/useMemoryApi'

// Obergrenzen je Agent (ADR-0053 3.1.5, packages/models memory.py):
// Eintraege ohne Agentennotizen bzw. Agentennotizen, jeweils ueber alle Status.
const MAX_ENTRIES = 500
const MAX_NOTES = 200
// Ab diesem Anteil steht „fast voll“ hinter der Zahl (Spec §6.6).
const NEARLY_FULL = 0.9

// Dauer des Deep-Link-Highlights (`#memory`, Pill der Agentenuebersicht).
const HIGHLIGHT_MS = 2000

type FacetFilters = Omit<EntryFilters, 'agent'>

const NO_FILTERS: FacetFilters = {
  kind: '',
  status: '',
  health: '',
  origin: '',
  source: '',
  q: '',
  sort: 'newest',
}

interface CardCounts {
  pending: number | null
  total: number | null
  notes: number | null
}

/**
 * Zahlen der Karte, immer vom Server: offene Freigaben (wie der Tab-Zaehler
 * „Zur Freigabe“: `status=pending` plus offene Aenderungsvorschlaege) und der
 * Fuellstand. Ein Fehler laesst nur die jeweilige Zahl weg.
 */
function useAgentMemoryCounts(agentId: string, nonce: number): CardCounts {
  const api = useApi()
  const [counts, setCounts] = useState<CardCounts>({ pending: null, total: null, notes: null })

  useEffect(() => {
    let cancelled = false
    Promise.all([
      api.countMemories({ scope: 'agent', agent_id: agentId, status: 'pending' }),
      api.listMemoryProposals({ status: 'pending', agent_id: agentId }),
    ])
      .then(([pending, proposals]) => {
        if (cancelled) return
        const open = proposals.filter((proposal) => proposal.status === 'pending').length
        setCounts((current) => ({ ...current, pending: pending.total + open }))
      })
      .catch(() => {
        if (!cancelled) setCounts((current) => ({ ...current, pending: null }))
      })
    api
      .countMemories({ scope: 'agent', agent_id: agentId }, ['kind'])
      .then((result) => {
        if (cancelled) return
        setCounts((current) => ({
          ...current,
          total: result.total,
          notes: result.groups?.kind?.agent_note ?? 0,
        }))
      })
      .catch(() => {
        if (!cancelled) setCounts((current) => ({ ...current, total: null, notes: null }))
      })
    return () => {
      cancelled = true
    }
  }, [api, agentId, nonce])

  return counts
}

/**
 * Gedaechtnis-Karte der Agent-Seite (Spec §6.6, ersetzt `AgentMemorySection`):
 * dieselbe `MemoryList` wie der Tab „Eintraege“, der Agent fest gesetzt und
 * ohne Agent-Facette. Freigaben passieren nur in der Warteschlange; die Karte
 * verlinkt dorthin. Agentengedaechtnis sieht erst `editor` (ADR-0053 6.4.1) —
 * fuer viewer rendert die Karte nichts.
 */
export function AgentMemoryCard({ agent }: { agent: Agent }) {
  const role = useCurrentWorkspaceRole()
  if (role === null || role === 'viewer') return null
  return <AgentMemoryCardContent agent={agent} />
}

function AgentMemoryCardContent({ agent }: { agent: Agent }) {
  const { t, i18n } = useTranslation('agents')
  const wsPath = useWorkspacePath()
  const searchId = useId()
  const sortId = useId()
  const [facets, setFacets] = useState<FacetFilters>(NO_FILTERS)
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query.trim())
  const [nonce, setNonce] = useState(0)
  const format = useMemo(() => new Intl.NumberFormat(i18n.language), [i18n.language])

  const filters = useMemo<EntryFilters>(
    () => ({ ...facets, q: debouncedQuery, agent: agent.id }),
    [facets, debouncedQuery, agent.id],
  )
  const data = useMemoryEntries(filters, true)
  const counts = useAgentMemoryCounts(agent.id, nonce)
  const memoryOff = (agent.tool_policy.memory_mode ?? 'off') === 'off'

  // Deep-Link `#memory`: zur Karte scrollen und sie kurz hervorheben.
  const { hash, state } = useLocation()
  const cardRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (hash !== '#memory') return
    const card = cardRef.current
    if (card === null) return
    card.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // Hervorhebung direkt am Element: kein State, keine Kaskade.
    card.dataset.highlighted = 'true'
    const timer = window.setTimeout(() => {
      delete card.dataset.highlighted
    }, HIGHLIGHT_MS)
    return () => window.clearTimeout(timer)
  }, [hash])

  const setFacet = useCallback((facet: EntryFacet, value: string) => {
    // Der Agent ist fest; nur die uebrigen Facetten sind waehlbar.
    if (facet === 'agent') return
    setFacets((current) => ({ ...current, [facet]: value }))
  }, [])

  const resetFilters = () => {
    setFacets(NO_FILTERS)
    setQuery('')
  }

  const refresh = () => {
    data.reload()
    setNonce((value) => value + 1)
  }

  // Detail-Sheet (C5c-2, Spec §6.6/§7): der Chevron je Zeile setzt
  // `?entry=<id>` und gibt den Eintrag im Router-State mit (wie auf /memory).
  const [params, setParams] = useSearchParams()
  const entryId = params.get('entry')
  const entryState = (state as Partial<MemoryEntryState> | null)?.memory ?? null
  const closeEntry = () =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.delete('entry')
        return next
      },
      { replace: true },
    )

  // „In der Gedaechtnisverwaltung oeffnen“ uebernimmt die gesetzten Filter.
  const centralHref = useMemo(() => {
    const params = new URLSearchParams({ tab: 'entries', agent: agent.id })
    for (const facet of ENTRY_FACETS) {
      if (facet !== 'agent' && filters[facet] !== '') params.set(facet, filters[facet])
    }
    if (filters.q !== '') params.set('q', filters.q)
    if (filters.sort === 'oldest') params.set('sort', 'oldest')
    return wsPath(`/memory?${params.toString()}`)
  }, [agent.id, filters, wsPath])

  const hasEntries = (counts.total ?? 0) > 0 || data.items.length > 0
  const entries = counts.total !== null && counts.notes !== null ? counts.total - counts.notes : null

  return (
    <Card
      id="memory"
      ref={cardRef}
      data-testid="agent-memory-card"
      className="scroll-mt-6 transition-shadow duration-[var(--duration-fast)] ease-standard data-[highlighted=true]:ring-2 data-[highlighted=true]:ring-brand/50"
    >
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <CardTitle tabIndex={-1} className="outline-none" data-memory-card-heading>
              {t('memory.title')}
            </CardTitle>
            <CardDescription>{t('memory.description')}</CardDescription>
          </div>
          {(counts.total ?? 0) > 0 ? (
            <DeleteAllMenu agent={agent} count={counts.total ?? 0} onDeleted={refresh} />
          ) : null}
        </div>
        {entries !== null && counts.notes !== null ? (
          <p
            className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
            data-testid="memory-fill"
          >
            <FillLevel
              text={t('memory.capEntries', {
                count: entries,
                formatted: format.format(entries),
                maximum: format.format(MAX_ENTRIES),
              })}
              nearlyFull={entries >= MAX_ENTRIES * NEARLY_FULL}
            />
            <FillLevel
              text={t('memory.capNotes', {
                count: counts.notes,
                formatted: format.format(counts.notes),
                maximum: format.format(MAX_NOTES),
              })}
              nearlyFull={counts.notes >= MAX_NOTES * NEARLY_FULL}
            />
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-4">
        {memoryOff ? (
          <AttentionBanner
            icon={Brain}
            title={t('memory.off')}
            description={hasEntries ? t('memory.offReadOnly') : undefined}
          />
        ) : null}

        {(counts.pending ?? 0) > 0 ? (
          <div
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 p-3"
            data-testid="memory-pending-hint"
          >
            <p className="text-sm font-medium" aria-live="polite">
              {t('memory.pendingHint', {
                count: counts.pending ?? 0,
                formatted: format.format(counts.pending ?? 0),
              })}
            </p>
            <Button asChild variant="outline" size="sm" className="min-h-10 md:min-h-0">
              <Link
                to={wsPath(`/memory?tab=approval&agent=${encodeURIComponent(agent.id)}`)}
                data-testid="memory-to-approval"
              >
                {t('memory.toApproval')}
              </Link>
            </Button>
          </div>
        ) : null}

        {memoryOff && !hasEntries ? null : (
          <>
            <div className="flex flex-col gap-3 md:flex-row md:items-end">
              <p
                className="text-sm break-words text-muted-foreground md:self-center md:pt-5"
                data-testid="memory-fixed-agent"
              >
                {t('memory.fixedAgent', { agent: agent.name })}
              </p>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <Label htmlFor={searchId}>{t('learning:approval.search')}</Label>
                <Input
                  id={searchId}
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t('learning:entries.searchPlaceholderPlain')}
                />
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <FilterSheetButton
                  filters={filters}
                  counts={data.counts}
                  countsError={data.countsError}
                  agents={data.agents}
                  hideAgent
                  alwaysVisible
                  onChange={setFacet}
                  total={data.counts?.total ?? null}
                  onReset={resetFilters}
                />
                <div className="flex flex-col gap-1">
                  <Label htmlFor={sortId}>{t('learning:entries.sort.label')}</Label>
                  <Select
                    id={sortId}
                    value={facets.sort}
                    className="min-h-11 md:min-h-10"
                    onChange={(event) =>
                      setFacets((current) => ({
                        ...current,
                        sort: event.target.value === 'oldest' ? 'oldest' : 'newest',
                      }))
                    }
                  >
                    <option value="newest">{t('learning:entries.sort.newest')}</option>
                    <option value="oldest">{t('learning:entries.sort.oldest')}</option>
                  </Select>
                </div>
              </div>
            </div>
            <ActiveFilterChips
              filters={filters}
              agents={data.agents}
              hideAgent
              onChange={setFacet}
            />
            <MemoryList
              data={data}
              filters={filters}
              onFilter={setFacet}
              onResetFilters={resetFilters}
              onChanged={() => setNonce((value) => value + 1)}
              fixedAgentId={agent.id}
              readOnly={memoryOff}
              detailLinks
              emptyState={
                <EmptyState
                  title={t('memory.empty.title')}
                  description={t('memory.empty.description')}
                />
              }
            />
          </>
        )}

        <Link
          to={centralHref}
          className="self-start text-sm font-medium underline-offset-4 hover:underline"
          data-testid="memory-open-central"
        >
          {t('memory.openCentral')} <span aria-hidden="true">→</span>
        </Link>
      </CardContent>
      <MemoryDetailSheet
        entryId={entryId}
        initial={entryState}
        onClose={closeEntry}
        onChanged={refresh}
        fallbackFocus={() => cardRef.current?.querySelector<HTMLElement>('[data-memory-card-heading]') ?? null}
      />
    </Card>
  )
}

/** Fuellstand als Text, ab 90 % mit „fast voll“ als Punkt + Wort. */
function FillLevel({ text, nearlyFull }: { text: string; nearlyFull: boolean }) {
  const { t } = useTranslation('agents')
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span>{text}</span>
      {nearlyFull ? (
        <span className="inline-flex items-center gap-1 font-medium text-foreground">
          <span
            aria-hidden="true"
            className="size-2 shrink-0 rounded-full"
            style={{ backgroundColor: 'var(--status-review)' }}
          />
          {t('memory.nearlyFull')}
        </span>
      ) : null}
    </span>
  )
}

/**
 * „Alle löschen“ im Overflow der Karte (Spec §6.6): `destructive`, mit
 * Bestaetigung samt Anzahl. `DELETE /agents/{id}/memories` (editor).
 */
function DeleteAllMenu({
  agent,
  count,
  onDeleted,
}: {
  agent: Agent
  count: number
  onDeleted: () => void
}) {
  const { t, i18n } = useTranslation('agents')
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const formatted = new Intl.NumberFormat(i18n.language).format(count)

  const submit = async () => {
    setBusy(true)
    try {
      await api.deleteAllAgentMemories(agent.id)
      notify.success(t('memory.deleteAll.success'))
      setOpen(false)
      onDeleted()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('memory.deleteAll.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-h-10 shrink-0 md:min-h-0"
            aria-label={t('memory.actions', { name: agent.name })}
            data-testid="memory-actions"
          >
            <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem className="text-destructive" onSelect={() => setOpen(true)}>
            <Trash2 aria-hidden="true" />
            {t('memory.deleteAll.label')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('memory.deleteAll.dialogTitle', { count, formatted })}</DialogTitle>
            <DialogDescription>{t('memory.deleteAll.dialogDescription')}</DialogDescription>
          </DialogHeader>
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
              onClick={() => void submit()}
            >
              {t('memory.deleteAll.confirmLabel', { count, formatted })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
