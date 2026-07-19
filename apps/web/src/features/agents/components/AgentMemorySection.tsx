import { ChevronDown, Trash2 } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { MemoryRead, MemoryUpdateInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
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
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import { useAgentMemories } from '../hooks/useAgentMemories'

const IMPORTANCE_LEVELS = Array.from({ length: 10 }, (_, index) => index + 1)

interface AgentMemorySectionProps {
  agentId: string
}

/** Kategorie- + Wichtigkeits-Pills — von Triage-, Aktiv- und Rejected-Zeile geteilt. */
function MemoryPills({ memory }: { memory: MemoryRead }) {
  const { t } = useTranslation('agents')
  return (
    <div className="flex flex-wrap gap-2">
      <Badge variant="secondary">{t(`memory.category.${memory.category}`)}</Badge>
      <Badge variant="outline">{t('memory.importance', { value: memory.importance })}</Badge>
    </div>
  )
}

interface ConfirmDeleteButtonProps {
  triggerLabel: string
  ariaLabel: string
  dialogTitle: string
  dialogDescription: string
  confirmLabel: string
  successMessage: string
  errorMessage: string
  onConfirm: () => Promise<void>
  variant?: 'ghost' | 'outline'
}

/**
 * Loesch-Bestaetigungs-Dialog (lokales, generalisiertes Pendant zu
 * `DeleteFeedbackButton` — hier fuer Einzel- UND "Alle löschen" genutzt, daher
 * alle Texte als Props statt fest verdrahteter Feedback-i18n-Keys).
 */
function ConfirmDeleteButton({
  triggerLabel,
  ariaLabel,
  dialogTitle,
  dialogDescription,
  confirmLabel,
  successMessage,
  errorMessage,
  onConfirm,
  variant = 'ghost',
}: ConfirmDeleteButtonProps) {
  const { t } = useTranslation('agents')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const onDelete = async () => {
    setBusy(true)
    try {
      await onConfirm()
      notify.success(successMessage)
      setOpen(false)
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : errorMessage)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant={variant}
          size="sm"
          aria-label={ariaLabel}
          className={variant === 'ghost' ? 'h-8 text-xs text-destructive hover:text-destructive' : undefined}
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={busy} onClick={() => void onDelete()}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Ablehnen-Dialog mit optionalem Notiz-Feld (Freigeben braucht keinen Dialog). */
function RejectMemoryDialog({
  onReject,
}: {
  onReject: (note: string) => Promise<void>
}) {
  const { t } = useTranslation('agents')
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const onConfirm = async () => {
    setBusy(true)
    try {
      await onReject(note.trim())
      setOpen(false)
      setNote('')
    } catch {
      // Fehler wurde bereits vom Aufrufer als Toast gemeldet — Dialog offen
      // lassen, damit erneut versucht werden kann.
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          {t('memory.triage.reject')}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('memory.triage.rejectDialogTitle')}</DialogTitle>
          <DialogDescription>{t('memory.triage.rejectDialogDescription')}</DialogDescription>
        </DialogHeader>
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="font-medium">{t('memory.triage.rejectNoteLabel')}</span>
          <Textarea
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t('memory.triage.rejectNotePlaceholder')}
            className="w-full"
          />
        </Label>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={busy} onClick={() => void onConfirm()}>
            {t('memory.triage.rejectConfirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface PendingMemoryRowProps {
  memory: MemoryRead
  canWrite: boolean
  onApprove: (id: string, fact: string) => Promise<void>
  onReject: (id: string, note: string) => Promise<void>
}

function PendingMemoryRow({ memory, canWrite, onApprove, onReject }: PendingMemoryRowProps) {
  const { t } = useTranslation('agents')
  const [fact, setFact] = useState(memory.fact)
  const [busy, setBusy] = useState(false)

  const handleApprove = async () => {
    setBusy(true)
    try {
      await onApprove(memory.id, fact.trim())
      notify.success(t('memory.triage.approveSuccess'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('memory.triage.error'))
    } finally {
      setBusy(false)
    }
  }

  const handleReject = async (note: string) => {
    try {
      await onReject(memory.id, note)
      notify.success(t('memory.triage.rejectSuccess'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('memory.triage.error'))
      throw cause
    }
  }

  return (
    <div
      data-testid="memory-pending-row"
      className="flex flex-col gap-3 rounded-lg border border-border/40 bg-card p-4 shadow-card"
    >
      <div className="flex flex-col gap-1">
        <Label
          htmlFor={`memory-pending-fact-${memory.id}`}
          className="text-xs font-medium text-muted-foreground"
        >
          {t('memory.triage.factLabel')}
        </Label>
        <Input
          id={`memory-pending-fact-${memory.id}`}
          value={fact}
          onChange={(event) => setFact(event.target.value)}
          disabled={!canWrite || busy}
        />
      </div>
      {memory.context !== null && memory.context !== '' ? (
        <p className="text-sm text-muted-foreground italic">
          <span className="font-medium not-italic">{t('memory.triage.contextLabel')}: </span>
          {memory.context}
        </p>
      ) : null}
      <MemoryPills memory={memory} />
      {canWrite ? (
        <div className="flex flex-wrap justify-end gap-2">
          <RejectMemoryDialog onReject={handleReject} />
          <Button type="button" variant="brand" size="sm" disabled={busy} onClick={() => void handleApprove()}>
            {t('memory.triage.approve')}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

interface ActiveMemoryRowProps {
  memory: MemoryRead
  canWrite: boolean
  onUpdate: (id: string, input: MemoryUpdateInput) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

function ActiveMemoryRow({ memory, canWrite, onUpdate, onDelete }: ActiveMemoryRowProps) {
  const { t } = useTranslation('agents')
  const [editing, setEditing] = useState(false)
  const [fact, setFact] = useState(memory.fact)
  const [importance, setImportance] = useState(memory.importance)
  const [busy, setBusy] = useState(false)

  const startEdit = () => {
    setFact(memory.fact)
    setImportance(memory.importance)
    setEditing(true)
  }

  const saveEdit = async () => {
    setBusy(true)
    try {
      await onUpdate(memory.id, { fact: fact.trim(), importance })
      notify.success(t('memory.active.updateSuccess'))
      setEditing(false)
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('memory.active.updateError'))
    } finally {
      setBusy(false)
    }
  }

  const usage =
    memory.retrieval_count === 0 || memory.last_retrieved_at === null
      ? t('memory.active.usageNever')
      : t('memory.active.usage', { count: memory.retrieval_count, date: memory.last_retrieved_at })

  if (editing) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <Label
            htmlFor={`memory-active-fact-${memory.id}`}
            className="text-xs font-medium text-muted-foreground"
          >
            {t('memory.active.factLabel')}
          </Label>
          <Input
            id={`memory-active-fact-${memory.id}`}
            value={fact}
            onChange={(event) => setFact(event.target.value)}
            disabled={busy}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label
            htmlFor={`memory-active-importance-${memory.id}`}
            className="text-xs font-medium text-muted-foreground"
          >
            {t('memory.active.importanceLabel')}
          </Label>
          <Select
            id={`memory-active-importance-${memory.id}`}
            value={String(importance)}
            onChange={(event) => setImportance(Number(event.target.value))}
            disabled={busy}
            className="w-24"
          >
            {IMPORTANCE_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => setEditing(false)}>
            {t('memory.active.cancel')}
          </Button>
          <Button type="button" variant="brand" size="sm" disabled={busy} onClick={() => void saveEdit()}>
            {t('memory.active.save')}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <Stack gap="xs">
        <p className="text-sm font-medium">{memory.fact}</p>
        <MemoryPills memory={memory} />
        <p className="text-xs text-muted-foreground">{usage}</p>
      </Stack>
      {canWrite ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={startEdit}>
            {t('memory.active.edit')}
          </Button>
          <ConfirmDeleteButton
            triggerLabel={t('memory.delete.label')}
            ariaLabel={t('memory.delete.ariaLabel')}
            dialogTitle={t('memory.delete.dialogTitle')}
            dialogDescription={t('memory.delete.dialogDescription')}
            confirmLabel={t('memory.delete.confirmLabel')}
            successMessage={t('memory.delete.success')}
            errorMessage={t('memory.delete.error')}
            onConfirm={() => onDelete(memory.id)}
          />
        </div>
      ) : null}
    </div>
  )
}

interface RejectedMemoryRowProps {
  memory: MemoryRead
  canWrite: boolean
  onDelete: (id: string) => Promise<void>
}

function RejectedMemoryRow({ memory, canWrite, onDelete }: RejectedMemoryRowProps) {
  const { t } = useTranslation('agents')
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <Stack gap="xs">
        <p className="text-sm">{memory.fact}</p>
        <MemoryPills memory={memory} />
        <p className="text-xs text-muted-foreground">
          {memory.triage_note !== null && memory.triage_note !== ''
            ? `${t('memory.rejected.noteLabel')}: ${memory.triage_note}`
            : t('memory.rejected.noNote')}
        </p>
      </Stack>
      {canWrite ? (
        <ConfirmDeleteButton
          triggerLabel={t('memory.delete.label')}
          ariaLabel={t('memory.delete.ariaLabel')}
          dialogTitle={t('memory.delete.dialogTitle')}
          dialogDescription={t('memory.delete.dialogDescription')}
          confirmLabel={t('memory.delete.confirmLabel')}
          successMessage={t('memory.delete.success')}
          errorMessage={t('memory.delete.error')}
          onConfirm={() => onDelete(memory.id)}
        />
      ) : null}
    </div>
  )
}

/**
 * Gedächtnis-Sektion am Agenten (ADR-0044): Triage-Block fuer pending-
 * Vorschläge (Fakt inline editierbar vor Freigabe, `context` nur als
 * Triage-Hilfe sichtbar), aktive Liste (Fakt/Kategorie/Wichtigkeit,
 * Nutzungs-Log, Inline-Edit, Einzel-Löschen) und eine eingeklappte
 * Rejected-Liste (Notiz + endgültiges Löschen). editor+-gated: Viewer sehen
 * alles, Mutations-Aktionen sind ausgeblendet — das Backend erzwingt die
 * Rolle zusätzlich (403).
 */
export function AgentMemorySection({ agentId }: AgentMemorySectionProps) {
  const { t } = useTranslation('agents')
  const api = useApi()
  const { memories, loading, error, reload } = useAgentMemories(agentId)
  const role = useCurrentWorkspaceRole()
  const canWrite = role !== null && role !== 'viewer'
  const [showRejected, setShowRejected] = useState(false)

  const pending = memories.filter((memory) => memory.status === 'pending')
  const active = memories.filter((memory) => memory.status === 'active')
  const rejected = memories.filter((memory) => memory.status === 'rejected')

  const approveMemory = async (id: string, fact: string) => {
    await api.triageAgentMemory(agentId, id, { action: 'approve', fact })
    reload()
  }
  const rejectMemory = async (id: string, note: string) => {
    await api.triageAgentMemory(agentId, id, {
      action: 'reject',
      note: note === '' ? undefined : note,
    })
    reload()
  }
  const updateMemory = async (id: string, input: MemoryUpdateInput) => {
    await api.updateAgentMemory(agentId, id, input)
    reload()
  }
  const deleteMemory = async (id: string) => {
    await api.deleteAgentMemory(agentId, id)
    reload()
  }
  const deleteAllMemories = async () => {
    await api.deleteAllAgentMemories(agentId)
    reload()
  }

  const isEmpty = !loading && error === null && memories.length === 0

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CardTitle>{t('memory.title')}</CardTitle>
            {pending.length > 0 ? (
              <Badge variant="secondary" data-testid="memory-pending-badge">
                {t('memory.pendingBadge', { count: pending.length })}
              </Badge>
            ) : null}
          </div>
          {canWrite && memories.length > 0 ? (
            <ConfirmDeleteButton
              variant="outline"
              triggerLabel={t('memory.deleteAll.label')}
              ariaLabel={t('memory.deleteAll.label')}
              dialogTitle={t('memory.deleteAll.dialogTitle')}
              dialogDescription={t('memory.deleteAll.dialogDescription')}
              confirmLabel={t('memory.deleteAll.confirmLabel')}
              successMessage={t('memory.deleteAll.success')}
              errorMessage={t('memory.deleteAll.error')}
              onConfirm={deleteAllMemories}
            />
          ) : null}
        </div>
        <CardDescription>{t('memory.description')}</CardDescription>
      </CardHeader>
      <CardContent>
        <DataView
          loading={loading}
          error={error}
          empty={isEmpty}
          emptyTitle={t('memory.empty.title')}
          emptyDescription={t('memory.empty.description')}
        >
          <Stack gap="lg">
            {pending.length > 0 ? (
              <div className="flex flex-col gap-3">
                <h3 className="text-sm font-semibold">{t('memory.triage.title')}</h3>
                <div className="flex flex-col gap-3">
                  {pending.map((memory) => (
                    <PendingMemoryRow
                      key={memory.id}
                      memory={memory}
                      canWrite={canWrite}
                      onApprove={approveMemory}
                      onReject={rejectMemory}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-semibold">{t('memory.active.title')}</h3>
              <DataList
                items={active}
                getKey={(memory) => memory.id}
                renderItem={(memory): ReactNode => (
                  <ActiveMemoryRow
                    memory={memory}
                    canWrite={canWrite}
                    onUpdate={updateMemory}
                    onDelete={deleteMemory}
                  />
                )}
                empty={<EmptyState title={t('memory.active.emptyTitle')} />}
              />
            </div>

            {rejected.length > 0 ? (
              <div className="flex flex-col gap-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="self-start"
                  aria-expanded={showRejected}
                  onClick={() => setShowRejected((value) => !value)}
                >
                  <ChevronDown
                    aria-hidden="true"
                    className={cn(
                      'transition-transform duration-[var(--duration-fast)] ease-standard',
                      showRejected ? 'rotate-180' : '',
                    )}
                  />
                  {t('memory.rejected.toggle', { count: rejected.length })}
                </Button>
                {showRejected ? (
                  <ul className="divide-y rounded-lg border border-border/40 bg-card shadow-card">
                    {rejected.map((memory) => (
                      <li key={memory.id} className="px-4 py-3 text-sm">
                        <RejectedMemoryRow memory={memory} canWrite={canWrite} onDelete={deleteMemory} />
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </Stack>
        </DataView>
      </CardContent>
    </Card>
  )
}
