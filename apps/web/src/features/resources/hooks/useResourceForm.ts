import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Resource, ResourceBlock, ResourceInput } from '@/api/types'
import { useApi } from '@/api/useApi'
import {
  useAutoSaveDraft,
  type UseAutoSaveDraftResult,
} from '@/hooks/useAutoSaveDraft'

// Welle 4: `bodyBlocks` in das Editor-Schema aufgenommen, damit
// `ResourceEditorForm` nahtlos sowohl mit dem Auto-Save-Hook (Detail-Page)
// als auch mit dem Create-Hook (New-Page) funktioniert.
const schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  description: z.string(),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
})

export type ResourceEditorValues = z.infer<typeof schema>

export interface UseResourceFormResult {
  form: UseFormReturn<ResourceEditorValues>
  autoSave: UseAutoSaveDraftResult
}

export function useResourceForm(resource: Resource | null): UseResourceFormResult {
  const api = useApi()
  const form = useForm<ResourceEditorValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '', bodyBlocks: [] },
  })
  // Siehe `usePersonaForm` — `formReady` verhindert das Default-Snapshot-Race.
  const [formReady, setFormReady] = useState(false)

  useEffect(() => {
    if (resource === null) {
      return
    }
    form.reset({
      name: resource.name,
      description: resource.content.description ?? '',
      bodyBlocks: resource.content.blocks ?? [],
    })
    setFormReady(true)
  }, [resource, form])

  const values = form.watch()
  // Auto-Save baut ResourceInput aus den Form-Werten inkl. bodyBlocks.
  const combined: ResourceInput = {
    name: values.name,
    content: { description: values.description, blocks: values.bodyBlocks },
  }
  const autoSave = useAutoSaveDraft<ResourceInput>({
    values: combined,
    isReady: resource !== null && formReady,
    patchFn: async (next) => {
      if (resource === null) {
        return
      }
      await api.patchResourceDraft(resource.id, next)
    },
  })

  return { form, autoSave }
}
