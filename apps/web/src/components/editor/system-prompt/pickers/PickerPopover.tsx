// PickerPopover — gemeinsame, nicht-blockierende Popover-Shell fuer alle
// Pill-Picker (Playbook/Resource/PersonaField/DateFormat). Buendelt die
// wiederholte Boilerplate (Popover-Root, Anker, Content-Klassen, Titel,
// Dismiss→onCancel) an einer Stelle; der jeweilige Picker liefert nur Body +
// Footer als `children`.
import { type ReactNode } from 'react'

import {
  type AnchorRef,
  type Measurable,
  Popover,
  PopoverAnchor,
  PopoverContent,
} from '@/components/ui/popover'

interface PickerPopoverProps {
  open: boolean
  onCancel: () => void
  /** Anker (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  title: string
  ariaLabel: string
  testId: string
  children: ReactNode
}

export function PickerPopover({
  open,
  onCancel,
  anchorRef,
  title,
  ariaLabel,
  testId,
  children,
}: PickerPopoverProps) {
  return (
    <Popover open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      {/* Radix' virtualRef erwartet RefObject<Measurable> (current non-null in den
          React-Typen); zur Laufzeit ist ein null-current zulaessig (Fallback). */}
      {anchorRef ? (
        <PopoverAnchor virtualRef={anchorRef as React.RefObject<Measurable>} />
      ) : null}
      <PopoverContent
        align="start"
        className="w-80 max-w-[min(20rem,90vw)]"
        aria-label={ariaLabel}
        data-testid={testId}
      >
        <div className="flex flex-col gap-3">
          <div className="text-sm font-semibold tracking-tight">{title}</div>
          {children}
        </div>
      </PopoverContent>
    </Popover>
  )
}
