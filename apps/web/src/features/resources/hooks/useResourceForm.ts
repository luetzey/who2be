import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import type { Resource, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'

const schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  description: z.string(),
})

export type ResourceEditorValues = z.infer<typeof schema>

export function useResourceForm(resource: Resource | null, onSaved: () => void) {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const form = useForm<ResourceEditorValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '' },
  })

  useEffect(() => {
    if (resource === null) {
      return
    }
    form.reset({ name: resource.name, description: resource.content.description ?? '' })
    setBlocks(resource.content.blocks ?? [])
  }, [resource, form])

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      await api.updateResource(resource?.id ?? '', {
        name: values.name,
        content: { description: values.description, blocks },
      })
      onSaved()
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : 'Speichern fehlgeschlagen.')
    }
  })

  return { form, blocks, setBlocks, onSubmit, saveError }
}
