// PersonaFieldPicker — Radio-Dialog: "Name" oder "Beschreibung".
// Kein API-Call. target_id ist der englische Slug "name" / "description".
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

type PersonaFieldTarget = 'name' | 'description'

interface PersonaFieldPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
}

const OPTIONS: { target_id: PersonaFieldTarget; label: string; description: string }[] = [
  { target_id: 'name', label: 'Persona: Name', description: 'Der Name der Persona' },
  {
    target_id: 'description',
    label: 'Persona: Beschreibung',
    description: 'Die Beschreibung der Persona',
  },
]

export function PersonaFieldPicker({ open, onConfirm, onCancel }: PersonaFieldPickerProps) {
  const [selected, setSelected] = useState<PersonaFieldTarget>('name')

  function handleConfirm() {
    const option = OPTIONS.find((o) => o.target_id === selected)
    if (option === undefined) return
    onConfirm({
      kind: 'persona-field',
      target_id: option.target_id,
      label: option.label,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel() }}>
      <DialogContent data-testid="persona-field-picker-dialog">
        <DialogHeader>
          <DialogTitle>Persona-Feld einfuegen</DialogTitle>
        </DialogHeader>
        <fieldset className="flex flex-col gap-2">
          <legend className="sr-only">Persona-Feld auswaehlen</legend>
          {OPTIONS.map((opt) => {
            const inputId = `persona-field-${opt.target_id}`
            return (
              <div
                key={opt.target_id}
                className="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-muted/50"
              >
                <input
                  id={inputId}
                  type="radio"
                  name="persona-field"
                  value={opt.target_id}
                  checked={selected === opt.target_id}
                  onChange={() => setSelected(opt.target_id)}
                  data-testid={`persona-field-option-${opt.target_id}`}
                  className="mt-0.5"
                />
                <label htmlFor={inputId} className="flex cursor-pointer flex-col gap-0.5">
                  <span className="text-sm font-medium">{opt.label}</span>
                  <span className="text-xs text-muted-foreground">{opt.description}</span>
                </label>
              </div>
            )
          })}
        </fieldset>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Abbrechen
          </Button>
          <Button variant="brand" onClick={handleConfirm} data-testid="persona-field-picker-confirm">
            Einfuegen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
