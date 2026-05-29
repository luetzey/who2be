import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'

const schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  description: z.string(),
})

export type ResourceCreateValues = z.infer<typeof schema>

export function useCreateResource(onCreated: (id: string) => void) {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const [blocks, setBlocks] = useState<ResourceBlock[]>([])
  const form = useForm<ResourceCreateValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', description: '' },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createResource({
        name: values.name,
        content: { description: values.description, blocks },
      })
      onCreated(created.id)
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
    }
  })

  return { form, blocks, setBlocks, onSubmit, saveError }
}
