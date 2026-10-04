import { ChevronDown, History, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useInRouterContext, useSearchParams } from 'react-router-dom'

import type { MemoryProposalRead, MemoryRead } from '@/api/types'
import { ExpandableText } from '@/components/data/ExpandableText'
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

// Zeilen der Warteschlange „Zur Freigabe“ (Spec S1′, Gedaechtnisverwaltung §5).
// Freitext (Fakt, Begruendung, Vorschlag) ist immer ein Textknoten — nie HTML
// oder Markdown (ADR-0038) — und bricht mit `break-words` um.

// Zeilenaktionen: Floor 32 px ab md, 40 px darunter (Spec §15 „Zielgroesse“).
const ROW_ACTION = 'min-h-10 md:min-h-0'

// Sichtbarer Fokus, wenn eine Zeile selbst per Kuerzel fokussiert wird (2.4.7).
const QUEUE_ROW_FOCUS =
  'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset'

// ---------------------------------------------------------------- HoldReason

export type HoldCause = 'external' | 'instruction' | 'inferred'

/**
 * Grund des Zurueckhaltens, aus den Daten abgeleitet (PM-F1 = a, kein
 * `hold_reasons[]` in der API). Reihenfolge bei mehreren Ursachen:
 * fremder Inhalt, dann Anweisung, dann abgeleitet (Spec §5.2).
 */
export function holdCauseOf(memory: MemoryRead): HoldCause | null {
  if (memory.status !== 'pending') return null
  if (memory.origin === 'external_content') return 'external'
  if (memory.category === 'instruction') return 'instruction'
  if (memory.origin === 'inferred') return 'inferred'
  return null
}

/** Kopf einer zurueckgehaltenen Zeile: Warn-Icon + Wort + Erklaerung. */
export function HoldReason({ cause }: { cause: HoldCause }) {
  const { t } = useTranslation('learning')
  return (
    <div className="flex flex-col gap-1" data-testid="hold-reason">
      <p className="flex items-start gap-2 text-sm font-medium">
        <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <span className="break-words">{t(`approval.hold.${cause}`)}</span>
      </p>
      <p className="text-sm break-words text-muted-foreground">
        <span className="font-medium">{t('approval.whyHere')} </span>
        {t(`approval.hold.${cause}Why`)}
      </p>
    </div>
  )
}

// --------------------------------------------------------------- RejectDialog

interface RejectDialogProps {
  onReject: (note: string) => Promise<void>
  triggerLabel: string
  title: string
  disabled?: boolean
}

/** Ablehnen mit optionaler Notiz; sagt, dass Abgelehntes Dedup-Basis bleibt. */
export function RejectDialog({ onReject, triggerLabel, title, disabled }: RejectDialogProps) {
  const { t } = useTranslation('learning')
  const noteId = useId()
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const confirm = async () => {
    setBusy(true)
    try {
      await onReject(note.trim())
      setOpen(false)
      setNote('')
    } catch {
      // Der Aufrufer meldet den Fehler; der Dialog bleibt fuer einen Neuversuch offen.
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
          className={ROW_ACTION}
          disabled={disabled}
          data-row-action="reject"
        >
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{t('approval.rejectKeepsDedup')}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1">
          <Label htmlFor={noteId}>{t('approval.rejectNote')}</Label>
          <Textarea
            id={noteId}
            rows={3}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              {t('common:actions.cancel')}
            </Button>
          </DialogClose>
          <Button type="button" variant="destructive" disabled={busy} onClick={() => void confirm()}>
            {t('approval.reject')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ MemoryRow

export interface MemoryRowProps {
  memory: MemoryRead
  agentName: string | null
  // Darf die Person entscheiden? Sonst nur lesen, Aktionen ausgeblendet.
  canAct: boolean
  // Checkbox nur fuer nicht zurueckgehaltene neue Eintraege.
  selectable: boolean
  selected: boolean
  onToggleSelect: (id: string) => void
  // Grund eines fehlgeschlagenen Stapels bzw. einer Einzelaktion, inline.
  failure: string | null
  onApprove: (memory: MemoryRead, fact: string) => Promise<void>
  onReject: (memory: MemoryRead, note: string) => Promise<void>
}

function shorten(text: string, max = 60): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`
}

/**
 * Ein neuer Eintrag in der Warteschlange. Zurueckgehaltene sind immer offen,
 * tragen ihren Grund und keine Checkbox (Stapel-Freigabe ist fuer sie
 * gesperrt, Spec §5.2). Normale Zeilen sind einzeilig und klappen per Knopf
 * am Fakt auf. Ein Lernvorschlag (`lesson`) kann nie `active` werden — er hat
 * deshalb kein „Freigeben“ (DB-CHECK, Delta S1).
 */
export function MemoryRow({
  memory,
  agentName,
  canAct,
  selectable,
  selected,
  onToggleSelect,
  failure,
  onApprove,
  onReject,
}: MemoryRowProps) {
  const { t, i18n } = useTranslation('learning')
  // Ausserhalb eines Routers (isolierte Tests) gibt es kein Detail-Sheet.
  const inRouter = useInRouterContext()
  const detailsId = useId()
  const factId = useId()
  const cause = holdCauseOf(memory)
  const held = cause !== null
  const [open, setOpen] = useState(held)
  const [fact, setFact] = useState(memory.fact)
  const [busy, setBusy] = useState(false)
  const isLesson = memory.kind === 'lesson'
  const expanded = held || open

  const approve = async () => {
    setBusy(true)
    try {
      await onApprove(memory, fact.trim())
    } finally {
      setBusy(false)
    }
  }

  const kindLabel = t(`kind.${memory.kind ?? 'agent_note'}`)
  const originLabel = t('origin.perAgent', {
    origin: t(`origin.${memory.origin ?? 'legacy_unknown'}`),
  })
  const created = new Date(memory.created_at).toLocaleString(i18n.language, {
    dateStyle: 'short',
    timeStyle: 'short',
  })

  return (
    <div
      data-testid={held ? 'memory-held-row' : 'memory-row'}
      // Anker der Tastaturkuerzel (j/k/x/a/r/e/h, ApprovalQueue); ohne eigenen
      // Fokus-Knopf (zurueckgehaltene Zeile) nimmt die Zeile selbst den Fokus.
      data-queue-row={memory.id}
      tabIndex={-1}
      className={cn(
        QUEUE_ROW_FOCUS,
        'flex flex-col gap-3 p-4',
        held && 'rounded-lg border border-border/60 bg-card shadow-card',
      )}
    >
      {held ? <HoldReason cause={cause} /> : null}
      <div className="flex min-w-0 items-start gap-3">
        {selectable && canAct ? (
          <Checkbox
            className="mt-1"
            checked={selected}
            onChange={() => onToggleSelect(memory.id)}
            aria-label={t('approval.selectRow', { fact: shorten(memory.fact) })}
          />
        ) : null}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {held ? (
            <ExpandableText text={memory.fact} className="text-sm font-medium break-words" />
          ) : (
            <Button
              type="button"
              variant="ghost"
              data-queue-focus
              aria-expanded={open}
              aria-controls={detailsId}
              onClick={() => setOpen((value) => !value)}
              className="h-auto min-h-10 w-full items-start justify-start gap-2 px-1 py-1 text-left text-sm font-medium whitespace-normal md:min-h-0"
            >
              <span className="min-w-0 flex-1 break-words">{memory.fact}</span>
              <ChevronDown
                aria-hidden="true"
                className={cn('mt-0.5 size-4 shrink-0', open && 'rotate-180')}
              />
            </Button>
          )}
          <p className="text-xs break-words text-muted-foreground">
            {kindLabel} · {originLabel}
            {agentName !== null ? ` · ${agentName}` : ''}
          </p>
        </div>
      </div>

      {expanded ? (
        <div id={detailsId} className="flex flex-col gap-3">
          {canAct && !isLesson ? (
            <div className="flex flex-col gap-1">
              <Label htmlFor={factId} className="text-xs text-muted-foreground">
                {t('approval.factLabel')}
              </Label>
              <Textarea
                id={factId}
                rows={2}
                value={fact}
                disabled={busy}
                onChange={(event) => setFact(event.target.value)}
                className="max-h-[60svh]"
                data-queue-edit
              />
            </div>
          ) : null}
          {memory.context !== null && memory.context !== '' ? (
            <p className="text-sm break-words text-muted-foreground">
              <span className="font-medium">{t('approval.agentReason')}: </span>
              {memory.context}
            </p>
          ) : null}
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">{t('approval.channel')}</dt>
            <dd className="break-words">{t(`channel.${memory.source}`)}</dd>
            <dt className="text-muted-foreground">{t('approval.category')}</dt>
            <dd>{t(`agents:memory.category.${memory.category}`)}</dd>
            <dt className="text-muted-foreground">{t('approval.created')}</dt>
            <dd>{created}</dd>
          </dl>
          {failure !== null ? <RowFailure message={failure} /> : null}
          {canAct || inRouter ? (
            <div className="flex flex-wrap justify-end gap-2">
              {inRouter ? <HistoryButton memory={memory} /> : null}
              {canAct ? (
                <RejectDialog
                  triggerLabel={t('approval.reject')}
                  title={t('approval.rejectTitle')}
                  disabled={busy}
                  onReject={(note) => onReject(memory, note)}
                />
              ) : null}
              {!canAct || isLesson ? null : (
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  className={ROW_ACTION}
                  disabled={busy || fact.trim() === ''}
                  data-row-action="approve"
                  onClick={() => void approve()}
                >
                  {t('approval.approve')}
                </Button>
              )}
            </div>
          ) : null}
        </div>
      ) : failure !== null ? (
        <RowFailure message={failure} />
      ) : null}
    </div>
  )
}

// --------------------------------------------------------- Detail-Sheet-Link

/** Router-State, mit dem eine Liste dem Detail-Sheet den Eintrag mitgibt. */
export interface MemoryEntryState {
  memory: MemoryRead
}

/**
 * Ziel des Detail-Sheets (Spec §7, `?entry=<id>`): aktuelle Parameter
 * bleiben, `entry` kommt dazu. Der Eintrag reist im Router-State mit, damit
 * das Sheet ihn ohne Suchlauf sofort zeigt (es gibt kein `GET` je Eintrag).
 */
export function useEntryLink(memory: MemoryRead) {
  const [params] = useSearchParams()
  const next = new URLSearchParams(params)
  next.set('entry', memory.id)
  const state: MemoryEntryState = { memory }
  return { to: { search: `?${next.toString()}` }, state }
}

/** „Verlauf“ in der aufgeklappten Zeile der Warteschlange (S1′). */
function HistoryButton({ memory }: { memory: MemoryRead }) {
  const { t } = useTranslation('learning')
  const link = useEntryLink(memory)
  return (
    <Button asChild variant="ghost" size="sm" className={ROW_ACTION}>
      <Link {...link} data-testid="open-history" data-row-action="history" aria-haspopup="dialog">
        <History aria-hidden="true" />
        {t('approval.history')}
      </Link>
    </Button>
  )
}

function RowFailure({ message }: { message: string }) {
  return (
    <p
      className="flex items-start gap-2 text-sm break-words text-destructive"
      data-testid="row-failure"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      {message}
    </p>
  )
}

// ---------------------------------------------------------------- ProposalRow

type DiffToken = { text: string; op: 'same' | 'added' | 'removed' }

/**
 * Wort-Diff (LCS ueber Woerter und Leerraum); Fakten sind kurz (≤ 300 Zeichen).
 *
 * Danach werden Aenderungsstrecken zusammengefasst: Leerraum, der zwischen
 * zwei geaenderten Woertern als „gleich“ erkannt wurde, gehoert zur Strecke.
 * Jede Strecke erscheint als ein entfernter Block, dann ein hinzugefuegter —
 * sonst verschraenken sich alte und neue Woerter („Frauseit Schmidt.Oktober“).
 */
export function wordDiff(before: string, after: string): DiffToken[] {
  const a = before.split(/(\s+)/).filter((token) => token !== '')
  const b = after.split(/(\s+)/).filter((token) => token !== '')
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () =>
    new Array<number>(b.length + 1).fill(0),
  )
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1])
    }
  }
  const out: DiffToken[] = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ text: a[i], op: 'same' })
      i++
      j++
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.push({ text: a[i++], op: 'removed' })
    } else {
      out.push({ text: b[j++], op: 'added' })
    }
  }
  while (i < a.length) out.push({ text: a[i++], op: 'removed' })
  while (j < b.length) out.push({ text: b[j++], op: 'added' })
  return groupChanges(out)
}

const WHITESPACE = /^\s+$/

function groupChanges(tokens: DiffToken[]): DiffToken[] {
  const result: DiffToken[] = []
  let k = 0
  while (k < tokens.length) {
    if (tokens[k].op === 'same') {
      result.push(tokens[k++])
      continue
    }
    // Strecke: Aenderungen plus Leerraum dazwischen, solange danach noch
    // eine Aenderung folgt.
    let removed = ''
    let added = ''
    while (k < tokens.length) {
      const token = tokens[k]
      if (token.op === 'removed') removed += token.text
      else if (token.op === 'added') added += token.text
      else {
        let next = k
        while (next < tokens.length && tokens[next].op === 'same' && WHITESPACE.test(tokens[next].text)) next++
        if (next === k || next >= tokens.length || tokens[next].op === 'same') break
        const gap = tokens.slice(k, next).map((t) => t.text).join('')
        if (removed !== '') removed += gap
        if (added !== '') added += gap
        k = next
        continue
      }
      k++
    }
    if (removed !== '') result.push({ text: removed.trimEnd(), op: 'removed' })
    if (removed !== '' && added !== '') result.push({ text: ' ', op: 'same' })
    if (added !== '') result.push({ text: added.trimEnd(), op: 'added' })
  }
  return result
}

export interface ProposalRowProps {
  proposal: MemoryProposalRead
  currentFact: string | null
  agentName: string | null
  canAct: boolean
  failure: string | null
  onDecide: (proposal: MemoryProposalRead, accept: boolean, note?: string) => Promise<void>
}

/**
 * Aenderungs- oder Loeschvorschlag eines Agenten (ADR-0053 3.1.4). Ohne
 * Checkbox: jeder Diff soll gelesen werden, entschieden wird per `decide`,
 * nie automatisch (4.2). Der Diff traegt Durch- bzw. Unterstreichung, damit
 * die Farbe nicht allein spricht, plus eine `sr-only`-Fassung.
 */
export function ProposalRow({
  proposal,
  currentFact,
  agentName,
  canAct,
  failure,
  onDecide,
}: ProposalRowProps) {
  const { t } = useTranslation('learning')
  const [busy, setBusy] = useState(false)
  const isChange = proposal.action === 'change'

  const accept = async () => {
    setBusy(true)
    try {
      await onDecide(proposal, true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      data-testid="memory-proposal-row"
      data-queue-row={proposal.id}
      tabIndex={-1}
      className={cn(QUEUE_ROW_FOCUS, 'flex flex-col gap-3 p-4')}
    >
      <p className="text-xs font-medium text-muted-foreground">
        {isChange ? t('approval.proposal.change') : t('approval.proposal.delete')}
        {agentName !== null ? ` · ${agentName}` : ''}
      </p>
      {isChange ? (
        <ChangeDiff before={currentFact} after={proposal.new_fact ?? ''} />
      ) : (
        <p className="text-sm break-words line-through" data-testid="proposal-delete-fact">
          {currentFact ?? t('approval.proposal.unknownFact')}
        </p>
      )}
      <p className="text-sm break-words text-muted-foreground">
        <span className="font-medium">{t('approval.agentReason')}: </span>
        {proposal.reason}
      </p>
      {failure !== null ? <RowFailure message={failure} /> : null}
      {canAct ? (
        <div className="flex flex-wrap justify-end gap-2">
          <RejectDialog
            triggerLabel={t('approval.reject')}
            title={t('approval.proposal.rejectTitle')}
            disabled={busy}
            onReject={(note) => onDecide(proposal, false, note === '' ? undefined : note)}
          />
          <Button
            type="button"
            variant="default"
            size="sm"
            className={ROW_ACTION}
            disabled={busy}
            data-queue-focus
            onClick={() => void accept()}
          >
            {isChange ? t('approval.applyChange') : t('approval.applyDelete')}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

export function ChangeDiff({ before, after }: { before: string | null; after: string }) {
  const { t } = useTranslation('learning')
  if (before === null) {
    return <p className="text-sm break-words">{after}</p>
  }
  return (
    <p className="text-sm break-words whitespace-pre-wrap" data-testid="proposal-diff">
      <span className="sr-only">
        {t('approval.proposal.srDiff', { before, after })}
      </span>
      <span aria-hidden="true">
        {wordDiff(before, after).map((token, index) =>
          token.op === 'same' ? (
            <span key={index}>{token.text}</span>
          ) : token.op === 'removed' ? (
            <del key={index} className="bg-diff-removed text-diff-removed-fg line-through">
              {token.text}
            </del>
          ) : (
            <ins key={index} className="bg-diff-added text-diff-added-fg underline">
              {token.text}
            </ins>
          ),
        )}
      </span>
    </p>
  )
}
