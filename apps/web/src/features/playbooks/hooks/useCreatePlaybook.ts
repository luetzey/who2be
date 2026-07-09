import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

import { joinTriggers } from '@/lib/triggers'
import { PLAYBOOK_TYPES, type PlaybookEditorValues } from './usePlaybookForm'

// Schema deckt sich bewusst mit `usePlaybookForm` — so kann
// `PlaybookEditorForm` ohne Sonderbehandlung in der Neu-Page genutzt werden.
// `bodyBlocks`/`tags`/`triggers` sind Passthrough; Track B (Nur-BlockNote):
// der Body wird als stringifiziertes BlockNote-Dokument persistiert.
const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.enum(PLAYBOOK_TYPES),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
  triggers: z.array(z.string()),
})

export type PlaybookCreateValues = PlaybookEditorValues

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseCreatePlaybookResult {
  form: UseFormReturn<PlaybookEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreatePlaybook(
  onCreated: (id: string) => void,
  // Content-i18n (ADR-0027): gewaehlte Sprachvarianten (mind. eine), Default ['de'].
  locales: string[] = ['de'],
): UseCreatePlaybookResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PlaybookEditorValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: '',
      type: 'workflow',
      description: '',
      bodyBlocks: [],
      tags: [],
      triggers: [],
    },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createPlaybook({
        name: values.name,
        content: {
          description: values.description,
          body: JSON.stringify(values.bodyBlocks),
          type: values.type,
          tags: values.tags,
          triggers: joinTriggers(values.triggers),
        },
        locales,
      })
      notify.success('Playbook angelegt.')
      onCreated(created.id)
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
