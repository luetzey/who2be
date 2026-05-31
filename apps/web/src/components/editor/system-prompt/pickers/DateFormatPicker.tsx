// DateFormatPicker — Radio-Dialog: ISO-8601 oder lesbar.
// Kein API-Call. target_id ist "" (ISO) oder "human" (lesbar).
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

import type { PlaceholderProps } from '../PlaceholderBlock'

type DateFormatTarget = '' | 'human'

interface DateFormatPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
}

const OPTIONS: {
  target_id: DateFormatTarget
  inputId: string
  label: string
  description: string
  example: string
}[] = [
  {
    target_id: 'human',
    inputId: 'date-format-human',
    label: 'Datum (lesbar)',
    description: 'Wird als "31. Mai 2026" ausgegeben',
    example: '31. Mai 2026',
  },
  {
    target_id: '',
    inputId: 'date-format-iso',
    label: 'Datum (ISO-8601)',
    description: 'Wird als "2026-05-31" ausgegeben',
    example: '2026-05-31',
  },
]

export function DateFormatPicker({ open, onConfirm, onCancel }: DateFormatPickerProps) {
  const [selected, setSelected] = useState<DateFormatTarget>('human')

  function handleConfirm() {
    const option = OPTIONS.find((o) => o.target_id === selected)
    if (option === undefined) return
    onConfirm({
      kind: 'date',
      target_id: option.target_id,
      label: option.label,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      <DialogContent data-testid="date-format-picker-dialog">
        <DialogHeader>
          <DialogTitle>Datum einfuegen</DialogTitle>
        </DialogHeader>
        <fieldset className="flex flex-col gap-2">
          <legend className="sr-only">Datumsformat auswaehlen</legend>
          {OPTIONS.map((opt) => (
            <div
              key={opt.inputId}
              className="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-muted/50"
            >
              <input
                id={opt.inputId}
                type="radio"
                name="date-format"
                value={opt.target_id}
                checked={selected === opt.target_id}
                onChange={() => setSelected(opt.target_id)}
                data-testid={`date-format-option-${opt.target_id === '' ? 'iso' : opt.target_id}`}
                className="mt-0.5"
              />
              <label htmlFor={opt.inputId} className="flex cursor-pointer flex-col gap-0.5">
                <span className="text-sm font-medium">{opt.label}</span>
                <span className="text-xs text-muted-foreground">
                  {opt.description} — Beispiel:{' '}
                  <code className="font-mono">{opt.example}</code>
                </span>
              </label>
            </div>
          ))}
        </fieldset>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Abbrechen
          </Button>
          <Button variant="brand" onClick={handleConfirm} data-testid="date-format-picker-confirm">
            Einfuegen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
