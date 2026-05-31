import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { SystemPromptBodyFormat, SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  body: z.string().min(1, 'Body erforderlich.'),
  // body_format wird nicht via RHF-Validierung erzwungen — der Default 'blocknote'
  // ist immer gueltig. BlockNote-Save setzt diesen Wert direkt vor dem Submit.
  body_format: z.enum(['plain', 'blocknote']),
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
    defaultValues: {
      name: '',
      description: '',
      body: '',
      body_format: 'blocknote' as SystemPromptBodyFormat,
    },
  })

  useEffect(() => {
    if (template !== null) {
      form.reset({
        name: template.name,
        description: template.content.description,
        body: template.content.body,
        // Fehlende body_format (Legacy-Templates vor Welle 5) → 'plain'.
        // body_format lebt seit Welle 5 auf Template-Top-Level (siehe types.ts).
        body_format: template.body_format ?? 'plain',
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
        body_format: values.body_format,
        content: {
          description: values.description,
          body: values.body,
        },
      })
      notify.success('Gespeichert — neue Version erstellt.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
