// ResourcesCatalogScopePicker — Radio-Dialog: Welche Resources listet die
// Resource-Katalog-Pill? `target_id` ist 'all' (alle aktiven Resources des
// Workspace) oder ein Tag-String (nur Resources mit diesem Tag). Der Resolver
// filtert beim Render entsprechend (kein Persona-Kontext noetig).
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { type AnchorRef } from '@/components/ui/popover'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'
import { useTranslation } from 'react-i18next'

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

// Ergebnis geht als BlockNote-Prop INS DOKUMENT — Inhalt, also an die Sprache
// des System-Prompts gebunden (ADR-0045) und bewusst stabil. Uebersetzt wird
// die Picker-Oberflaeche, nicht der gespeicherte Wert.
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
  const { t } = useTranslation('editor')
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
      title={isEdit ? t('picker.resourcesCatalogScope.titleEdit') : t('picker.resourcesCatalogScope.titleNew')}
      ariaLabel={t('picker.resourcesCatalogScope.ariaLabel')}
      testId="resources-catalog-scope-picker-dialog"
    >
      <RadioGroup
        value={mode}
        onValueChange={(value) => setMode(value as CatalogMode)}
        aria-label={t('picker.resourcesCatalogScope.listLabel')}
      >
        <Label
          htmlFor="resources-catalog-mode-all"
          className="flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal hover:bg-muted/50"
        >
          <RadioGroupItem
            id="resources-catalog-mode-all"
            value="all"
            data-testid="resources-catalog-option-all"
            className="mt-0.5"
          />
          <span className="flex flex-col gap-0.5">
            <span className="text-sm font-medium">{t('picker.resourcesCatalogScope.all')}</span>
            <span className="text-xs text-muted-foreground">
              Listet alle aktiven Resources des Workspace.
            </span>
          </span>
        </Label>
        <Label
          htmlFor="resources-catalog-mode-tag"
          className="flex flex-1 cursor-pointer items-start gap-3 rounded-md border p-3 font-normal hover:bg-muted/50"
        >
          <RadioGroupItem
            id="resources-catalog-mode-tag"
            value="tag"
            data-testid="resources-catalog-option-tag"
            className="mt-0.5"
          />
          <span className="flex flex-1 flex-col gap-1">
            <span className="text-sm font-medium">{t('picker.resourcesCatalogScope.byTag')}</span>
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
              aria-label={t('picker.resourcesCatalogScope.tagLabel')}
              data-testid="resources-catalog-tag-input"
              className="mt-1 h-8"
            />
          </span>
        </Label>
      </RadioGroup>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          {t('picker.cancel')}
        </Button>
        <Button
          variant="brand"
          onClick={handleConfirm}
          data-testid="resources-catalog-scope-picker-confirm"
        >
          {isEdit ? t('picker.update') : t('picker.insert')}
        </Button>
      </div>
    </PickerPopover>
  )
}
