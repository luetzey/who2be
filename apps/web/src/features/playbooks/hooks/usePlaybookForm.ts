import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Playbook } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.string().min(1, 'Typ erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  body: z.string().min(1, 'Inhalt erforderlich.'),
  tags: z.string(),
  triggers: z.string(),
})

export type PlaybookEditorValues = z.infer<typeof editorSchema>

function splitList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePlaybookFormResult {
  form: UseFormReturn<PlaybookEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

/**
 * Editor-Form fuer Playbook-Update. Resettet auf Persona-Aenderung,
 * Submit ruft updatePlaybook + Toast + uebergebenes `onSaved`.
 */
export function usePlaybookForm(
  playbook: Playbook | null,
  onSaved: () => void,
): UsePlaybookFormResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PlaybookEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: {
      name: '',
      type: 'workflow',
      description: '',
      body: '',
      tags: '',
      triggers: '',
    },
  })

  useEffect(() => {
    if (playbook !== null) {
      form.reset({
        name: playbook.name,
        type: playbook.content.type,
        description: playbook.content.description,
        body: playbook.content.body,
        tags: playbook.content.tags.join(', '),
        triggers: playbook.content.triggers ?? '',
      })
    }
  }, [playbook, form])

  const onSubmit = form.handleSubmit(async (values) => {
    if (playbook === null) {
      return
    }
    setSaveError(null)
    try {
      await api.updatePlaybook(playbook.id, {
        name: values.name,
        content: {
          description: values.description,
          body: values.body,
          type: values.type,
          tags: splitList(values.tags),
          triggers: values.triggers.trim() === '' ? null : values.triggers.trim(),
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
