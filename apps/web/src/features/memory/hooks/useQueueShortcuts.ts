import { useCallback, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { useTranslation } from 'react-i18next'

import type { MemoryRead } from '@/api/types'
import { holdCauseOf } from '@/components/memory/MemoryRow'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { notify } from '@/lib/feedback'

// Tastaturkuerzel der Warteschlange „Zur Freigabe“ (Gedaechtnisverwaltung
// §5.2 „Tastatur“ → Lernschleife-Spec S1): j/k, x, a, r, e, h, `?`. Nur
// Desktop (§14), nur bei Fokus in der Liste und abschaltbar (WCAG 2.1.4).
// Die Kuerzel loesen dieselben Knoepfe aus wie die Maus — kein zweiter
// Codepfad fuer Freigeben oder Ablehnen.

/**
 * Darf ein Eintrag in einen Stapel (Checkbox, `x`) bzw. per `a` freigegeben
 * werden? Zurueckgehaltene werden einzeln entschieden (§5.2), Lernvorschlaege
 * nie freigegeben (DB-CHECK, Delta S1). Eine Regel fuer Checkbox und Kuerzel.
 */
export function isBatchable(memory: MemoryRead): boolean {
  return holdCauseOf(memory) === null && memory.kind !== 'lesson'
}

export type QueueRow =
  | { type: 'memory'; memory: MemoryRead; canAct: boolean }
  | { type: 'proposal'; canAct: boolean }

export type QueueCommand =
  | 'next'
  | 'prev'
  | 'select'
  | 'approve'
  | 'reject'
  | 'edit'
  | 'history'
  | 'help'

const KEYS: Record<string, QueueCommand> = {
  j: 'next',
  k: 'prev',
  x: 'select',
  a: 'approve',
  r: 'reject',
  e: 'edit',
  h: 'history',
  '?': 'help',
}

/** Reihenfolge in der Hilfe. */
export const SHORTCUTS: ReadonlyArray<{ key: string; command: QueueCommand }> = Object.entries(
  KEYS,
).map(([key, command]) => ({ key, command }))

/**
 * Was ein Kuerzel auf einer Zeile tut: ausfuehren, verweigern (mit Ansage
 * „Einzeln entscheiden“) oder still ignorieren.
 */
export function resolveCommand(
  command: Exclude<QueueCommand, 'next' | 'prev' | 'help'>,
  row: QueueRow,
): 'run' | 'refuse' | 'ignore' {
  if (!row.canAct) return command === 'history' && row.type === 'memory' ? 'run' : 'ignore'
  switch (command) {
    case 'select':
    case 'approve':
      return row.type === 'memory' && isBatchable(row.memory) ? 'run' : 'refuse'
    case 'reject':
      return 'run'
    case 'edit':
      // Lernvorschlaege sind nicht bearbeitbar (Spec S3′ „Aktionen nach Status“).
      return row.type === 'memory' && row.memory.kind !== 'lesson' ? 'run' : 'ignore'
    case 'history':
      return row.type === 'memory' ? 'run' : 'ignore'
  }
}

/** Fokus in einem Feld, das selbst Text annimmt — dort wirkt kein Kuerzel. */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  if (target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) return true
  if (target instanceof HTMLInputElement) return target.type !== 'checkbox'
  return false
}

const STORAGE_KEY = 'who2be:memory-queue-shortcuts'

function readEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== 'off'
  } catch {
    return true
  }
}

/** An/Aus der Kuerzel, im Browser gemerkt (WCAG 2.1.4 „abschaltbar“). */
export function useShortcutsEnabled(): [boolean, (value: boolean) => void] {
  const [enabled, setEnabled] = useState(readEnabled)
  const update = useCallback((value: boolean) => {
    setEnabled(value)
    try {
      window.localStorage.setItem(STORAGE_KEY, value ? 'on' : 'off')
    } catch {
      // Ohne Speicher gilt die Wahl nur fuer diese Sitzung.
    }
  }, [])
  return [enabled, update]
}

interface UseQueueKeyboardOptions {
  container: HTMLElement | null
  enabled: boolean
  rowOf: (id: string) => QueueRow | undefined
  onSelect: (memory: MemoryRead) => void
  onHelp: () => void
}

/**
 * Haengt die Kuerzel an den Listen-Container: Sie wirken nur, wenn der Fokus
 * in der Liste liegt, nicht in Eingabefeldern, nicht in Dialogen und nicht
 * mit Strg/Alt/Meta. `Esc` im Faktfeld fuehrt zurueck auf die Zeile.
 */
export function useQueueKeyboard({
  container,
  enabled,
  rowOf,
  onSelect,
  onHelp,
}: UseQueueKeyboardOptions) {
  const { t } = useTranslation('learning')
  const mobile = useIsMobile()
  const latest = useRef({ rowOf, onSelect, onHelp, t })
  useEffect(() => {
    latest.current = { rowOf, onSelect, onHelp, t }
  })

  useEffect(() => {
    if (container === null || !enabled || mobile) return

    const rows = () => [...container.querySelectorAll<HTMLElement>('[data-queue-row]')]
    const focusRow = (row: HTMLElement) =>
      (row.querySelector<HTMLElement>('[data-queue-focus]') ?? row).focus()
    const expand = (row: HTMLElement) => {
      const toggle = row.querySelector<HTMLElement>('[data-queue-focus][aria-expanded="false"]')
      if (toggle !== null) flushSync(() => toggle.click())
    }
    const action = (row: HTMLElement, name: string) =>
      row.querySelector<HTMLElement>(`[data-row-action="${name}"]`)

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return
      const target = event.target as HTMLElement
      if (target.closest('[role="dialog"]') !== null) return
      const current = target.closest<HTMLElement>('[data-queue-row]')

      if (event.key === 'Escape' && target instanceof HTMLTextAreaElement && current !== null) {
        event.preventDefault()
        focusRow(current)
        return
      }
      if (isTypingTarget(target)) return
      if (!Object.hasOwn(KEYS, event.key)) return
      const command = KEYS[event.key]
      event.preventDefault()
      const { rowOf: lookup, onSelect: select, onHelp: help, t: translate } = latest.current

      if (command === 'help') {
        help()
        return
      }
      if (command === 'next' || command === 'prev') {
        const all = rows()
        if (all.length === 0) return
        const index = current === null ? -1 : all.indexOf(current)
        const next =
          command === 'next'
            ? all[index < 0 ? 0 : Math.min(index + 1, all.length - 1)]
            : all[index < 0 ? all.length - 1 : Math.max(index - 1, 0)]
        focusRow(next)
        return
      }
      if (current === null) return
      const row = lookup(current.dataset.queueRow ?? '')
      if (row === undefined) return
      const verdict = resolveCommand(command, row)
      if (verdict === 'ignore') return
      if (verdict === 'refuse') {
        notify.info(translate('approval.decideIndividually'))
        return
      }
      switch (command) {
        case 'select':
          if (row.type === 'memory') select(row.memory)
          return
        case 'approve':
          expand(current)
          action(current, 'approve')?.click()
          return
        case 'reject':
          expand(current)
          action(current, 'reject')?.click()
          return
        case 'edit':
          expand(current)
          current.querySelector<HTMLElement>('[data-queue-edit]')?.focus()
          return
        case 'history':
          expand(current)
          action(current, 'history')?.click()
          return
      }
    }

    container.addEventListener('keydown', onKeyDown)
    return () => container.removeEventListener('keydown', onKeyDown)
  }, [container, enabled, mobile])
}

