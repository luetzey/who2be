// PersonaSkillsEditor — useFieldArray-basierter Editor fuer Skill-Referenzen
// (PR-A). Eine Persona traegt eine flache Liste von {name, note}-Eintraegen —
// kein Aggregat, nur ein schlanker Verweis plus Notiz. Auf Persona-Ebene
// (nicht pro Modus). Alles ueber @/components/ui/* (Lint-Gate).

import { Plus, Trash2 } from 'lucide-react'
import { useCallback } from 'react'
import { useFieldArray, type Control } from 'react-hook-form'

import type { PersonaEditorValues } from '@/features/personas/hooks/usePersonaForm'
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

interface PersonaSkillsEditorProps {
  control: Control<PersonaEditorValues>
  disabled?: boolean
}

export function PersonaSkillsEditor({ control, disabled = false }: PersonaSkillsEditorProps) {
  const { fields, append, remove } = useFieldArray({
    control,
    name: 'skills',
  })

  const addSkill = useCallback(() => {
    append({ name: '', note: '' })
  }, [append])

  if (fields.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Noch keine Skills referenziert. Skills benennen Faehigkeiten, auf die
          sich die Persona stuetzt — mit einer kurzen Notiz, wofür sie zählen.
        </p>
        <div className="flex justify-start">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addSkill}
            disabled={disabled}
          >
            <Plus className="size-4" />
            Ersten Skill hinzufügen
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
          className="flex flex-col gap-3 rounded-lg border p-4"
          data-testid="persona-skill-row"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-muted-foreground">
              Skill {index + 1}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => remove(index)}
              disabled={disabled}
              aria-label={`Skill ${index + 1} entfernen`}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="size-4" />
            </Button>
          </div>

          <FormField
            control={control}
            name={`skills.${index}.name`}
            render={({ field: f }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl>
                  <Input {...f} placeholder="z. B. Aktives Zuhören" disabled={disabled} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={control}
            name={`skills.${index}.note`}
            render={({ field: f }) => (
              <FormItem>
                <FormLabel>Notiz</FormLabel>
                <FormControl>
                  <Textarea
                    {...f}
                    placeholder="Wofür dieser Skill in der Persona zählt…"
                    disabled={disabled}
                    className="min-h-20 resize-none"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      ))}

      <div className="flex justify-start">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addSkill}
          disabled={disabled}
        >
          <Plus className="size-4" />
          Skill hinzufügen
        </Button>
      </div>
    </div>
  )
}
