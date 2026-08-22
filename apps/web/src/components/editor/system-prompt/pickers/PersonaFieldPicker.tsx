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
import { useTranslation } from 'react-i18next'

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

// `label` ist der Wert, der als BlockNote-Prop INS DOKUMENT geschrieben wird —
// also Inhalt und damit an die Sprache des System-Prompts gebunden (ADR-0045),
// nicht an die UI-Sprache. Er bleibt bewusst stabil, sonst traegt derselbe
// Prompt je nach Bediener gemischtsprachige Pills. `labelKey`/`descriptionKey`
// sind die UI-Anzeige und folgen der Oberflaechensprache.
const OPTIONS: {
  target_id: PersonaFieldTarget
  label: string
  labelKey: string
  descriptionKey: string
}[] = [
  {
    target_id: 'name',
    label: 'Persona: Name',
    labelKey: 'picker.personaField.name.label',
    descriptionKey: 'picker.personaField.name.description',
  },
  {
    target_id: 'description',
    label: 'Persona: Beschreibung',
    labelKey: 'picker.personaField.description.label',
    descriptionKey: 'picker.personaField.description.description',
  },
  {
    target_id: 'profile',
    label: 'Persona: Profil (vollständig)',
    labelKey: 'picker.personaField.profile.label',
    descriptionKey: 'picker.personaField.profile.description',
  },
  {
    target_id: 'profile-body',
    label: 'Persona: Profil-Inhalt',
    labelKey: 'picker.personaField.profileBody.label',
    descriptionKey: 'picker.personaField.profileBody.description',
  },
  {
    target_id: 'modes',
    label: 'Persona: Modi',
    labelKey: 'picker.personaField.modes.label',
    descriptionKey: 'picker.personaField.modes.description',
  },
]

export function PersonaFieldPicker({
  open,
  onConfirm,
  onCancel,
  anchorRef,
  initial,
}: PersonaFieldPickerProps) {
  const { t } = useTranslation('editor')
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
      title={isEdit ? t('picker.personaField.titleEdit') : t('picker.personaField.titleNew')}
      ariaLabel={t('picker.personaField.ariaLabel')}
      testId="persona-field-picker-dialog"
    >
      <RadioGroup
        value={selected}
        onValueChange={(value) => setSelected(value as PersonaFieldTarget)}
        aria-label={t('picker.personaField.listLabel')}
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
                <span className="text-sm font-medium">{t(opt.labelKey)}</span>
                <span className="text-xs text-muted-foreground">{t(opt.descriptionKey)}</span>
              </span>
            </Label>
          )
        })}
      </RadioGroup>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel}>
          {t('picker.cancel')}
        </Button>
        <Button variant="brand" onClick={handleConfirm} data-testid="persona-field-picker-confirm">
          {isEdit ? t('picker.update') : t('picker.insert')}
        </Button>
      </div>
    </PickerPopover>
  )
}
