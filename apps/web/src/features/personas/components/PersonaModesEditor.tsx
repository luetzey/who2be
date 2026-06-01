// PersonaModesEditor — useFieldArray-basierter Editor fuer Persona-Modi.
// Jeder Modus hat: Name (Input), Trigger (Input), Default (exklusiv via Radio-
// Logik), Identity-Add + Output-Override (Textarea).
// Alles ueber @/components/ui/* (Lint-Gate).

import { Plus, Trash2 } from 'lucide-react'
import { useCallback } from 'react'
import { useFieldArray, type Control } from 'react-hook-form'

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
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface PersonaModesEditorProps {
  control: Control<PersonaEditorValues>
  disabled?: boolean
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
      identity_add: '',
      output_style_override: '',
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
        <div
          key={field.id}
          className={cn(
            'flex flex-col gap-3 rounded-lg border p-4',
            field.is_default && 'border-brand/40 bg-brand/5',
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-muted-foreground">
                Modus {index + 1}
              </span>
              {field.is_default ? (
                <Badge variant="secondary">Default</Badge>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {!field.is_default ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setDefault(index)}
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
                onClick={() => remove(index)}
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
                  <Input
                    {...f}
                    placeholder="z. B. Coaching-Modus"
                    disabled={disabled}
                  />
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

          <div className="grid grid-cols-2 gap-3">
            <FormField
              control={control}
              name={`modes.${index}.identity_add`}
              render={({ field: f }) => (
                <FormItem>
                  <FormLabel>Identity-Ergänzung</FormLabel>
                  <FormControl>
                    <Textarea
                      {...f}
                      placeholder="Was dieser Modus zur Identität ergänzt…"
                      disabled={disabled}
                      className="min-h-24 resize-none"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={control}
              name={`modes.${index}.output_style_override`}
              render={({ field: f }) => (
                <FormItem>
                  <FormLabel>Output-Stil</FormLabel>
                  <FormControl>
                    <Textarea
                      {...f}
                      placeholder="Wie sich der Antwort-Stil in diesem Modus ändert…"
                      disabled={disabled}
                      className="min-h-24 resize-none"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>
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
