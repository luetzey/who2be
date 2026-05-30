import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  body: z.string().min(1, 'Body erforderlich.'),
})

export type SystemPromptEditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseSystemPromptFormResult {
  form: UseFormReturn<SystemPromptEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useSystemPromptForm(
  template: SystemPromptTemplate | null,
  onSaved: () => void,
): UseSystemPromptFormResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<SystemPromptEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: { name: '', description: '', body: '' },
  })

  useEffect(() => {
    if (template !== null) {
      form.reset({
        name: template.name,
        description: template.content.description,
        body: template.content.body,
      })
    }
  }, [template, form])

  const onSubmit = form.handleSubmit(async (values) => {
    if (template === null) {
      return
    }
    setSaveError(null)
    try {
      await api.updateSystemPromptTemplate(template.id, {
        name: values.name,
        content: { description: values.description, body: values.body },
      })
      notify.success('Gespeichert — neue Version erstellt.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
