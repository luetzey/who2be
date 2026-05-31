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

const schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  description: z.string(),
})

export type ResourceEditorValues = z.infer<typeof schema>

export interface UseResourceFormResult {
  form: UseFormReturn<ResourceEditorValues>
  blocks: ResourceBlock[]
  setBlocks: (blocks: ResourceBlock[]) => void
  autoSave: UseAutoSaveDraftResult
}

export function useResourceForm(resource: Resource | null): UseResourceFormResult {
  const api = useApi()
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const form = useForm<ResourceEditorValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '' },
  })
  // Siehe `usePersonaForm` — `formReady` verhindert das Default-Snapshot-Race.
  const [formReady, setFormReady] = useState(false)

  useEffect(() => {
    if (resource === null) {
      return
    }
    form.reset({ name: resource.name, description: resource.content.description ?? '' })
    setBlocks(resource.content.blocks ?? [])
    setFormReady(true)
  }, [resource, form])

  const values = form.watch()
  // Auto-Save bekommt name + description + blocks als kombinierten Snapshot.
  // Blocks sind ein eigener State (BlockNote-Onsave reicht sie via Setter).
  const combined: ResourceInput = {
    name: values.name,
    content: { description: values.description, blocks },
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

  return { form, blocks, setBlocks, autoSave }
}
