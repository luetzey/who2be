import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.string().min(1, 'Typ erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  body: z.string().min(1, 'Inhalt erforderlich.'),
  tags: z.string(),
  triggers: z.string(),
})

export type PlaybookCreateValues = z.infer<typeof createSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseCreatePlaybookResult {
  form: UseFormReturn<PlaybookCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreatePlaybook(onCreated: (id: string) => void): UseCreatePlaybookResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PlaybookCreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: '',
      type: 'workflow',
      description: '',
      body: '',
      tags: '',
      triggers: '',
    },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createPlaybook({
        name: values.name,
        content: {
          description: values.description,
          body: values.body,
          type: values.type,
          tags: splitList(values.tags),
          triggers: values.triggers.trim() === '' ? null : values.triggers.trim(),
        },
      })
      notify.success('Playbook angelegt.')
      onCreated(created.id)
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
