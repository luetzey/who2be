import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Phase 3 Runde 3 Track 3: `systemPrompt` ist deprecated, der System-Prompt
// lebt am Agent-Template. Neue Personas werden ohne System-Prompt-Feld
// angelegt; Pydantic-Default '' greift.
const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
})

export type PersonaCreateValues = z.infer<typeof createSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseCreatePersonaResult {
  form: UseFormReturn<PersonaCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreatePersona(onCreated: (id: string) => void): UseCreatePersonaResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PersonaCreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createPersona({
        name: values.name,
        content: {
          description: values.description,
          system_prompt: '',
          traits: [],
        },
      })
      notify.success('Persona angelegt.')
      onCreated(created.id)
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
