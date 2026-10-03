import { Bot } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Agent, Member, MemoryEventRead, MemoryEventSnapshot, MemoryRead } from '@/api/types'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ChangeDiff } from '@/components/memory/MemoryRow'
import { Button } from '@/components/ui/button'
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
import { Skeleton } from '@/components/ui/skeleton'

// Verlauf im Detail-Sheet (Gedaechtnisverwaltung §7, Delta S3, ADR-0053 3.1.2).
// Die API liefert die aelteste Aenderung zuerst; angezeigt wird die neueste
// zuerst als `<ol>`. Rollback stellt den Stand `before` des gewaehlten
// Ereignisses her und schreibt den Verlauf fort (append-only).

// Ab hier „Aeltere laden“ (Spec §7 „Langer Verlauf“).
export const HISTORY_PAGE = 20

// Die Felder, die ein Rollback herstellt (Repository `restore`).
const RESTORED = ['fact', 'category', 'importance', 'status'] as const

type Snapshot = Pick<MemoryRead, (typeof RESTORED)[number]>

/** Unterscheidet sich `before` vom aktuellen Stand? Sonst waere „Wiederherstellen“ tot. */
function restoresSomething(before: MemoryEventSnapshot | null, current: Snapshot): boolean {
  if (before === null) return false
  return RESTORED.some((key) => before[key] !== undefined && before[key] !== current[key])
}

// Interner Verweis des Rollbacks (`rollback_to:<event_id>`) ist keine Notiz.
function visibleReason(event: MemoryEventRead): string | null {
  if (event.reason === null || event.reason === '') return null
  if (event.event === 'rolled_back') return null
  return event.reason
}

export interface MemoryHistoryProps {
  memory: MemoryRead
  events: MemoryEventRead[] | null
  loading: boolean
  error: string | null
  onRetry: () => void
  // `null`: kein Rollback (nur lesen).
  onRestore: ((event: MemoryEventRead) => Promise<void>) | null
  agents: Agent[]
  members: Member[]
  userId: string | null
}

export function MemoryHistory({
  memory,
  events,
  loading,
  error,
  onRetry,
  onRestore,
  agents,
  members,
  userId,
}: MemoryHistoryProps) {
  const { t } = useTranslation('learning')
  const [shown, setShown] = useState(HISTORY_PAGE)
  const newestFirst = useMemo(() => (events ?? []).slice().reverse(), [events])

  if (error !== null) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorAlert title={t('history.loadError')} message={error} />
        <Button type="button" variant="outline" size="sm" className="self-start" onClick={onRetry}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  }

  if (loading && events === null) {
    return (
      <ol className="flex flex-col gap-4" aria-busy="true" data-testid="history-loading">
        {[0, 1, 2].map((index) => (
          <li key={index} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </li>
        ))}
      </ol>
    )
  }

  if (newestFirst.length === 0) {
    return <p className="text-sm text-muted-foreground">{t('history.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <ol className="flex flex-col gap-4" data-testid="history-list">
        {newestFirst.slice(0, shown).map((event) => (
          <HistoryItem
            key={event.id}
            event={event}
            memory={memory}
            onRestore={onRestore}
            agents={agents}
            members={members}
            userId={userId}
          />
        ))}
      </ol>
      {newestFirst.length > shown ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="min-h-11 self-start md:min-h-9"
          onClick={() => setShown((value) => value + HISTORY_PAGE)}
        >
          {t('history.older', { count: newestFirst.length - shown })}
        </Button>
      ) : null}
    </div>
  )
}

interface HistoryItemProps {
  event: MemoryEventRead
  memory: MemoryRead
  onRestore: MemoryHistoryProps['onRestore']
  agents: Agent[]
  members: Member[]
  userId: string | null
}

function HistoryItem({ event, memory, onRestore, agents, members, userId }: HistoryItemProps) {
  const { t, i18n } = useTranslation('learning')
  const when = new Date(event.created_at)
  const label =
    event.event === 'edited' && event.before?.status === 'pending'
      ? t('history.event.editedBeforeApproval')
      : t(`history.event.${event.event}`)
  const reason = visibleReason(event)
  const factChanged =
    event.before?.fact !== undefined &&
    event.after?.fact !== undefined &&
    event.before.fact !== event.after.fact
  const rule =
    event.event === 'auto_activated' && event.after?.kind && event.after.origin
      ? t('history.rule', {
          kind: t(`kind.${event.after.kind}`),
          origin: t(`origin.${event.after.origin}`),
        })
      : null

  return (
    <li className="flex min-w-0 flex-col gap-1 border-l-2 border-border pl-3" data-testid="history-item">
      <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 text-sm">
        <time dateTime={event.created_at} className="text-xs text-muted-foreground tabular-nums">
          {when.toLocaleString(i18n.language, { dateStyle: 'short', timeStyle: 'short' })}
        </time>
        <span className="font-medium break-words">{label}</span>
      </p>
      <p className="flex min-w-0 flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
        <Actor event={event} agents={agents} members={members} userId={userId} />
        {rule !== null ? (
          <>
            <span aria-hidden="true">·</span>
            <span className="break-words">{rule}</span>
          </>
        ) : null}
      </p>
      {reason !== null ? (
        <p className="text-xs break-words text-muted-foreground">
          {t('history.reason', { reason })}
        </p>
      ) : null}
      {factChanged ? (
        <ChangeDiff before={event.before?.fact ?? null} after={event.after?.fact ?? ''} />
      ) : null}
      {onRestore !== null && restoresSomething(event.before, memory) ? (
        <RestoreDialog event={event} memory={memory} onRestore={onRestore} />
      ) : null}
    </li>
  )
}

function Actor({
  event,
  agents,
  members,
  userId,
}: Pick<HistoryItemProps, 'event' | 'agents' | 'members' | 'userId'>) {
  const { t } = useTranslation('learning')
  if (event.actor_kind === 'system') return <span>{t('history.actor.system')}</span>
  if (event.actor_kind === 'agent') {
    const id = event.agent_id ?? event.actor_id
    const name = agents.find((agent) => agent.id === id)?.name ?? null
    return (
      <span className="inline-flex min-w-0 items-center gap-1 break-words">
        <Bot className="size-3.5 shrink-0" aria-hidden="true" />
        {name !== null ? t('history.actor.by', { name }) : t('history.actor.agentUnknown')}
      </span>
    )
  }
  if (event.actor_id !== null && event.actor_id === userId) {
    return <span>{t('history.actor.you')}</span>
  }
  const email = members.find((member) => member.user_id === event.actor_id)?.email ?? null
  return (
    <span className="break-words">
      {email ? t('history.actor.by', { name: email }) : t('history.actor.humanUnknown')}
    </span>
  )
}

/** Bestaetigung mit Diff „jetzt → danach“ inklusive Statuswechsel (Delta S3). */
function RestoreDialog({
  event,
  memory,
  onRestore,
}: {
  event: MemoryEventRead
  memory: MemoryRead
  onRestore: (event: MemoryEventRead) => Promise<void>
}) {
  const { t } = useTranslation('learning')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const before = event.before ?? {}
  const nextFact = before.fact ?? memory.fact
  const nextStatus = before.status ?? memory.status

  const submit = async () => {
    setBusy(true)
    try {
      await onRestore(event)
      setOpen(false)
    } catch {
      // Der Aufrufer meldet den Grund; der Dialog bleibt offen.
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
          className="mt-1 min-h-11 self-start text-left whitespace-normal md:min-h-0"
          data-testid="restore-before"
        >
          {t('history.restoreBefore')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('history.restoreTitle')}</DialogTitle>
          <DialogDescription>{t('history.restoreBody')}</DialogDescription>
        </DialogHeader>
        <div className="flex min-w-0 flex-col gap-2" data-testid="restore-preview">
          <ChangeDiff before={nextFact === memory.fact ? null : memory.fact} after={nextFact} />
          {nextStatus !== memory.status ? (
            <p className="text-sm break-words" data-testid="restore-status">
              {t('history.statusChange', {
                from: t(`entries.status.${memory.status}`),
                to: t(`entries.status.${nextStatus}`),
              })}
            </p>
          ) : null}
          {before.category !== undefined && before.category !== memory.category ? (
            <p className="text-sm break-words">
              {t('history.categoryChange', {
                from: t(`agents:memory.category.${memory.category}`),
                to: t(`agents:memory.category.${before.category}`),
              })}
            </p>
          ) : null}
          {before.importance !== undefined && before.importance !== memory.importance ? (
            <p className="text-sm">
              {t('history.importanceChange', { from: memory.importance, to: before.importance })}
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button type="button" disabled={busy} onClick={() => void submit()}>
            {t('history.restoreSubmit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
