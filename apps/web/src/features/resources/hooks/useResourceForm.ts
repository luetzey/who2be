import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useRef, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Resource, ResourceBlock, ResourceInput } from '@/api/types'
// Track E3: Tags werden jetzt Teil des Form-States.
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
  // Track E3 — Tags (jsonb, keine Migration noetig).
  tags: z.array(z.string()),
})

export type ResourceEditorValues = z.infer<typeof schema>

export interface UseResourceFormResult {
  form: UseFormReturn<ResourceEditorValues>
  autoSave: UseAutoSaveDraftResult
}

export function useResourceForm(
  resource: Resource | null,
  onSaved?: () => void,
): UseResourceFormResult {
  const api = useApi()
  const form = useForm<ResourceEditorValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '', bodyBlocks: [], tags: [] },
  })
  // Siehe `usePersonaForm` — `formReady` verhindert das Default-Snapshot-Race.
  const [formReady, setFormReady] = useState(false)
  const resetIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (resource === null || resetIdRef.current === resource.id) {
      return
    }
    form.reset({
      name: resource.name,
      description: resource.content.description ?? '',
      bodyBlocks: resource.content.blocks ?? [],
      tags: resource.content.tags ?? [],
    })
    resetIdRef.current = resource.id
    setFormReady(true)
  }, [resource, form])

  const values = form.watch()
  // Auto-Save baut ResourceInput aus den Form-Werten inkl. bodyBlocks + tags.
  const combined: ResourceInput = {
    name: values.name,
    content: { description: values.description, blocks: values.bodyBlocks, tags: values.tags },
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
    onSaved,
  })

  return { form, autoSave }
}
