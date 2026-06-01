import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

import { blockPlainText } from '../lib/blockText'
import { joinTriggers } from '../lib/triggers'
import { PLAYBOOK_TYPES, type PlaybookEditorValues } from './usePlaybookForm'

// Schema deckt sich bewusst mit `usePlaybookForm` — so kann
// `PlaybookEditorForm` ohne Sonderbehandlung in der Neu-Page genutzt werden.
// `bodyBlocks`/`tags`/`triggers` sind Passthrough; das Backend persistiert
// einen Plain-Text-Body (siehe `blocksToPlainText`).
const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.enum(PLAYBOOK_TYPES),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
  triggers: z.array(z.string()),
  body_format: z.enum(['plain', 'blocknote']),
})

export type PlaybookCreateValues = PlaybookEditorValues

function blocksToPlainText(blocks: ResourceBlock[]): string {
  return blocks
    .map((block) => blockPlainText(block).trim())
    .filter((text) => text.length > 0)
    .join('\n\n')
}

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseCreatePlaybookResult {
  form: UseFormReturn<PlaybookEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreatePlaybook(onCreated: (id: string) => void): UseCreatePlaybookResult {
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
      body_format: 'plain',
    },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const body =
        values.body_format === 'blocknote'
          ? JSON.stringify(values.bodyBlocks)
          : blocksToPlainText(values.bodyBlocks)
      const created = await api.createPlaybook({
        name: values.name,
        content: {
          description: values.description,
          body,
          type: values.type,
          tags: values.tags,
          triggers: joinTriggers(values.triggers),
          body_format: values.body_format,
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
