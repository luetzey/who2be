import { MoreHorizontal, Trash2, TriangleAlert } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import type { Member, MemoryEventRead, MemoryRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useSession } from '@/auth/session-context'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { StatusLine } from '@/components/memory/MemoryList'
import { MemoryHistory } from '@/components/memory/MemoryHistory'
import { HoldReason, RejectDialog, holdCauseOf } from '@/components/memory/MemoryRow'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useAgents } from '@/hooks/useAgents'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import {
  apiReason,
  useReasonText,
  visibleToMe,
} from '@/features/memory/hooks/useMemoryApi'

// Detail-Sheet eines Gedaechtniseintrags (Gedaechtnisverwaltung S3′, §7,
// §13.5, §14, §15; ADR-0053 3.1.2/3.1.3). Geoeffnet ueber `?entry=<id>`.
// Freitext bleibt Textknoten (ADR-0038) und bricht mit `break-words`.

const ACTION = 'min-h-11 md:min-h-9'

type Owner = string | null

/** Besitzer-Pfad: eigenes Nutzergedaechtnis (`null`) oder Agent. */
function ownerOf(memory: MemoryRead): Owner {
  return memory.scope === 'user' ? null : (memory.agent_id ?? '')
}

function isGone(cause: unknown): boolean {
  return (
    apiReason(cause).reason === 'memory_not_found' ||
    (cause instanceof ApiError && cause.status === 404)
  )
}

export interface MemoryDetailSheetProps {
  // `?entry=` — `null` schliesst das Sheet.
  entryId: string | null
  // Aus der Liste mitgegeben (Router-State); spart den Suchlauf.
  initial: MemoryRead | null
  onClose: () => void
  // Nach jeder Aenderung (Liste und Zaehler neu laden).
  onChanged: () => void
  // Fokusziel beim Schliessen, wenn der Ausloeser fehlt (Deep-Link, Loeschen).
  fallbackFocus: () => HTMLElement | null
}

export function MemoryDetailSheet({
  entryId,
  initial,
  onClose,
  onChanged,
  fallbackFocus,
}: MemoryDetailSheetProps) {
  const mobile = useIsMobile()
  const titleRef = useRef<HTMLHeadingElement>(null)
  const returnFocus = useRef<HTMLElement | null>(null)
  const open = entryId !== null

  // Ausloeser merken, solange er noch den Fokus hat (Link in der Zeile).
  // Layout-Effekt: laeuft vor Radix' Fokus-Effekt, der den Fokus ins Sheet holt.
  useLayoutEffect(() => {
    if (!open) return
    const active = document.activeElement
    returnFocus.current = active instanceof HTMLElement && active !== document.body ? active : null
  }, [open])

  return (
    <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent
        side={mobile ? 'bottom' : 'right'}
        data-testid="memory-detail-sheet"
        className={cn(
          'gap-0 overflow-y-auto overscroll-contain p-0',
          mobile ? 'h-[100svh] rounded-none' : 'w-full sm:max-w-lg',
        )}
        onOpenAutoFocus={(event) => {
          // Fokus auf den Titel, nicht auf den ersten Knopf (Spec §15).
          event.preventDefault()
          titleRef.current?.focus()
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          const target = returnFocus.current
          if (target !== null && target.isConnected) target.focus()
          else fallbackFocus()?.focus()
        }}
      >
        {entryId !== null ? (
          <DetailBody
            key={entryId}
            entryId={entryId}
            initial={initial !== null && initial.id === entryId ? initial : null}
            titleRef={titleRef}
            onClose={onClose}
            onChanged={onChanged}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

interface DetailBodyProps {
  entryId: string
  initial: MemoryRead | null
  titleRef: RefObject<HTMLHeadingElement>
  onClose: () => void
  onChanged: () => void
}

function DetailBody({ entryId, initial, titleRef, onClose, onChanged }: DetailBodyProps) {
  const { t } = useTranslation('learning')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const { me } = useSession()
  const userId = me?.user_id ?? null
  const canManageAgents = role !== null && role !== 'viewer'
  const reasonText = useReasonText()
  const { agents } = useAgents()
  const descriptionId = useId()

  const [memory, setMemory] = useState<MemoryRead | null>(
    initial !== null && visibleToMe(initial, userId) ? initial : null,
  )
  const [missing, setMissing] = useState(false)
  // Netz-/Serverfehler beim Deep-Link — nicht dasselbe wie „nicht gefunden“.
  const [loadError, setLoadError] = useState<string | null>(null)
  const [events, setEvents] = useState<MemoryEventRead[] | null>(null)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyNonce, setHistoryNonce] = useState(0)
  const [members, setMembers] = useState<Member[]>([])
  const [busy, setBusy] = useState(false)

  // Deep-Link: Einzelabruf. Unsichtbares beantwortet der Server mit 404 wie
  // eine unbekannte ID; `visibleToMe` verwirft fremdes Nutzergedaechtnis
  // trotzdem (3.1.1). Nur 404 heisst „nicht gefunden“, alles andere ist ein
  // Ladefehler mit Retry.
  useEffect(() => {
    if (memory !== null || missing || loadError !== null) return
    let cancelled = false
    api
      .getMemory(entryId)
      .then((hit) => {
        if (cancelled) return
        if (visibleToMe(hit, userId)) setMemory(hit)
        else setMissing(true)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        if (isGone(cause)) setMissing(true)
        else setLoadError(cause instanceof Error ? cause.message : String(cause))
      })
    return () => {
      cancelled = true
    }
  }, [api, entryId, memory, missing, loadError, userId])

  const memoryId = memory?.id ?? null
  const owner = memory !== null ? ownerOf(memory) : undefined

  // Verlauf laden, sobald der Eintrag (und damit sein Besitzer) bekannt ist.
  useEffect(() => {
    if (memoryId === null || owner === undefined) return
    let cancelled = false
    api
      .getMemoryHistory(owner, memoryId)
      .then((rows) => {
        if (cancelled) return
        setEvents(rows)
        setHistoryError(null)
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        if (isGone(cause)) {
          setMemory(null)
          setMissing(true)
          return
        }
        setHistoryError(cause instanceof Error ? cause.message : String(cause))
      })
    return () => {
      cancelled = true
    }
  }, [api, memoryId, owner, historyNonce])

  // Namen nur laden, wenn ein anderer Mensch im Verlauf steht.
  const needsMembers =
    events?.some((event) => event.actor_kind === 'human' && event.actor_id !== userId) ?? false
  useEffect(() => {
    if (!needsMembers) return
    let cancelled = false
    api
      .listMembers()
      .then((rows) => {
        if (!cancelled) setMembers(rows)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [api, needsMembers])

  const fail = useCallback(
    (cause: unknown) => {
      if (isGone(cause)) {
        notify.info(t('entries.gone'))
        setMemory(null)
        setMissing(true)
        onChanged()
        return
      }
      const { reason, params } = apiReason(cause)
      notify.error(
        reason !== null ? reasonText(reason, params) : t('batch.failedAll'),
      )
    },
    [onChanged, reasonText, t],
  )

  // Eine Aenderung: Ergebnis uebernehmen, Verlauf und Liste neu laden.
  const mutate = async (
    run: () => Promise<MemoryRead>,
    done: string,
    rethrow = false,
  ): Promise<void> => {
    setBusy(true)
    try {
      const next = await run()
      setMemory(next)
      setHistoryNonce((value) => value + 1)
      notify.success(done)
      onChanged()
    } catch (cause: unknown) {
      fail(cause)
      if (rethrow) throw cause
    } finally {
      setBusy(false)
    }
  }

  if (memory === null) {
    const failed = loadError !== null
    return (
      <>
        <SheetHeader className="sticky top-0 z-10 border-b bg-background p-4 pr-12 text-left">
          <SheetTitle ref={titleRef} tabIndex={-1} className="outline-none">
            {t('detail.title')}
          </SheetTitle>
          <SheetDescription
            id={descriptionId}
            className={missing || failed ? undefined : 'sr-only'}
          >
            {missing
              ? t('detail.notVisible')
              : failed
                ? t('detail.loadError')
                : t('detail.loading')}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 p-4">
          {missing ? (
            <Button type="button" variant="outline" className="self-start" onClick={onClose}>
              {t('common:actions.close')}
            </Button>
          ) : failed ? (
            <div className="flex flex-col gap-3" data-testid="detail-load-error">
              <ErrorAlert title={t('detail.loadError')} message={loadError} />
              <Button
                type="button"
                variant="outline"
                className="self-start"
                onClick={() => setLoadError(null)}
              >
                {t('common:actions.retry')}
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-3" aria-busy="true" data-testid="detail-loading">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}
        </div>
      </>
    )
  }

  const own = memory.scope === 'user'
  // Eigenes Nutzergedaechtnis darf die Person selbst (ab viewer), Agenten-
  // gedaechtnis ab editor (Spec §7). Fremdes ist oben schon ausgeschlossen.
  const canAct = own ? userId !== null : canManageAgents
  const ownerKey = ownerOf(memory)
  const lesson = memory.kind === 'lesson'
  const cause = holdCauseOf(memory)

  const triage = (action: 'approve' | 'reject', note?: string) =>
    mutate(
      () =>
        ownerKey === null
          ? api.triageMyMemory(memory.id, { action, note })
          : api.triageAgentMemory(ownerKey, memory.id, { action, note }),
      t(action === 'approve' ? 'entries.done.approve' : 'detail.done.reject'),
      true,
    )

  return (
    <>
      <SheetHeader className="sticky top-0 z-10 gap-2 border-b bg-background p-4 pr-12 text-left">
        <SheetTitle ref={titleRef} tabIndex={-1} className="outline-none">
          {t('detail.title')}
        </SheetTitle>
        <SheetDescription
          id={descriptionId}
          className="text-base font-medium break-words whitespace-pre-wrap text-foreground"
          data-testid="detail-fact"
        >
          {memory.fact}
        </SheetDescription>
        <StatusLine memory={memory} />
      </SheetHeader>

      <div className="flex min-w-0 flex-col gap-6 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
        {cause !== null ? <HoldReason cause={cause} /> : null}

        {canAct ? (
          <DetailActions
            memory={memory}
            busy={busy}
            lesson={lesson}
            onApprove={() => triage('approve').catch(() => undefined)}
            onReject={(note) => triage('reject', note === '' ? undefined : note)}
            onConfirm={() =>
              mutate(() => api.confirmMemory(ownerKey, memory.id), t('entries.done.confirm'))
            }
            onReactivate={() =>
              mutate(() => api.reactivateMemory(ownerKey, memory.id), t('entries.done.reactivate'))
            }
            onSave={(fact) =>
              mutate(
                () =>
                  ownerKey === null
                    ? api.updateMyMemory(memory.id, { fact })
                    : api.updateAgentMemory(ownerKey, memory.id, { fact }),
                t('detail.done.edit'),
                true,
              )
            }
            onDelete={async () => {
              setBusy(true)
              try {
                if (ownerKey === null) await api.deleteMyMemory(memory.id)
                else await api.deleteAgentMemory(ownerKey, memory.id)
                notify.success(t('detail.done.delete'))
                onChanged()
                onClose()
              } catch (cause: unknown) {
                fail(cause)
                throw cause
              } finally {
                setBusy(false)
              }
            }}
          />
        ) : null}

        <Provenance memory={memory} agentName={agentNameOf(agents, memory)} />
        <Delivery memory={memory} />

        <section aria-labelledby={`${descriptionId}-history`} className="flex flex-col gap-3">
          <h3 id={`${descriptionId}-history`} className="text-sm font-semibold">
            {t('history.title')}
          </h3>
          <MemoryHistory
            memory={memory}
            events={events}
            loading={events === null}
            error={historyError}
            onRetry={() => {
              setHistoryError(null)
              setHistoryNonce((value) => value + 1)
            }}
            onRestore={
              canAct
                ? (event) =>
                    mutate(
                      () => api.rollbackMemory(ownerKey, memory.id, { event_id: event.id }),
                      t('history.restored'),
                      true,
                    )
                : null
            }
            agents={agents}
            members={members}
            userId={userId}
          />
        </section>
      </div>
    </>
  )
}

function agentNameOf(agents: { id: string; name: string }[], memory: MemoryRead): string | null {
  const id = memory.agent_id ?? memory.created_by_agent_id ?? null
  return id !== null ? (agents.find((agent) => agent.id === id)?.name ?? null) : null
}

// ------------------------------------------------------------------ Aktionen

interface DetailActionsProps {
  memory: MemoryRead
  busy: boolean
  lesson: boolean
  onApprove: () => void
  onReject: (note: string) => Promise<void>
  onConfirm: () => void
  onReactivate: () => void
  onSave: (fact: string) => Promise<void>
  onDelete: () => Promise<void>
}

/**
 * Aktionen je Status (Spec §7): `pending` → Freigeben/Ablehnen (Lernvorschlag
 * nur Ablehnen), aktiv unbestaetigt → Bestaetigen, `expired` → Wieder
 * aktivieren. Bearbeiten bei allen ausser `lesson` und `rejected`; Loeschen
 * immer, im Menue „Weitere Aktionen“.
 */
function DetailActions({
  memory,
  busy,
  lesson,
  onApprove,
  onReject,
  onConfirm,
  onReactivate,
  onSave,
  onDelete,
}: DetailActionsProps) {
  const { t } = useTranslation('learning')
  const factId = useId()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(memory.fact)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const editRef = useRef<HTMLButtonElement>(null)
  const canEdit = !lesson && memory.status !== 'rejected'
  const unconfirmed = memory.status === 'active' && !memory.confirmed_at && !lesson

  // Fokus folgt dem Modus: ins Textfeld beim Bearbeiten, danach zurueck auf
  // „Bearbeiten“ (kein `autoFocus`, jsx-a11y).
  const wasEditing = useRef(false)
  useEffect(() => {
    if (editing) textareaRef.current?.focus()
    else if (wasEditing.current) editRef.current?.focus()
    wasEditing.current = editing
  }, [editing])

  if (editing) {
    const trimmed = draft.trim()
    return (
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (trimmed === '' || trimmed === memory.fact) return
          onSave(trimmed)
            .then(() => setEditing(false))
            .catch(() => undefined)
        }}
      >
        <Label htmlFor={factId}>{t('approval.factLabel')}</Label>
        <Textarea
          id={factId}
          rows={3}
          value={draft}
          disabled={busy}
          ref={textareaRef}
          onChange={(event) => setDraft(event.target.value)}
          className="max-h-[60svh]"
        />
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            className={ACTION}
            disabled={busy}
            onClick={() => {
              setDraft(memory.fact)
              setEditing(false)
            }}
          >
            {t('common:actions.cancel')}
          </Button>
          <Button
            type="submit"
            className={ACTION}
            disabled={busy || trimmed === '' || trimmed === memory.fact}
          >
            {t('common:actions.save')}
          </Button>
        </div>
      </form>
    )
  }

  return (
    <div className="flex flex-wrap gap-2" data-testid="detail-actions">
      {memory.status === 'pending' && !lesson ? (
        <Button type="button" className={ACTION} disabled={busy} onClick={onApprove}>
          {t('approval.approve')}
        </Button>
      ) : null}
      {memory.status === 'pending' ? (
        <RejectDialog
          triggerLabel={t('approval.reject')}
          title={t('approval.rejectTitle')}
          disabled={busy}
          onReject={onReject}
        />
      ) : null}
      {unconfirmed ? (
        <Button type="button" variant="outline" className={ACTION} disabled={busy} onClick={onConfirm}>
          {t('entries.action.confirm')}
        </Button>
      ) : null}
      {memory.status === 'expired' && !lesson ? (
        <Button
          type="button"
          variant="outline"
          className={ACTION}
          disabled={busy}
          onClick={onReactivate}
        >
          {t('entries.action.reactivate')}
        </Button>
      ) : null}
      {canEdit ? (
        <Button
          type="button"
          variant="ghost"
          className={ACTION}
          disabled={busy}
          ref={editRef}
          data-testid="detail-edit"
          onClick={() => {
            setDraft(memory.fact)
            setEditing(true)
          }}
        >
          {t('common:actions.edit')}
        </Button>
      ) : null}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-11 md:size-9"
            disabled={busy}
            aria-label={t('detail.moreActions')}
            data-testid="detail-more"
          >
            <MoreHorizontal aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem className="text-destructive" onSelect={() => setDeleteOpen(true)}>
            <Trash2 aria-hidden="true" />
            {t('detail.delete')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('detail.deleteTitle')}</DialogTitle>
            <DialogDescription>{t('detail.deleteBody')}</DialogDescription>
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
              data-testid="detail-delete-submit"
              onClick={() => void onDelete().catch(() => undefined)}
            >
              {t('detail.deleteSubmit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// --------------------------------------------------------- Herkunft/Auslieferung

function Provenance({ memory, agentName }: { memory: MemoryRead; agentName: string | null }) {
  const { t, i18n } = useTranslation('learning')
  const origin = memory.origin ?? 'legacy_unknown'
  const risky = origin === 'external_content' || origin === 'inferred'
  const kind = memory.kind ?? 'agent_note'
  const channel =
    memory.source === 'agent' && agentName !== null
      ? `${t('channel.agent')} ${agentName}`
      : t(`channel.${memory.source}`)
  const created = new Date(memory.created_at).toLocaleString(i18n.language, {
    dateStyle: 'short',
    timeStyle: 'short',
  })
  return (
    <section className="flex flex-col gap-2" aria-labelledby={`provenance-${memory.id}`}>
      <h3 id={`provenance-${memory.id}`} className="text-sm font-semibold">
        {t('detail.provenance')}
      </h3>
      {/* minmax(0,1fr) + wrap-anywhere: lange URLs/Namen ohne Leerzeichen
          duerfen die Wertspalte nicht ueber den Sheet-Rand schieben (1fr hat
          min-content als Untergrenze, break-words senkt die nicht). */}
      <dl
        className="grid grid-cols-1 gap-x-3 gap-y-1 text-sm sm:grid-cols-[auto_minmax(0,1fr)]"
        data-testid="detail-provenance"
      >
        <dt className="text-muted-foreground">{t('detail.channel')}</dt>
        <dd className="min-w-0 wrap-anywhere">{t('detail.channelServer', { channel })}</dd>
        <dt className="text-muted-foreground">{t('detail.perAgent')}</dt>
        <dd className="flex min-w-0 items-start gap-1.5 wrap-anywhere" data-testid="detail-origin">
          {risky ? <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> : null}
          {t(`origin.${origin}`)}
        </dd>
        {memory.context !== null && memory.context !== '' ? (
          <>
            <dt className="text-muted-foreground">{t('detail.reason')}</dt>
            <dd className="min-w-0 wrap-anywhere whitespace-pre-wrap">{memory.context}</dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">{t('detail.kindScope')}</dt>
        <dd className="min-w-0 wrap-anywhere">
          {t(`kind.${kind}`)} · {t(`detail.scope.${memory.scope === 'user' ? 'user' : 'agent'}`)}
        </dd>
        <dt className="text-muted-foreground">{t('detail.category')}</dt>
        <dd className="min-w-0 wrap-anywhere">
          {t(`agents:memory.category.${memory.category}`)} ·{' '}
          {t('detail.importance', { value: memory.importance })}
        </dd>
        <dt className="text-muted-foreground">{t('detail.created')}</dt>
        <dd className="min-w-0">
          <time dateTime={memory.created_at}>{created}</time>
        </dd>
      </dl>
    </section>
  )
}

function Delivery({ memory }: { memory: MemoryRead }) {
  const { t, i18n } = useTranslation('learning')
  const last = memory.last_retrieved_at
  return (
    <section className="flex flex-col gap-2" aria-labelledby={`delivery-${memory.id}`}>
      <h3 id={`delivery-${memory.id}`} className="text-sm font-semibold">
        {t('detail.delivery')}
      </h3>
      <p className="text-sm" data-testid="detail-delivery">
        {memory.retrieval_count > 0 && last !== null
          ? t('detail.deliveredLast', {
              count: memory.retrieval_count,
              when: new Date(last).toLocaleString(i18n.language, {
                dateStyle: 'short',
                timeStyle: 'short',
              }),
            })
          : t('detail.neverDelivered')}
      </p>
    </section>
  )
}
