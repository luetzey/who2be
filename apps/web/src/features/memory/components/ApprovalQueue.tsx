import { TriangleAlert } from 'lucide-react'
import { useCallback, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type { MemoryBatchItemResult, MemoryProposalRead, MemoryRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { MemoryRow, ProposalRow, RejectDialog, holdCauseOf } from '@/components/memory/MemoryRow'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'

import {
  HELD_LOAD_LIMIT,
  MINE_GROUP,
  SELECTION_LIMIT,
  countMismatchOf,
  failuresOf,
  groupKeyOf,
  useApprovalQueue,
  type ProposalWithTarget,
} from '../hooks/useMemoryApi'

interface ApprovalQueueProps {
  q: string
  agentId: string
  onShowAgent: (agentId: string) => void
  onResetFilters: () => void
}

interface Group {
  key: string
  label: string
  items: MemoryRead[]
  proposals: ProposalWithTarget[]
  // Server-Zaehler der nicht zurueckgehaltenen neuen Eintraege der Gruppe.
  total: number
}

const PREVIEW_COUNT = 5

/** Grund je Zeile (Spec §9). */
function useReasonText() {
  const { t } = useTranslation('learning')
  return useCallback(
    (reason: string | null | undefined, params?: Record<string, unknown> | null): string => {
      const name = typeof params?.decided_by_name === 'string' ? params.decided_by_name : null
      switch (reason) {
        case 'memory_not_found':
          return t('batch.reason.memory_not_found')
        case 'memory_not_pending':
        case 'memory_proposal_not_pending':
          return name !== null
            ? t('approval.alreadyDecidedBy', { name })
            : t('approval.alreadyDecided')
        case 'memory_cap_reached':
          return params?.scope === 'user'
            ? t('approval.capReachedUser', { maximum: params.maximum ?? 500 })
            : t('batch.reason.memory_cap_reached')
        case 'memory_note_cap_reached':
          return t('approval.capReachedNote')
        case 'memory_held':
          return t('batch.reason.memory_held')
        case 'forbidden':
          return t('batch.reason.forbidden')
        default:
          return t('batch.reason.other', { code: reason ?? '?' })
      }
    },
    [t],
  )
}

function apiReason(cause: unknown): { reason: string | null; params: Record<string, unknown> | null } {
  if (!(cause instanceof ApiError)) return { reason: null, params: null }
  const body = cause.body as { reason?: unknown; params?: unknown } | null
  return {
    reason: typeof body?.reason === 'string' ? body.reason : null,
    params:
      body?.params !== null && typeof body?.params === 'object'
        ? (body.params as Record<string, unknown>)
        : null,
  }
}

/**
 * S1′ „Zur Freigabe“ (Gedaechtnisverwaltung §5): zurueckgehaltene oben,
 * einzeln; dann „Dein Nutzergedaechtnis“ und je Agent ein Block mit
 * „Alle von <Agent> freigeben“; Aenderungs- und Loeschvorschlaege am Ende
 * ihres Blocks. Stapel laufen ueber `POST /memories/batch`, Vorschlaege
 * ueber `decide`. Viewer sehen nur ihr eigenes Nutzergedaechtnis.
 */
export function ApprovalQueue({ q, agentId, onShowAgent, onResetFilters }: ApprovalQueueProps) {
  const { t, i18n } = useTranslation('learning')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const wsPath = useWorkspacePath()
  const data = useApprovalQueue({ q, agentId })
  const reasonText = useReasonText()
  const listRef = useRef<HTMLDivElement>(null)

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [failures, setFailures] = useState<Map<string, string>>(new Map())
  const [partialBanner, setPartialBanner] = useState<{
    failed: number
    action: 'approve' | 'reject'
  } | null>(null)
  const [selectionHint, setSelectionHint] = useState(false)
  const [busy, setBusy] = useState(false)
  const [groupDialog, setGroupDialog] = useState<Group | null>(null)

  const formatNumber = useMemo(() => new Intl.NumberFormat(i18n.language), [i18n.language])
  const agentName = useCallback(
    (id: string | null | undefined): string | null =>
      id ? (data.agents.find((agent) => agent.id === id)?.name ?? null) : null,
    [data.agents],
  )

  // Fokus nach einer Aktion: naechste Zeile, sonst Gruppenkopf/Leerzustand
  // (Spec §9 Punkt 1). Ein Mikrotask spaeter, damit die Liste neu steht.
  const focusNext = useCallback(() => {
    window.setTimeout(() => {
      const root = listRef.current
      const target =
        root?.querySelector<HTMLElement>('[data-queue-focus]') ??
        root?.querySelector<HTMLElement>('h2, h3') ??
        null
      target?.focus()
    }, 0)
  }, [])

  const groups = useMemo<Group[]>(() => {
    const byKey = new Map<string, Group>()
    const ensure = (key: string): Group => {
      let group = byKey.get(key)
      if (group === undefined) {
        group = {
          key,
          label: key === MINE_GROUP ? t('approval.groupMine') : (agentName(key) ?? key),
          items: [],
          proposals: [],
          total: data.groupCounts[key] ?? 0,
        }
        byKey.set(key, group)
      }
      return group
    }
    for (const memory of data.items) ensure(groupKeyOf(memory)).items.push(memory)
    for (const entry of data.proposals) {
      // Vorschlaege zum Nutzergedaechtnis kommen nur zur Person selbst.
      const key = entry.proposal.agent_id
      const ownTarget = !data.agents.some((agent) => agent.id === key) || !data.canManageAgents
      ensure(ownTarget ? MINE_GROUP : key).proposals.push(entry)
    }
    const mine = byKey.get(MINE_GROUP)
    const agentGroups = [...byKey.values()]
      .filter((group) => group.key !== MINE_GROUP)
      .sort(
        (a, b) =>
          b.total + b.proposals.length - (a.total + a.proposals.length) ||
          a.label.localeCompare(b.label, i18n.language),
      )
    return mine !== undefined ? [mine, ...agentGroups] : agentGroups
  }, [data.items, data.proposals, data.groupCounts, data.agents, data.canManageAgents, agentName, t, i18n.language])

  const canActOn = useCallback(
    (memory: MemoryRead) => (memory.scope === 'user' ? true : data.canManageAgents),
    [data.canManageAgents],
  )

  const removeFromSelection = (ids: string[]) =>
    setSelected((current) => {
      const next = new Set(current)
      for (const id of ids) next.delete(id)
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

  const setFailure = (id: string, message: string | null) =>
    setFailures((current) => {
      const next = new Map(current)
      if (message === null) next.delete(id)
      else next.set(id, message)
      return next
    })

  // ------------------------------------------------------------ Einzelaktionen

  const triage = async (memory: MemoryRead, action: 'approve' | 'reject', payload: string) => {
    const input =
      action === 'approve'
        ? { action, fact: payload !== memory.fact ? payload : undefined }
        : { action, note: payload === '' ? undefined : payload }
    try {
      if (memory.scope === 'user') {
        await api.triageMyMemory(memory.id, input)
      } else {
        await api.triageAgentMemory(memory.agent_id ?? '', memory.id, input)
      }
      setFailure(memory.id, null)
      removeFromSelection([memory.id])
      notify.success(t(action === 'approve' ? 'batch.done.approve' : 'batch.done.reject', { count: 1 }))
      data.reload()
      focusNext()
    } catch (cause: unknown) {
      const { reason, params } = apiReason(cause)
      if (reason === 'memory_not_pending' || reason === 'memory_not_found') {
        notify.info(reasonText(reason, params))
        data.reload()
        return
      }
      setFailure(memory.id, reason !== null ? reasonText(reason, params) : (cause as Error).message)
      notify.error(t('batch.failedAll'))
      throw cause
    }
  }

  const decide = async (proposal: MemoryProposalRead, accept: boolean, note?: string) => {
    try {
      await api.decideMemoryProposal(proposal.id, { accept, note })
      setFailure(proposal.id, null)
      notify.success(t(accept ? 'approval.proposal.accepted' : 'approval.proposal.rejected'))
      data.reload()
      focusNext()
    } catch (cause: unknown) {
      const { reason, params } = apiReason(cause)
      if (reason === 'memory_proposal_not_pending') {
        notify.info(t('proposal.alreadyDecided'))
        data.reload()
        return
      }
      setFailure(proposal.id, reason !== null ? reasonText(reason, params) : (cause as Error).message)
      notify.error(t('batch.failedAll'))
      throw cause
    }
  }

  // ----------------------------------------------------------------- Stapel

  const applyBatchResult = (action: 'approve' | 'reject', results: MemoryBatchItemResult[]) => {
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
    if (failed.size === 0) {
      notify.success(t(`batch.done.${action}`, { count: ok }))
      setPartialBanner(null)
    } else {
      notify.info(t(`batch.partial.${action}`, { ok, failed: failed.size }))
      setPartialBanner({ failed: failed.size, action })
    }
    data.reload()
  }

  const runSelectionBatch = async (action: 'approve' | 'reject', note?: string) => {
    const ids = [...selected]
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

  // ------------------------------------------------------------- Rendering

  const heldHidden = Math.max(0, (data.heldTotal ?? 0) - data.held.length)
  const nothing = data.held.length === 0 && data.items.length === 0 && data.proposals.length === 0
  const filtered = q !== '' || agentId !== ''

  if (data.loading && nothing) {
    return <LoadingState rows={5} />
  }

  if (data.error !== null && nothing) {
    const forbidden = data.error instanceof ApiError && data.error.status === 403
    return (
      <div className="flex flex-col gap-3">
        <ErrorAlert
          title={t('approval.loadError')}
          message={forbidden ? t('approval.forbidden', { role: roleLabel('editor') }) : data.error.message}
        />
        <Button type="button" variant="outline" className="self-start" onClick={data.reload}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  }

  if (nothing) {
    if (filtered) {
      return (
        <EmptyState
          title={t('approval.noMatch')}
          action={
            <Button type="button" variant="outline" onClick={onResetFilters}>
              {t('approval.resetFilters')}
            </Button>
          }
        />
      )
    }
    if (!data.canManageAgents) {
      return (
        <EmptyState
          title={t('approval.emptyViewer.title')}
          description={t('approval.emptyViewer.body')}
        />
      )
    }
    const allOff =
      data.agents.length > 0 &&
      data.agents.every((agent) => (agent.tool_policy.memory_mode ?? 'off') === 'off')
    if (allOff) {
      return (
        <EmptyState
          title={t('approval.emptyAllOff.title')}
          description={t('approval.emptyAllOff.body')}
          action={
            <Button asChild variant="outline">
              <Link to={wsPath('/agents')}>{t('approval.emptyAllOff.action')}</Link>
            </Button>
          }
        />
      )
    }
    return (
      <EmptyState
        title={t('approval.emptyViewer.title')}
        description={t('approval.emptyEditor.body')}
        action={
          role === 'admin' ? (
            <Button asChild variant="outline">
              <Link to={wsPath('/settings/workspace#memory-approval')}>
                {t('approval.emptyEditor.action')}
              </Link>
            </Button>
          ) : undefined
        }
      />
    )
  }

  return (
    <div ref={listRef} className="flex flex-col gap-6 pb-28 md:pb-20">
      {data.error !== null ? <ErrorAlert message={data.error.message} /> : null}

      {partialBanner !== null ? (
        <div tabIndex={-1} ref={(node) => node?.focus()}>
          <AttentionBanner
            icon={TriangleAlert}
            title={t(`batch.partialBanner.${partialBanner.action}`, { count: partialBanner.failed })}
            actions={
              <Button type="button" variant="outline" size="sm" onClick={() => setPartialBanner(null)}>
                {t('common:actions.close')}
              </Button>
            }
          />
        </div>
      ) : null}

      {data.held.length > 0 ? (
        <section aria-labelledby="queue-held" className="flex flex-col gap-3">
          <h3 id="queue-held" tabIndex={-1} className="text-xs font-semibold tracking-wide uppercase">
            {t('approval.heldBackTitle')} ({formatNumber.format(data.heldTotal ?? data.held.length)})
          </h3>
          <ul className="flex flex-col gap-3">
            {data.held.map((memory) => (
              <li key={memory.id}>
                <MemoryRow
                  memory={memory}
                  agentName={agentName(memory.agent_id ?? memory.created_by_agent_id)}
                  canAct={canActOn(memory)}
                  selectable={false}
                  selected={false}
                  onToggleSelect={toggleSelect}
                  failure={failures.get(memory.id) ?? null}
                  onApprove={(m, fact) => triage(m, 'approve', fact)}
                  onReject={(m, note) => triage(m, 'reject', note)}
                />
              </li>
            ))}
          </ul>
          {heldHidden > 0 && data.held.length >= HELD_LOAD_LIMIT ? (
            <p className="text-sm text-muted-foreground">
              {t('approval.moreHeld', { count: heldHidden })}
            </p>
          ) : null}
        </section>
      ) : null}

      {groups.map((group) => {
        const headingId = `queue-group-${group.key}`
        const loaded = group.items.length
        const hidden = Math.max(0, group.total - loaded)
        const canGroupApprove =
          group.total > 0 && (group.key === MINE_GROUP || data.canManageAgents)
        return (
          <section key={group.key} aria-labelledby={headingId} className="flex flex-col gap-2">
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <h3
                id={headingId}
                tabIndex={-1}
                className="text-xs font-semibold tracking-wide break-words uppercase"
              >
                {group.label} ({formatNumber.format(group.total + group.proposals.length)})
              </h3>
              {canGroupApprove ? (
                <div className="flex flex-col gap-1 md:items-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-10 w-full md:min-h-0 md:w-auto"
                    aria-label={
                      group.key === MINE_GROUP
                        ? t('approval.groupApproveMine', { count: group.total })
                        : t('approval.groupApproveAgentAria', { count: group.total, agent: group.label })
                    }
                    onClick={() => setGroupDialog(group)}
                  >
                    {group.key === MINE_GROUP
                      ? t('approval.groupApproveMine', { count: group.total })
                      : t('approval.groupApproveAgent', { count: group.total, agent: group.label })}
                  </Button>
                  <p className="text-xs text-muted-foreground">{t('approval.groupExcludes')}</p>
                </div>
              ) : null}
            </div>
            <ul className="divide-y rounded-lg border border-border/40 bg-card shadow-card">
              {group.items.map((memory) => (
                <li key={memory.id}>
                  <MemoryRow
                    memory={memory}
                    agentName={
                      group.key === MINE_GROUP
                        ? agentName(memory.created_by_agent_id)
                        : null
                    }
                    canAct={canActOn(memory)}
                    selectable={holdCauseOf(memory) === null && memory.kind !== 'lesson'}
                    selected={selected.has(memory.id)}
                    onToggleSelect={toggleSelect}
                    failure={failures.get(memory.id) ?? null}
                    onApprove={(m, fact) => triage(m, 'approve', fact)}
                    onReject={(m, note) => triage(m, 'reject', note)}
                  />
                </li>
              ))}
              {group.proposals.map((entry) => (
                <li key={entry.proposal.id}>
                  <ProposalRow
                    proposal={entry.proposal}
                    currentFact={entry.currentFact}
                    agentName={group.key === MINE_GROUP ? agentName(entry.proposal.agent_id) : null}
                    canAct
                    failure={failures.get(entry.proposal.id) ?? null}
                    onDecide={decide}
                  />
                </li>
              ))}
            </ul>
            {hidden > 0 && group.key !== MINE_GROUP && agentId === '' ? (
              <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                {t('approval.moreInGroup', { count: hidden, agent: group.label })}
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0"
                  onClick={() => onShowAgent(group.key)}
                >
                  {t('approval.onlyAgent', { agent: group.label })}
                </Button>
              </p>
            ) : null}
          </section>
        )
      })}

      {data.hasMore ? (
        <Button
          type="button"
          variant="outline"
          className="self-start"
          aria-busy={data.loadingMore}
          disabled={data.loadingMore}
          onClick={data.loadMore}
        >
          {t('approval.loadMore')}
        </Button>
      ) : null}

      {selected.size > 0 ? (
        <div
          role="region"
          aria-label={t('approval.bulk.region')}
          className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-card md:left-auto md:w-[calc(100%-16rem)]"
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
              <RejectDialog
                triggerLabel={t('approval.bulk.reject')}
                title={t('approval.bulk.rejectTitle', { count: selected.size })}
                disabled={busy}
                onReject={(note) => runSelectionBatch('reject', note === '' ? undefined : note)}
              />
              <Button
                type="button"
                variant="brand"
                size="sm"
                className="min-h-10 md:min-h-0"
                disabled={busy}
                onClick={() => void runSelectionBatch('approve').catch(() => undefined)}
              >
                {t('approval.bulk.approve', { count: selected.size })}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {groupDialog !== null ? (
        <GroupApproveDialog
          group={groupDialog}
          agentId={groupDialog.key === MINE_GROUP ? null : groupDialog.key}
          q={q}
          onClose={() => setGroupDialog(null)}
          onDone={(results) => {
            setGroupDialog(null)
            applyBatchResult('approve', results)
            focusNext()
          }}
        />
      ) : null}
    </div>
  )
}

interface GroupApproveDialogProps {
  group: Group
  agentId: string | null
  q: string
  onClose: () => void
  onDone: (results: MemoryBatchItemResult[]) => void
}

/**
 * „Alle von <Agent> freigeben“ (Spec §5.2): Filter-Stapel mit
 * `expected_count`. Weicht die Serverzahl ab (409
 * `memory_batch_count_mismatch`), bleibt der Dialog offen und nennt die neue
 * Zahl — es wird nie mehr freigegeben, als die Person bestaetigt hat.
 */
function GroupApproveDialog({ group, agentId, q, onClose, onDone }: GroupApproveDialogProps) {
  const { t } = useTranslation('learning')
  const api = useApi()
  const [expected, setExpected] = useState(group.total)
  const [changed, setChanged] = useState(false)
  const [busy, setBusy] = useState(false)
  const mine = agentId === null

  const submit = async () => {
    setBusy(true)
    try {
      const result = await api.batchMemories({
        action: 'approve',
        filter: {
          status: 'pending',
          held: false,
          kind: mine ? 'user_fact' : undefined,
          scope: mine ? 'user' : 'agent',
          agent_id: agentId ?? undefined,
          q: q !== '' ? q : undefined,
        },
        expected_count: expected,
      })
      onDone(result.results)
    } catch (cause: unknown) {
      const count = countMismatchOf(cause)
      if (count !== null) {
        setExpected(count)
        setChanged(true)
      } else {
        notify.error(t('batch.failedAll'))
      }
    } finally {
      setBusy(false)
    }
  }

  const preview = group.items.slice(0, PREVIEW_COUNT)
  const rest = Math.max(0, expected - preview.length)

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {mine
              ? t('approval.groupConfirm.titleMine', { count: expected })
              : t('approval.groupConfirm.title', { count: expected, agent: group.label })}
          </DialogTitle>
          <DialogDescription>{t('approval.groupConfirm.body')}</DialogDescription>
        </DialogHeader>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm">
          {preview.map((memory) => (
            <li key={memory.id} className="break-words">
              {memory.fact}
            </li>
          ))}
        </ul>
        {rest > 0 ? (
          <p className="text-sm text-muted-foreground">
            {t('approval.groupConfirm.more', { count: rest })}
          </p>
        ) : null}
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
            {t('approval.groupConfirm.submit', { count: expected })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
