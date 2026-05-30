import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useMemo, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Playbook, PlaybookType, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

import { blockPlainText } from '../lib/blockText'
import { joinTriggers, splitTriggers } from '../lib/triggers'

const PLAYBOOK_TYPES = [
  'prompt',
  'instructions',
  'snippet',
  'workflow',
  'checklist',
  'faq',
] as const satisfies readonly PlaybookType[]

// `bodyBlocks` und `tags` kommen als Passthrough-Felder ins Schema
// — Zod ruft sie nur durch, validiert aber Name/Typ/Description.
const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  type: z.enum(PLAYBOOK_TYPES),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  triggers: z.array(z.string()),
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
})

export type PlaybookEditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

// Backend persistiert `body: str`. Bis das Schema in einem Folge-Plan auf
// `body_blocks` migriert wurde, serialisieren wir die BlockNote-Bloecke
// beim Submit als Plain-Text-Snapshot (Blockwise mit `\n\n` getrennt).
function blocksToPlainText(blocks: ResourceBlock[]): string {
  return blocks
    .map((block) => blockPlainText(block).trim())
    .filter((text) => text.length > 0)
    .join('\n\n')
}

// Reverse: vorhandener `body`-String wird in Paragraphen-Bloecke zerlegt,
// damit der Editor etwas zum Anzeigen hat. Verlustbehaftet (Formatierung
// geht verloren), aber stabil und deterministisch.
function plainTextToBlocks(body: string): ResourceBlock[] {
  if (body.trim() === '') {
    return []
  }
  return body.split(/\n\n+/).map((paragraph, index) => ({
    id: `playbook-body-${index}`,
    type: 'paragraph',
    content: [{ type: 'text', text: paragraph, styles: {} }],
  }))
}

function coercePlaybookType(value: string): PlaybookType {
  return (PLAYBOOK_TYPES as readonly string[]).includes(value)
    ? (value as PlaybookType)
    : 'workflow'
}

export interface UsePlaybookFormResult {
  form: UseFormReturn<PlaybookEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
  // Initial-Snapshot der Body-Bloecke, direkt vom playbook-Prop abgeleitet.
  // Wird als `initialBlocks` an die BlockNote-Insel gereicht — `field.value`
  // taugt dafuer nicht, weil form.reset erst nach dem Mount im Effect laeuft.
  initialBodyBlocks: ResourceBlock[]
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
      bodyBlocks: [],
      tags: [],
      triggers: [],
    },
  })

  useEffect(() => {
    if (playbook !== null) {
      form.reset({
        name: playbook.name,
        type: coercePlaybookType(playbook.content.type),
        description: playbook.content.description,
        bodyBlocks: plainTextToBlocks(playbook.content.body),
        tags: playbook.content.tags,
        triggers: splitTriggers(playbook.content.triggers ?? null),
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
          body: blocksToPlainText(values.bodyBlocks),
          type: values.type,
          tags: values.tags,
          triggers: joinTriggers(values.triggers),
        },
      })
      notify.success('Gespeichert — neue Version erstellt.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  const initialBodyBlocks = useMemo(
    () => (playbook !== null ? plainTextToBlocks(playbook.content.body) : []),
    [playbook],
  )

  return { form, onSubmit, saveError, initialBodyBlocks }
}

export { PLAYBOOK_TYPES }
