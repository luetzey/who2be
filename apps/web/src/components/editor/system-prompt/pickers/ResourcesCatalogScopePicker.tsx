// ResourcesCatalogScopePicker — Radio-Dialog: Welche Resources listet die
// Resource-Katalog-Pill? `target_id` ist 'all' (alle aktiven Resources des
// Workspace) oder ein Tag-String (nur Resources mit diesem Tag). Der Resolver
// filtert beim Render entsprechend (kein Persona-Kontext noetig).
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { type AnchorRef } from '@/components/ui/popover'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'

type CatalogMode = 'all' | 'tag'

interface ResourcesCatalogScopePickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /** Edit-Modus: vorhandene Pill-Werte; Modus + Tag werden vorbelegt. */
  initial?: PlaceholderProps
}

function labelFor(mode: CatalogMode, tag: string): string {
  if (mode === 'tag' && tag.trim() !== '') return `Resource-Katalog (Tag: ${tag.trim()})`
  return 'Resource-Katalog (alle)'
}

export function ResourcesCatalogScopePicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: ResourcesCatalogScopePickerProps) {
  const [mode, setMode] = useState<CatalogMode>('all')
  const [tag, setTag] = useState('')

  const isEdit = initial !== undefined
  const initialTargetId = initial?.target_id

  // Beim Oeffnen den Modus + Tag aus dem aktuellen Pill-Wert (Edit) oder dem
  // Default ('all') ableiten. `target_id` ist entweder '' / 'all' oder ein Tag.
  useEffect(() => {
    if (!open) return
    const value = initialTargetId ?? ''
    if (value === '' || value === 'all') {
      setMode('all')
      setTag('')
    } else {
      setMode('tag')
      setTag(value)
    }
  }, [open, initialTargetId])

  function handleConfirm() {
    const targetId = mode === 'tag' ? tag.trim() : 'all'
    // Leerer Tag-Input → wie 'all' behandeln (keine sinnlose Leer-Filter-Pill).
    const effectiveTargetId = mode === 'tag' && targetId === '' ? 'all' : targetId
    onConfirm({
      kind: 'resources-catalog',
      target_id: effectiveTargetId,
      label: labelFor(effectiveTargetId === 'all' ? 'all' : 'tag', tag),
    })
  }

  return (
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? 'Resource-Katalog ändern' : 'Resource-Katalog einfuegen'}
      ariaLabel="Resource-Katalog einfuegen"
      testId="resources-catalog-scope-picker-dialog"
    >
      <fieldset className="flex flex-col gap-2">
        <legend className="sr-only">Resource-Auswahl für den Katalog</legend>
        <div className="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-muted/50">
          <input
            id="resources-catalog-mode-all"
            type="radio"
            name="resources-catalog-mode"
            value="all"
            checked={mode === 'all'}
            onChange={() => setMode('all')}
            data-testid="resources-catalog-option-all"
            className="mt-0.5"
          />
          <label htmlFor="resources-catalog-mode-all" className="flex cursor-pointer flex-col gap-0.5">
            <span className="text-sm font-medium">Alle Resources</span>
            <span className="text-xs text-muted-foreground">
              Listet alle aktiven Resources des Workspace.
            </span>
          </label>
        </div>
        <div className="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-muted/50">
          <input
            id="resources-catalog-mode-tag"
            type="radio"
            name="resources-catalog-mode"
            value="tag"
            checked={mode === 'tag'}
            onChange={() => setMode('tag')}
            data-testid="resources-catalog-option-tag"
            className="mt-0.5"
          />
          <label htmlFor="resources-catalog-mode-tag" className="flex flex-1 cursor-pointer flex-col gap-1">
            <span className="text-sm font-medium">Nach Tag</span>
            <span className="text-xs text-muted-foreground">
              Listet nur Resources mit dem angegebenen Tag.
            </span>
            <Input
              value={tag}
              onChange={(event) => {
                setTag(event.target.value)
                setMode('tag')
              }}
              placeholder="z. B. billing"
              aria-label="Tag für den Resource-Katalog"
              data-testid="resources-catalog-tag-input"
              className="mt-1 h-8"
            />
          </label>
        </div>
      </fieldset>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          Abbrechen
        </Button>
        <Button
          variant="brand"
          onClick={handleConfirm}
          data-testid="resources-catalog-scope-picker-confirm"
        >
          {isEdit ? 'Aktualisieren' : 'Einfuegen'}
        </Button>
      </div>
    </PickerPopover>
  )
}
