import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Persona } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  systemPrompt: z.string().min(1, 'System-Prompt erforderlich.'),
  traits: z.string(),
})

export type PersonaEditorValues = z.infer<typeof editorSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePersonaFormResult {
  form: UseFormReturn<PersonaEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

/**
 * Editor-Form fuer Persona-Update. Wartet bis `persona` geladen ist,
 * resettet dann die Defaults. Submit ruft updatePersona, zeigt Toast
 * und triggert das uebergebene `onSaved` (typisch: reload).
 */
export function usePersonaForm(
  persona: Persona | null,
  onSaved: () => void,
): UsePersonaFormResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PersonaEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: { name: '', description: '', systemPrompt: '', traits: '' },
  })

  useEffect(() => {
    if (persona !== null) {
      form.reset({
        name: persona.name,
        description: persona.content.description,
        systemPrompt: persona.content.system_prompt,
        traits: persona.content.traits.join(', '),
      })
    }
  }, [persona, form])

  const onSubmit = form.handleSubmit(async (values) => {
    if (persona === null) {
      return
    }
    setSaveError(null)
    try {
      await api.updatePersona(persona.id, {
        name: values.name,
        content: {
          description: values.description,
          system_prompt: values.systemPrompt,
          traits: splitList(values.traits),
        },
      })
      notify.success('Gespeichert — neue Version erstellt.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
