import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'
import i18n from '@/i18n'

// Welle 4: Create ist immer erlaubt. `name` ist die einzige clientseitige
// Pflicht. Schema spiegelt `useResourceForm`, damit `ResourceEditorForm`
// mit beiden Hooks funktioniert.
// Track E3: Tags hinzugefuegt.
const createSchema = z.object({
  name: z.string().min(1, { error: () => i18n.t('common:validation.nameRequiredLong') }),
  description: z.string(),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
})

export type ResourceCreateValues = z.infer<typeof createSchema>

export interface UseCreateResourceResult {
  form: UseFormReturn<ResourceCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreateResource(
  onCreated: (id: string) => void,
  // Ein Element, eine Sprache (ADR-0045): einzelne Sprache statt der
  // frueheren Multi-Auswahl. `undefined` laesst das Backend auf die
  // Workspace-Content-Sprache defaulten.
  locale?: string,
): UseCreateResourceResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<ResourceCreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', description: '', bodyBlocks: [], tags: [] },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createResource({
        name: values.name,
        content: { description: values.description, blocks: values.bodyBlocks, tags: values.tags },
        locale,
      })
      notify.success(i18n.t('resources:toast.created'))
      onCreated(created.id)
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : i18n.t('common:errors.createFailed'))
    }
  })

  return { form, onSubmit, saveError }
}
