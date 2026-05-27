import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  systemPrompt: z.string().min(1, 'System-Prompt erforderlich.'),
  traits: z.string(),
})

export type PersonaCreateValues = z.infer<typeof createSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

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
    defaultValues: { name: '', description: '', systemPrompt: '', traits: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createPersona({
        name: values.name,
        content: {
          description: values.description,
          system_prompt: values.systemPrompt,
          traits: splitList(values.traits),
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
