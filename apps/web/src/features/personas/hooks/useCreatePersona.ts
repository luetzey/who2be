import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Welle 4: Create ist immer erlaubt. `name` ist die einzige clientseitige
// Pflicht (Spec: "Anlegen geht immer"). Body, Description duerfen leer sein.
// Schema spiegelt `usePersonaForm.editorSchema`, damit `PersonaEditorForm`
// mit beiden Hooks funktioniert.
const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  profileBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
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
    defaultValues: {
      name: '',
      description: '',
      profileBlocks: [],
      tags: [],
    },
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
          tags: values.tags,
          content: { description: '', blocks: values.profileBlocks },
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
