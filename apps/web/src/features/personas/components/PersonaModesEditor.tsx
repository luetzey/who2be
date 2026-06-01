// PersonaModesEditor — useFieldArray-basierter Editor fuer Persona-Modi.
// Jeder Modus hat: Name (Input), Trigger (Input), Default (exklusiv via Radio-
// Logik), Playbook-Bezug (Select) und drei BlockNote-Inseln (Identity-Add,
// Output-Stil, Anti-Patterns). PR-A: Die ehemaligen Textareas sind durch die
// geteilte BlockNote-Insel (`ResourceEditor`) ersetzt — Modi-Felder sind jetzt
// strukturierte Block-Dokumente, kein Plain-Text mehr.
// Alles ueber @/components/ui/* bzw. die geteilte Editor-Insel (Lint-Gate).

import { Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useFieldArray, useFormContext, useWatch, type Control } from 'react-hook-form'

import type { Playbook, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'
import type { PersonaEditorValues } from '@/features/personas/hooks/usePersonaForm'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { cn } from '@/lib/utils'

interface PersonaModesEditorProps {
  control: Control<PersonaEditorValues>
  disabled?: boolean
}

// Eine BlockNote-Insel fuer ein Modus-Block-Feld. Snapshotet `initialBlocks`
// einmalig beim Mount (per Closure-Default), damit der frische Editor nicht
// den spaeter durchlaufenden form.reset-State sieht — Pattern parallel zum
// Profil-Editor in PersonaEditorForm. `instanceKey` (= useFieldArray-`field.id`
// plus Feldname) remountet die Insel beim Hinzufuegen/Entfernen von Modi.
interface ModeBlockFieldProps {
  control: Control<PersonaEditorValues>
  index: number
  field: 'identity_add' | 'output_style_override' | 'anti_patterns'
  label: string
  instanceKey: string
  disabled: boolean
}

function ModeBlockField({
  control,
  index,
  field,
  label,
  instanceKey,
  disabled,
}: ModeBlockFieldProps) {
  return (
    <FormField
      control={control}
      name={`modes.${index}.${field}`}
      render={({ field: f }) => {
        // Initial-Snapshot nur beim ersten Render dieser Insel.
        const initialBlocks = (f.value ?? []) as ResourceBlock[]
        return (
          <FormItem>
            <FormLabel>{label}</FormLabel>
            <FormControl>
              <ResourceEditor
                key={`${instanceKey}-${field}`}
                initialBlocks={initialBlocks}
                editable={!disabled}
                onChange={(blocks: ResourceBlock[]) => f.onChange(blocks)}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )
      }}
    />
  )
}

// Playbook-Select fuer einen Modus. Laedt die Playbook-Liste ueber denselben
// `api.listPlaybooks()`-Mechanismus wie PlaybookPicker. Setzt sowohl
// `playbook_id` als auch den denormalisierten `playbook_name`-Snapshot.
interface ModePlaybookSelectProps {
  control: Control<PersonaEditorValues>
  index: number
  disabled: boolean
}

function ModePlaybookSelect({ control, index, disabled }: ModePlaybookSelectProps) {
  const api = useApi()
  const { setValue } = useFormContext<PersonaEditorValues>()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])

  useEffect(() => {
    let active = true
    api
      .listPlaybooks()
      .then((items) => {
        if (active) setPlaybooks(items)
      })
      .catch(() => {
        if (active) setPlaybooks([])
      })
    return () => {
      active = false
    }
  }, [api])

  return (
    <FormField
      control={control}
      name={`modes.${index}.playbook_id`}
      render={({ field: f }) => (
        <FormItem>
          <FormLabel>Playbook</FormLabel>
          <FormControl>
            <Select
              value={f.value ?? ''}
              disabled={disabled}
              onChange={(event) => {
                const id = event.target.value
                if (id === '') {
                  f.onChange(null)
                  setValue(`modes.${index}.playbook_name`, undefined)
                  return
                }
                const picked = playbooks.find((p) => p.id === id)
                f.onChange(id)
                setValue(`modes.${index}.playbook_name`, picked?.name ?? '')
              }}
            >
              <option value="">Kein Playbook</option>
              {playbooks.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </FormControl>
          <p className="text-xs text-muted-foreground">
            Optional — verknüpft diesen Modus mit einem Playbook.
          </p>
          <FormMessage />
        </FormItem>
      )}
    />
  )
}

export function PersonaModesEditor({ control, disabled = false }: PersonaModesEditorProps) {
  const { fields, append, remove, update } = useFieldArray({
    control,
    name: 'modes',
  })

  const addMode = useCallback(() => {
    append({
      name: '',
      trigger: '',
      is_default: fields.length === 0, // erster Modus ist automatisch Default
      identity_add: [],
      output_style_override: [],
      anti_patterns: [],
      playbook_id: null,
      playbook_name: undefined,
    })
  }, [append, fields.length])

  // Exklusivitaet: nur ein Default gleichzeitig — wie ein RadioGroup-Ersatz.
  const setDefault = useCallback(
    (index: number) => {
      fields.forEach((_, i) => {
        if (i === index) {
          update(i, { ...fields[i], is_default: true })
        } else if (fields[i].is_default) {
          update(i, { ...fields[i], is_default: false })
        }
      })
    },
    [fields, update],
  )

  if (fields.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Noch keine Modi definiert. Modi ermöglichen es der Persona, je nach Kontext
          unterschiedlich zu agieren (z. B. „Coaching-Modus" vs. „Analyse-Modus").
        </p>
        <div className="flex justify-start">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addMode}
            disabled={disabled}
          >
            <Plus className="size-4" />
            Ersten Modus anlegen
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {fields.map((field, index) => (
        <PersonaModeCard
          key={field.id}
          control={control}
          index={index}
          instanceKey={field.id}
          isDefault={field.is_default}
          disabled={disabled}
          onSetDefault={() => setDefault(index)}
          onRemove={() => remove(index)}
        />
      ))}

      <div className="flex justify-start">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addMode}
          disabled={disabled}
        >
          <Plus className="size-4" />
          Modus hinzufügen
        </Button>
      </div>
    </div>
  )
}

interface PersonaModeCardProps {
  control: Control<PersonaEditorValues>
  index: number
  instanceKey: string
  isDefault: boolean
  disabled: boolean
  onSetDefault: () => void
  onRemove: () => void
}

function PersonaModeCard({
  control,
  index,
  instanceKey,
  isDefault,
  disabled,
  onSetDefault,
  onRemove,
}: PersonaModeCardProps) {
  // Live-Default aus dem Form-State (useFieldArray-`field.is_default` aktualisiert
  // sich nicht ohne Re-Sync; useWatch ist die verlaessliche Quelle fuer das Badge).
  const watchedDefault = useWatch({ control, name: `modes.${index}.is_default` })
  const showDefault = watchedDefault ?? isDefault

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border p-4',
        showDefault && 'border-border bg-muted/40',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">
            Modus {index + 1}
          </span>
          {showDefault ? <Badge variant="secondary">Default</Badge> : null}
        </div>
        <div className="flex items-center gap-2">
          {!showDefault ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onSetDefault}
              disabled={disabled}
              className="text-xs"
            >
              Als Default setzen
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemove}
            disabled={disabled}
            aria-label={`Modus ${index + 1} entfernen`}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      <FormField
        control={control}
        name={`modes.${index}.name`}
        render={({ field: f }) => (
          <FormItem>
            <FormLabel>Name</FormLabel>
            <FormControl>
              <Input {...f} placeholder="z. B. Coaching-Modus" disabled={disabled} />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={`modes.${index}.trigger`}
        render={({ field: f }) => (
          <FormItem>
            <FormLabel>Trigger</FormLabel>
            <FormControl>
              <Input
                {...f}
                value={f.value ?? ''}
                placeholder="z. B. coaching, feedback (kommagetrennt)"
                disabled={disabled}
              />
            </FormControl>
            <p className="text-xs text-muted-foreground">
              Kommagetrennte Schlüsselwörter. Leer = Default-Modus
              (nur einer erlaubt).
            </p>
            <FormMessage />
          </FormItem>
        )}
      />

      <ModePlaybookSelect control={control} index={index} disabled={disabled} />

      <ModeBlockField
        control={control}
        index={index}
        field="identity_add"
        label="Identity-Ergänzung"
        instanceKey={instanceKey}
        disabled={disabled}
      />
      <ModeBlockField
        control={control}
        index={index}
        field="output_style_override"
        label="Output-Stil"
        instanceKey={instanceKey}
        disabled={disabled}
      />
      <ModeBlockField
        control={control}
        index={index}
        field="anti_patterns"
        label="Anti-Patterns"
        instanceKey={instanceKey}
        disabled={disabled}
      />
    </div>
  )
}
