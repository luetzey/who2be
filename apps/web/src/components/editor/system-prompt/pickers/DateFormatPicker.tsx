// DateFormatPicker — Radio-Dialog: ISO-8601 oder lesbar.
// Kein API-Call. target_id ist "" (ISO) oder "human" (lesbar).
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { type AnchorRef } from '@/components/ui/popover'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PickerPopover } from './PickerPopover'
import { useTranslation } from 'react-i18next'

type DateFormatTarget = '' | 'human'

interface DateFormatPickerProps {
  open: boolean
  onConfirm: (props: PlaceholderProps) => void
  onCancel: () => void
  /** Anker fuer das schwebende Panel (Pill beim Bearbeiten, Caret beim Einfuegen). */
  anchorRef?: AnchorRef
  /** Edit-Modus: vorhandene Pill-Werte; das Format wird vorbelegt. */
  initial?: PlaceholderProps
}

const OPTIONS: {
  target_id: DateFormatTarget
  inputId: string
  label: string
  labelKey: string
  descriptionKey: string
  example: string
}[] = [
  {
    target_id: 'human',
    inputId: 'date-format-human',
    label: 'Datum (lesbar)',
    labelKey: 'picker.date.readable.label',
    descriptionKey: 'picker.date.readable.description',
    example: '31. Mai 2026',
  },
  {
    target_id: '',
    inputId: 'date-format-iso',
    label: 'Datum (ISO-8601)',
    labelKey: 'picker.date.iso.label',
    descriptionKey: 'picker.date.iso.description',
    example: '2026-05-31',
  },
]

export function DateFormatPicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: DateFormatPickerProps) {
  const { t } = useTranslation('editor')
  const [selected, setSelected] = useState<DateFormatTarget>('human')

  const isEdit = initial !== undefined
  const initialTargetId = initial?.target_id

  // Beim Oeffnen das Format auf den aktuellen Pill-Wert (Edit) oder den
  // Default 'human' (Neu) setzen. '' (ISO) ist ein gueltiger Wert.
  useEffect(() => {
    if (!open) return
    setSelected(initialTargetId === '' ? '' : initialTargetId === 'human' ? 'human' : 'human')
  }, [open, initialTargetId])

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
    <PickerPopover
      open={open}
      onCancel={onCancel}
      anchorRef={anchorRef}
      title={isEdit ? t('picker.date.titleEdit') : t('picker.date.titleNew')}
      ariaLabel={t('picker.date.ariaLabel')}
      testId="date-format-picker-dialog"
    >
      {/* Radix behandelt den leeren String als „keine Auswahl"; ISO ('') wird
          daher auf den Radio-Wert 'iso' gemappt und beim Wechsel zurueck-
          uebersetzt. Der target_id-Vertrag (`''` = ISO) bleibt unveraendert. */}
      <RadioGroup
        value={selected === '' ? 'iso' : 'human'}
        onValueChange={(value) => setSelected(value === 'iso' ? '' : 'human')}
        aria-label={t('picker.date.listLabel')}
      >
        {OPTIONS.map((opt) => {
          const radioValue = opt.target_id === '' ? 'iso' : opt.target_id
          return (
            <Label
              key={opt.inputId}
              htmlFor={opt.inputId}
              className="flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal hover:bg-muted/50"
            >
              <RadioGroupItem
                id={opt.inputId}
                value={radioValue}
                data-testid={`date-format-option-${radioValue}`}
                className="mt-0.5"
              />
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">{t(opt.labelKey)}</span>
                <span className="text-xs text-muted-foreground">
                  {t(opt.descriptionKey)} — Beispiel:{' '}
                  <code className="font-mono">{opt.example}</code>
                </span>
              </span>
            </Label>
          )
        })}
      </RadioGroup>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          {t('picker.cancel')}
        </Button>
        <Button variant="brand" onClick={handleConfirm} data-testid="date-format-picker-confirm">
          {isEdit ? t('picker.update') : t('picker.insert')}
        </Button>
      </div>
    </PickerPopover>
  )
}
