import { Bot, ChevronRight, TriangleAlert } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type { MemoryBatchAction, MemoryBatchItemResult, MemoryRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ExpandableText } from '@/components/data/ExpandableText'
import { LoadingState } from '@/components/data/LoadingState'
import { RejectDialog, holdCauseOf, useEntryLink } from '@/components/memory/MemoryRow'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'
import { cn } from '@/lib/utils'

import {
  ENTRIES_LOADED_LIMIT,
  SELECTION_LIMIT,
  apiReason,
  countMismatchOf,
  failuresOf,
  memoryFilterOf,
  useReasonText,
  type EntryFacet,
  type EntryFilters,
  type MemoryEntriesData,
} from '@/features/memory/hooks/useMemoryApi'

// Liste des Tabs „Eintraege“ (Gedaechtnisverwaltung S2′, §6.4–§6.7, §9).
// Freitext ist immer ein Textknoten (ADR-0038) und bricht mit `break-words`.
// Der Chevron je Zeile oeffnet das Detail-Sheet (C5c-1), aber nur, wenn der
// Aufrufer `detailLinks` setzt (dort wertet ein Sheet `?entry=` aus).

// Zeilenaktionen: 40 px unter md, Standardhoehe darueber (Spec §15).
const ROW_ACTION = 'min-h-10 md:min-h-0'

type RowAction = 'confirm' | 'reactivate' | 'approve'

/**
 * Die eine sichtbare Zeilenaktion je Status (Spec §6.4), sonst `null`.
 * Zurueckgehaltene (`holdCauseOf` != null) bekommen hier KEIN „Freigeben“:
 * sie werden nur in der Warteschlange entschieden, einzeln und mit
 * sichtbarem Grund (Spec §5.2/F1) — die Zeile verlinkt stattdessen dorthin.
 */
function rowActionOf(memory: MemoryRead): RowAction | null {
  if (memory.kind === 'lesson') return null
  if (memory.status === 'active' && !memory.confirmed_at) return 'confirm'
  if (memory.status === 'expired') return 'reactivate'
  if (memory.status === 'pending' && holdCauseOf(memory) === null) return 'approve'
  return null
}

/** Zurueckgehaltener Vorschlag: Entscheidung gehoert in die Warteschlange. */
function decidesInQueue(memory: MemoryRead): boolean {
  return memory.status === 'pending' && memory.kind !== 'lesson' && holdCauseOf(memory) !== null
}

/** Passt ein Eintrag zur Stapelaktion? (Spec §6.5) */
function batchFits(action: MemoryBatchAction, memory: MemoryRead): boolean {
  switch (action) {
    case 'confirm':
      return memory.status === 'active' && !memory.confirmed_at && memory.kind !== 'lesson'
    case 'approve':
      return (
        memory.status === 'pending' && memory.kind !== 'lesson' && holdCauseOf(memory) === null
      )
    case 'reject':
      return memory.status === 'pending'
    case 'delete':
      return true
  }
}

function shorten(text: string, max = 60): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

const DAY_MS = 24 * 60 * 60 * 1000

// ---------------------------------------------------------------- StatusLine

/** Zeile 2: Status als Punkt + Wort, dazu Frist bzw. Auslieferungen. */
export function StatusLine({ memory }: { memory: MemoryRead }) {
  const { t } = useTranslation('learning')
  // Bezugszeit einmal je Zeile festhalten (Render bleibt rein).
  const [now] = useState(() => Date.now())
  const unconfirmed = memory.status === 'active' && !memory.confirmed_at
  const lesson = memory.kind === 'lesson'
  const word = unconfirmed ? t('health.unconfirmed') : t(`entries.status.${memory.status}`)
  const color =
    memory.status === 'active'
      ? 'var(--status-active)'
      : memory.status === 'pending'
        ? 'var(--status-review)'
        : 'var(--status-draft)'
  const parts: string[] = []
  if (lesson) {
    parts.push(t('entries.suggested', { count: memory.occurrence_count ?? 1 }))
  } else if (memory.expires_at && (memory.status === 'active' || memory.status === 'pending')) {
    if (unconfirmed || memory.status === 'pending') {
      const days = Math.max(0, Math.ceil((Date.parse(memory.expires_at) - now) / DAY_MS))
      parts.push(t('entries.expiresIn', { count: days }))
    }
  }
  if (memory.status === 'active') {
    parts.push(t('entries.delivered', { count: memory.retrieval_count }))
  }
  return (
    <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
        <span
          aria-hidden="true"
          data-testid="status-dot"
          className={cn('size-2 shrink-0 rounded-full', unconfirmed && 'border-2 bg-transparent')}
          style={unconfirmed ? { borderColor: color } : { backgroundColor: color }}
        />
        {word}
      </span>
      {parts.map((part) => (
        <span key={part} className="break-words">
          · {part}
        </span>
      ))}
    </p>
  )
}

// ------------------------------------------------------------------ EntryRow

interface EntryRowProps {
  memory: MemoryRead
  // `null` blendet den Agent-Link aus (unbekannt oder Agent-Seite selbst).
  agentName: string | null
  selected: boolean
  onToggleSelect: (id: string) => void
  failure: string | null
  onAction: (memory: MemoryRead, action: RowAction) => Promise<void>
  readOnly: boolean
  detailLink: boolean
}

/** Chevron rechts: Link-Button zum Detail-Sheet (Spec §7, §15 „Namen“). */
function DetailLink({ memory }: { memory: MemoryRead }) {
  const { t } = useTranslation('learning')
  const link = useEntryLink(memory)
  return (
    <Button
      asChild
      variant="ghost"
      size="icon"
      className="size-11 shrink-0 md:size-8"
    >
      <Link
        {...link}
        data-testid="open-detail"
        aria-haspopup="dialog"
        aria-label={t('entries.openDetail', { fact: shorten(memory.fact) })}
      >
        <ChevronRight aria-hidden="true" />
      </Link>
    </Button>
  )
}

function EntryRow({
  memory,
  agentName,
  selected,
  onToggleSelect,
  failure,
  onAction,
  readOnly,
  detailLink,
}: EntryRowProps) {
  const { t } = useTranslation('learning')
  const wsPath = useWorkspacePath()
  const [busy, setBusy] = useState(false)
  const action = readOnly ? null : rowActionOf(memory)
  const held = holdCauseOf(memory) !== null
  const kind = memory.kind ?? 'agent_note'
  const kindLabel = kind === 'user_fact' ? t('kind.user_fact_agent') : t(`kind.${kind}`)
  const originLabel = t('origin.perAgent', {
    origin: t(`origin.${memory.origin ?? 'legacy_unknown'}`),
  })

  const run = async () => {
    if (action === null) return
    setBusy(true)
    try {
      await onAction(memory, action)
    } catch {
      // Der Aufrufer zeigt den Grund an der Zeile.
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      data-testid="entry-row"
      data-memory-id={memory.id}
      className="flex min-w-0 items-start gap-3 p-4"
    >
      {readOnly ? null : held ? (
        // Zurueckgehaltene haben auch hier keine Checkbox (Spec §6.4); der
        // Platzhalter haelt die Spalte buendig.
        <span className="size-4 shrink-0" aria-hidden="true" />
      ) : (
        <Checkbox
          className="mt-1"
          checked={selected}
          onChange={() => onToggleSelect(memory.id)}
          aria-label={t('approval.selectRow', { fact: shorten(memory.fact) })}
        />
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <ExpandableText
          text={memory.fact}
          lines={3}
          mdLines={1000}
          className="text-sm font-medium break-words"
        />
        <StatusLine memory={memory} />
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span>{kindLabel}</span>
          {memory.agent_id !== null && agentName !== null ? (
            <>
              <span aria-hidden="true">·</span>
              <Link
                to={wsPath(`/agents/${memory.agent_id}`)}
                className="inline-flex min-w-0 items-center gap-1 break-words underline-offset-4 hover:underline"
              >
                <Bot className="size-3.5 shrink-0" aria-hidden="true" />
                {agentName}
              </Link>
            </>
          ) : null}
          <span aria-hidden="true">·</span>
          <span className="break-words">{originLabel}</span>
          {memory.source !== 'agent' ? (
            <>
              <span aria-hidden="true">·</span>
              <span>{t(`channel.${memory.source}`)}</span>
            </>
          ) : null}
        </p>
        {failure !== null ? (
          <p
            className="flex items-start gap-2 text-sm break-words text-destructive"
            data-testid="row-failure"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {failure}
          </p>
        ) : null}
        {!readOnly && decidesInQueue(memory) ? (
          <div className="flex justify-end pt-1">
            <Button asChild variant="outline" size="sm" className={ROW_ACTION}>
              <Link
                data-entry-focus
                data-testid="decide-in-queue"
                to={wsPath(
                  memory.agent_id
                    ? `/memory?tab=approval&agent=${encodeURIComponent(memory.agent_id)}`
                    : '/memory?tab=approval',
                )}
              >
                {t('entries.action.decideInQueue')}
              </Link>
            </Button>
          </div>
        ) : null}
        {action !== null ? (
          <div className="flex justify-end pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={ROW_ACTION}
              disabled={busy}
              data-entry-focus
              onClick={() => void run()}
            >
              {t(`entries.action.${action}`)}
            </Button>
          </div>
        ) : null}
      </div>
      {detailLink ? <DetailLink memory={memory} /> : null}
    </div>
  )
}

// ---------------------------------------------------------------- MemoryList

export interface MemoryListProps {
  data: MemoryEntriesData
  filters: EntryFilters
  onFilter: (facet: EntryFacet, value: string) => void
  onResetFilters: () => void
  // Nach jeder Aenderung (Tab-Zaehler aktualisieren).
  onChanged?: () => void
  // Agent-Seite (Spec §6.6): Agent ist fest gesetzt — er zaehlt nicht als
  // Filter, und die Zeile verlinkt nicht auf die Seite, auf der sie steht.
  fixedAgentId?: string
  // Nur lesen (Gedaechtnis beim Agenten aus, §6.6): keine Auswahl, keine
  // Zeilen- oder Stapelaktion.
  readOnly?: boolean
  // Leerzustand ohne Filter; Default ist der des Tabs „Eintraege“.
  emptyState?: ReactNode
  // Chevron je Zeile zum Detail-Sheet (`?entry=`, C5c-1). Nur, wo ein
  // `MemoryDetailSheet` die URL auswertet — sonst waere er ein toter Knopf.
  detailLinks?: boolean
}

/**
 * Liste mit Ergebniszahl, Erklaersaetzen, Zeilenaktionen, Stapelleiste und
 * Filter-Stapel. Gesamtzahlen kommen aus `counts` (Server), nie aus der
 * geladenen Teilmenge.
 */
export function MemoryList({
  data,
  filters,
  onFilter,
  onResetFilters,
  onChanged,
  fixedAgentId,
  readOnly = false,
  emptyState,
  detailLinks = false,
}: MemoryListProps) {
  const { t, i18n } = useTranslation('learning')
  const api = useApi()
  const wsPath = useWorkspacePath()
  const reasonText = useReasonText()
  const listRef = useRef<HTMLDivElement | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [selectionHint, setSelectionHint] = useState(false)
  const [failures, setFailures] = useState<Map<string, string>>(new Map())
  const [partialBanner, setPartialBanner] = useState<{
    failed: number
    action: MemoryBatchAction
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const format = useMemo(() => new Intl.NumberFormat(i18n.language), [i18n.language])

  const agentName = useCallback(
    (id: string | null | undefined) =>
      id ? (data.agents.find((agent) => agent.id === id)?.name ?? null) : null,
    [data.agents],
  )

  const focusNext = useCallback(() => {
    window.setTimeout(() => {
      const root = listRef.current
      const target =
        root?.querySelector<HTMLElement>('[data-entry-focus]') ??
        root?.querySelector<HTMLElement>('input[type="checkbox"]') ??
        null
      target?.focus()
    }, 0)
  }, [])

  const refresh = () => {
    data.reload()
    onChanged?.()
  }

  const setFailure = (id: string, message: string | null) =>
    setFailures((current) => {
      const next = new Map(current)
      if (message === null) next.delete(id)
      else next.set(id, message)
      return next
    })

  const toggleSelect = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) {
        next.delete(id)
        setSelectionHint(false)
      } else if (next.size >= SELECTION_LIMIT) {
        setSelectionHint(true)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // ----------------------------------------------------------- Einzelaktion

  const rowAction = async (memory: MemoryRead, action: RowAction) => {
    const owner = memory.scope === 'user' ? null : (memory.agent_id ?? '')
    try {
      if (action === 'confirm') await api.confirmMemory(owner, memory.id)
      else if (action === 'reactivate') await api.reactivateMemory(owner, memory.id)
      else if (owner === null) await api.triageMyMemory(memory.id, { action: 'approve' })
      else await api.triageAgentMemory(owner, memory.id, { action: 'approve' })
      setFailure(memory.id, null)
      notify.success(t(`entries.done.${action}`))
      refresh()
      focusNext()
    } catch (cause: unknown) {
      const { reason, params } = apiReason(cause)
      if (reason === 'memory_not_found' || (cause instanceof ApiError && cause.status === 404)) {
        notify.info(t('entries.gone'))
        refresh()
        return
      }
      setFailure(memory.id, reason !== null ? reasonText(reason, params) : (cause as Error).message)
      notify.error(t('batch.failedAll'))
      throw cause
    }
  }

  // ------------------------------------------------------------------ Stapel

  const applyBatchResult = (action: MemoryBatchAction, results: MemoryBatchItemResult[]) => {
    const failed = failuresOf(results)
    const ok = results.length - failed.size
    setFailures((current) => {
      const next = new Map(current)
      for (const result of results) {
        if (result.ok) next.delete(result.id)
        else next.set(result.id, reasonText(result.reason, result.params))
      }
      return next
    })
    // Fehlgeschlagene bleiben ausgewaehlt, erfolgreiche fallen heraus.
    setSelected(new Set(failed.keys()))
    setSelectionHint(false)
    if (failed.size === 0) {
      notify.success(t(`batch.done.${action}`, { count: ok }))
      setPartialBanner(null)
    } else {
      notify.info(t(`batch.partial.${action}`, { ok, failed: failed.size }))
      setPartialBanner({ failed: failed.size, action })
    }
    refresh()
  }

  const selectedRows = data.items.filter((memory) => selected.has(memory.id))
  const fitting = (action: MemoryBatchAction) =>
    selectedRows.filter((memory) => batchFits(action, memory)).map((memory) => memory.id)

  const runBatch = async (action: MemoryBatchAction, note?: string) => {
    const ids = fitting(action)
    if (ids.length === 0) return
    setBusy(true)
    try {
      const result = await api.batchMemories({ action, ids, note })
      applyBatchResult(action, result.results)
      focusNext()
    } catch {
      notify.error(t('batch.failedAll'))
      throw new Error('batch failed')
    } finally {
      setBusy(false)
    }
  }

  // --------------------------------------------------------------- Rendering

  const total = data.counts?.total ?? null
  const filtered =
    filters.q !== '' ||
    (['agent', 'kind', 'status', 'health', 'origin', 'source'] as const).some(
      (facet) => filters[facet] !== '' && !(facet === 'agent' && fixedAgentId !== undefined),
    )

  if (data.loading && data.items.length === 0) {
    return <LoadingState rows={6} />
  }

  if (data.error !== null && data.items.length === 0) {
    const forbidden = data.error instanceof ApiError && data.error.status === 403
    return (
      <div className="flex flex-col gap-3">
        <ErrorAlert
          title={t('entries.loadError')}
          message={
            forbidden ? t('approval.forbidden', { role: roleLabel('editor') }) : data.error.message
          }
        />
        <Button type="button" variant="outline" className="self-start" onClick={data.reload}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  }

  const remaining = total !== null ? Math.max(0, total - data.items.length) : null
  const limitReached = data.items.length >= ENTRIES_LOADED_LIMIT
  const confirmAll = !readOnly && filters.health === 'unconfirmed' && total !== null && total > 0

  return (
    <div ref={listRef} className="flex min-w-0 flex-col gap-4 pb-28 md:pb-20">
      <KindIntro filters={filters} onFilter={onFilter} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium" aria-live="polite" data-testid="entries-result-count">
          {total !== null ? t('entries.resultCount', { count: total, formatted: format.format(total) }) : ''}
        </p>
        {confirmAll ? (
          <FilterConfirmDialog
            filters={filters}
            count={total}
            onDone={(results) => applyBatchResult('confirm', results)}
          />
        ) : null}
      </div>

      {data.error !== null ? <ErrorAlert message={data.error.message} /> : null}

      {partialBanner !== null ? (
        <div tabIndex={-1} ref={(node) => node?.focus()}>
          <AttentionBanner
            icon={TriangleAlert}
            title={t(`batch.partialBanner.${partialBanner.action}`, {
              count: partialBanner.failed,
            })}
            actions={
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setPartialBanner(null)}
              >
                {t('common:actions.close')}
              </Button>
            }
          />
        </div>
      ) : null}

      {data.items.length === 0 ? (
        filtered ? (
          <EmptyState
            title={t('entries.noMatch')}
            action={
              <Button type="button" variant="outline" onClick={onResetFilters}>
                {t('entries.resetFilters')}
              </Button>
            }
          />
        ) : emptyState !== undefined ? (
          emptyState
        ) : (
          <EmptyState
            title={t('entries.empty.title')}
            description={t('entries.empty.body')}
            action={
              <Button asChild variant="outline">
                <Link to={wsPath('/agents')}>{t('entries.empty.action')}</Link>
              </Button>
            }
          />
        )
      ) : (
        <ul
          className="flex flex-col divide-y rounded-lg border border-border/60 bg-card"
          data-testid="entries-list"
        >
          {data.items.map((memory) => (
            <li key={memory.id} className="min-w-0">
              <EntryRow
                memory={memory}
                agentName={fixedAgentId !== undefined ? null : agentName(memory.agent_id)}
                selected={selected.has(memory.id)}
                onToggleSelect={toggleSelect}
                failure={failures.get(memory.id) ?? null}
                onAction={rowAction}
                readOnly={readOnly}
                detailLink={detailLinks}
              />
            </li>
          ))}
        </ul>
      )}

      {limitReached ? (
        <p className="text-sm text-muted-foreground" data-testid="entries-loaded-limit">
          {t('entries.loadedLimit', { count: ENTRIES_LOADED_LIMIT })}
        </p>
      ) : data.hasMore ? (
        <Button
          type="button"
          variant="outline"
          className="min-h-11 self-start md:min-h-10"
          aria-busy={data.loadingMore}
          disabled={data.loadingMore}
          onClick={data.loadMore}
        >
          {remaining !== null && remaining > 0
            ? t('entries.loadMoreCount', { count: remaining, formatted: format.format(remaining) })
            : t('approval.loadMore')}
        </Button>
      ) : null}

      {!readOnly && selected.size > 0 ? (
        <div
          role="region"
          aria-label={t('approval.bulk.region')}
          data-testid="entries-bulk-bar"
          className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-card md:left-auto md:w-[calc(100%-15rem)]"
        >
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2">
            <div className="flex flex-col">
              <span className="text-sm font-medium" aria-live="polite">
                {t('approval.bulk.selected', { count: selected.size })}
              </span>
              {selectionHint ? (
                <span className="text-xs text-muted-foreground" role="status">
                  {t('approval.selectionLimit')}
                </span>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <BulkDeleteDialog
                count={fitting('delete').length}
                disabled={busy}
                onConfirm={() => runBatch('delete')}
              />
              {fitting('reject').length > 0 ? (
                <RejectDialog
                  triggerLabel={bulkLabel(t, 'reject', fitting('reject').length, selected.size)}
                  title={t('approval.bulk.rejectTitle', { count: fitting('reject').length })}
                  disabled={busy}
                  onReject={(note) => runBatch('reject', note === '' ? undefined : note)}
                />
              ) : null}
              {fitting('approve').length > 0 ? (
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  className={ROW_ACTION}
                  disabled={busy}
                  onClick={() => void runBatch('approve').catch(() => undefined)}
                >
                  {bulkLabel(t, 'approve', fitting('approve').length, selected.size)}
                </Button>
              ) : null}
              {fitting('confirm').length > 0 ? (
                <Button
                  type="button"
                  variant="brand"
                  size="sm"
                  className={ROW_ACTION}
                  disabled={busy}
                  onClick={() => void runBatch('confirm').catch(() => undefined)}
                >
                  {bulkLabel(t, 'confirm', fitting('confirm').length, selected.size)}
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

/** „Bestätigen (3)“ bzw. „Bestätigen (3 von 4)“, wenn nicht alle passen. */
function bulkLabel(
  t: TFunction<'learning'>,
  action: 'confirm' | 'approve' | 'reject',
  count: number,
  total: number,
): string {
  return count === total
    ? t(`entries.bulk.${action}`, { count })
    : t(`entries.bulk.${action}Of`, { count, total })
}

// ------------------------------------------------------------- KindIntro

/** Erklaersatz zur Art (Spec §6.2: der Unterschied ist der Kern). */
function KindIntro({
  filters,
  onFilter,
}: {
  filters: EntryFilters
  onFilter: (facet: EntryFacet, value: string) => void
}) {
  const { t } = useTranslation('learning')
  if (filters.kind !== '') {
    const key = filters.kind === 'user_fact' ? 'user_fact_agent' : filters.kind
    return (
      <p className="text-sm break-words text-muted-foreground" data-testid="kind-intro">
        {t(`entries.kindIntro.${key}`)}
      </p>
    )
  }
  return (
    <p
      className="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm text-muted-foreground"
      data-testid="kind-intro"
    >
      <span>{t('entries.intro')}</span>
      {(['agent_note', 'user_fact', 'lesson'] as const).map((kind, index) => (
        <span key={kind} className="inline-flex items-center">
          <Button
            type="button"
            variant="link"
            size="sm"
            className="h-auto min-h-11 px-0 py-0 md:min-h-0"
            onClick={() => onFilter('kind', kind)}
          >
            {kind === 'user_fact' ? t('kind.user_fact_agent') : t(`kind.${kind}`)}
          </Button>
          {index < 2 ? <span aria-hidden="true">,&nbsp;</span> : null}
        </span>
      ))}
    </p>
  )
}

// -------------------------------------------------------- BulkDeleteDialog

function BulkDeleteDialog({
  count,
  disabled,
  onConfirm,
}: {
  count: number
  disabled: boolean
  onConfirm: () => Promise<void>
}) {
  const { t } = useTranslation('learning')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await onConfirm()
      setOpen(false)
    } catch {
      // Toast kam vom Aufrufer; der Dialog bleibt fuer einen Neuversuch offen.
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          // `text-destructive` liest `--destructive-text` (globals.css, Audit A6)
          // = das Text-Token aus Spec §6.5; `text-destructive-text` gibt es nicht.
          className={cn(ROW_ACTION, 'text-destructive')}
          disabled={disabled}
        >
          {t('entries.bulk.delete')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('entries.bulk.deleteTitle', { count })}</DialogTitle>
          <DialogDescription>{t('entries.bulk.deleteBody')}</DialogDescription>
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
            {t('entries.bulk.deleteSubmit', { count })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------ FilterConfirmDialog

/**
 * „Alle {{count}} bestätigen“ bei Zustand „Unbestätigt“: Filter-Stapel mit
 * `expected_count`. Weicht die Serverzahl ab (409
 * `memory_batch_count_mismatch`), bleibt der Dialog offen und nennt die neue
 * Zahl — bestaetigt wird nie mehr, als die Person gesehen hat.
 */
function FilterConfirmDialog({
  filters,
  count,
  onDone,
}: {
  filters: EntryFilters
  count: number
  onDone: (results: MemoryBatchItemResult[]) => void
}) {
  const { t } = useTranslation('learning')
  const api = useApi()
  const [open, setOpen] = useState(false)
  const [expected, setExpected] = useState(count)
  const [changed, setChanged] = useState(false)
  const [busy, setBusy] = useState(false)

  const openDialog = (next: boolean) => {
    if (next) {
      setExpected(count)
      setChanged(false)
    }
    setOpen(next)
  }

  const submit = async () => {
    setBusy(true)
    try {
      const result = await api.batchMemories({
        action: 'confirm',
        filter: memoryFilterOf(filters),
        expected_count: expected,
      })
      setOpen(false)
      onDone(result.results)
    } catch (cause: unknown) {
      const mismatch = countMismatchOf(cause)
      if (mismatch !== null) {
        setExpected(mismatch)
        setChanged(true)
      } else {
        notify.error(t('batch.failedAll'))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={openDialog}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm" className={ROW_ACTION}>
          {t('entries.confirmAll', { count })}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('entries.confirmAllTitle', { count: expected })}</DialogTitle>
          <DialogDescription>{t('entries.confirmAllBody')}</DialogDescription>
        </DialogHeader>
        {changed ? (
          <p className="text-sm font-medium" role="status" data-testid="count-changed">
            {t('approval.countChanged', { count: expected })}
          </p>
        ) : null}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="default"
            disabled={busy || expected === 0}
            onClick={() => void submit()}
          >
            {t('entries.confirmAllSubmit', { count: expected })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
