import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Welle 4: Create ist immer erlaubt. `name` ist die einzige clientseitige
// Pflicht. Schema spiegelt `useResourceForm`, damit `ResourceEditorForm`
// mit beiden Hooks funktioniert.
const createSchema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  description: z.string(),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
})

export type ResourceCreateValues = z.infer<typeof createSchema>

export interface UseCreateResourceResult {
  form: UseFormReturn<ResourceCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreateResource(onCreated: (id: string) => void): UseCreateResourceResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<ResourceCreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: '', bodyBlocks: [] },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createResource({
        name: values.name,
        content: { description: values.description, blocks: values.bodyBlocks },
      })
      notify.success('Resource angelegt.')
      onCreated(created.id)
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
    }
  })

  return { form, onSubmit, saveError }
}
