// CatalogScopePicker — Radio-Dialog: Welche Playbooks listet die Katalog-Pill?
// Kein API-Call. target_id ist 'all' (alle verknuepften) oder 'triggered'
// (nur Playbooks mit Trigger). Der Resolver filtert beim Render entsprechend.
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { type AnchorRef } from '@/components/ui/popover'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'

type CatalogScope = 'all' | 'triggered'

interface CatalogScopePickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /** Edit-Modus: vorhandene Pill-Werte; der Scope wird vorbelegt. */
  initial?: PlaceholderProps
}

function isCatalogScope(value: string | undefined): value is CatalogScope {
  return value === 'all' || value === 'triggered'
}

const OPTIONS: { target_id: CatalogScope; label: string; description: string }[] = [
  {
    target_id: 'all',
    label: 'Alle verknüpften Playbooks',
    description: 'Listet alle der Persona zugeordneten aktiven Playbooks — auch ohne Trigger.',
  },
  {
    target_id: 'triggered',
    label: 'Nur getriggerte Playbooks',
    description: 'Listet nur Playbooks mit einem nicht-leeren Trigger-Feld.',
  },
]

export function CatalogScopePicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: CatalogScopePickerProps) {
  const [selected, setSelected] = useState<CatalogScope>('all')

  const isEdit = initial !== undefined
  const initialTargetId = initial?.target_id

  // Beim Oeffnen den Scope auf den aktuellen Pill-Wert (Edit) oder den Default
  // 'all' (Neu) setzen.
  useEffect(() => {
    if (!open) return
    setSelected(isCatalogScope(initialTargetId) ? initialTargetId : 'all')
  }, [open, initialTargetId])

  function handleConfirm() {
    const option = OPTIONS.find((o) => o.target_id === selected)
    if (option === undefined) return
    onConfirm({
      kind: 'playbooks-catalog',
      target_id: option.target_id,
      label: `Playbook-Katalog (${option.target_id === 'triggered' ? 'getriggert' : 'alle'})`,
    })
  }

  return (
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? 'Playbook-Katalog ändern' : 'Playbook-Katalog einfuegen'}
      ariaLabel="Playbook-Katalog einfuegen"
      testId="catalog-scope-picker-dialog"
    >
      <RadioGroup
        value={selected}
        onValueChange={(value) => setSelected(value as CatalogScope)}
        aria-label="Playbook-Auswahl für den Katalog"
      >
        {OPTIONS.map((opt) => {
          const inputId = `catalog-scope-${opt.target_id}`
          return (
            <Label
              key={opt.target_id}
              htmlFor={inputId}
              className="flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal hover:bg-muted/50"
            >
              <RadioGroupItem
                id={inputId}
                value={opt.target_id}
                data-testid={`catalog-scope-option-${opt.target_id}`}
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
        <Button variant="brand" onClick={handleConfirm} data-testid="catalog-scope-picker-confirm">
          {isEdit ? 'Aktualisieren' : 'Einfuegen'}
        </Button>
      </div>
    </PickerPopover>
  )
}
