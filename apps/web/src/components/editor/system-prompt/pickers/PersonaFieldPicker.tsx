// PersonaFieldPicker — Radio-Dialog: "Name", "Beschreibung" oder "Profil (vollstaendig)".
// Kein API-Call. target_id ist der englische Slug "name" / "description" / "profile".
// Track E1: "profile" rendert die volle Persona-Persoenlichkeit inkl. BlockNote-Body und Modi.
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { type AnchorRef } from '@/components/ui/popover'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'

type PersonaFieldTarget = 'name' | 'description' | 'profile' | 'profile-body' | 'modes'

interface PersonaFieldPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /** Edit-Modus: vorhandene Pill-Werte; das referenzierte Feld wird vorbelegt. */
  initial?: PlaceholderProps
}

function isPersonaFieldTarget(value: string | undefined): value is PersonaFieldTarget {
  return (
    value === 'name' ||
    value === 'description' ||
    value === 'profile' ||
    value === 'profile-body' ||
    value === 'modes'
  )
}

const OPTIONS: { target_id: PersonaFieldTarget; label: string; description: string }[] = [
  { target_id: 'name', label: 'Persona: Name', description: 'Der Name der Persona' },
  {
    target_id: 'description',
    label: 'Persona: Beschreibung',
    description: 'Die Beschreibung der Persona',
  },
  {
    target_id: 'profile',
    label: 'Persona: Profil (vollständig)',
    description:
      'Rendert die vollständige Persönlichkeit — Beschreibung, Profil-Body und Modi. ' +
      'Empfohlen für den System-Prompt-Bootstrap.',
  },
  {
    target_id: 'profile-body',
    label: 'Persona: Profil-Inhalt',
    description:
      'Rendert nur den Profil-Body (BlockNote-Inhalt) — ohne Beschreibung, Traits oder Modi.',
  },
  {
    target_id: 'modes',
    label: 'Persona: Modi',
    description:
      'Rendert nur die Modi-Sektion der Persona. Ohne Modi bleibt die Stelle leer.',
  },
]

export function PersonaFieldPicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: PersonaFieldPickerProps) {
  const [selected, setSelected] = useState<PersonaFieldTarget>('name')

  const isEdit = initial !== undefined
  const initialTargetId = initial?.target_id

  // Beim Oeffnen die Radio-Auswahl auf den aktuellen Pill-Wert (Edit) oder
  // den Default 'name' (Neu) setzen.
  useEffect(() => {
    if (!open) return
    setSelected(isPersonaFieldTarget(initialTargetId) ? initialTargetId : 'name')
  }, [open, initialTargetId])

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
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? 'Persona-Feld ändern' : 'Persona-Feld einfuegen'}
      ariaLabel="Persona-Feld einfuegen"
      testId="persona-field-picker-dialog"
    >
      <RadioGroup
        value={selected}
        onValueChange={(value) => setSelected(value as PersonaFieldTarget)}
        aria-label="Persona-Feld auswaehlen"
      >
        {OPTIONS.map((opt) => {
          const inputId = `persona-field-${opt.target_id}`
          return (
            <Label
              key={opt.target_id}
              htmlFor={inputId}
              className="flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal hover:bg-muted/50"
            >
              <RadioGroupItem
                id={inputId}
                value={opt.target_id}
                data-testid={`persona-field-option-${opt.target_id}`}
                className="mt-0.5"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">{opt.label}</span>
                <span className="text-xs text-muted-foreground">{opt.description}</span>
              </span>
            </Label>
          )
        })}
      </RadioGroup>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button variant="brand" onClick={handleConfirm} data-testid="persona-field-picker-confirm">
          {isEdit ? 'Aktualisieren' : 'Einfuegen'}
        </Button>
      </div>
    </PickerPopover>
  )
}
