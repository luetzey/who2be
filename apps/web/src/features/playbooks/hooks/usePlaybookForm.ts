import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Playbook, PlaybookInput, PlaybookType, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import {
  useAutoSaveDraft,
  type UseAutoSaveDraftResult,
} from '@/hooks/useAutoSaveDraft'

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

// Backend persistiert `body: str`. Bis das Schema in einem Folge-Plan auf
// `body_blocks` migriert wurde, serialisieren wir die BlockNote-Bloecke
// beim Save als Plain-Text-Snapshot (Blockwise mit `\n\n` getrennt).
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

function toInput(values: PlaybookEditorValues): PlaybookInput {
  return {
    name: values.name,
    content: {
      description: values.description,
      body: blocksToPlainText(values.bodyBlocks),
      type: values.type,
      tags: values.tags,
      triggers: joinTriggers(values.triggers),
    },
  }
}

export interface UsePlaybookFormResult {
  form: UseFormReturn<PlaybookEditorValues>
  autoSave: UseAutoSaveDraftResult
  // Initial-Snapshot der Body-Bloecke, direkt vom playbook-Prop abgeleitet.
  // `field.value` taugt dafuer nicht, weil form.reset erst nach dem Mount
  // im Effect laeuft.
  initialBodyBlocks: ResourceBlock[]
}

/**
 * Editor-Form fuer Playbook-Auto-Save. Resettet auf Playbook-Aenderung,
 * leitet `form.watch`-Werte in `useAutoSaveDraft` (PATCH `.../draft`).
 *
 * `onSaved` triggert die Page nach erfolgreichem PATCH zum Refetch (Status/
 * Version live aktualisieren). Subsequent-Reloads derselben Playbook-ID
 * resetten den Form-State nicht, damit User-Edits nicht ueberschrieben werden.
 */
export function usePlaybookForm(
  playbook: Playbook | null,
  onSaved?: () => void,
): UsePlaybookFormResult {
  const api = useApi()
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

  // Siehe `usePersonaForm` — `formReady` verhindert das Default-Snapshot-Race.
  const [formReady, setFormReady] = useState(false)
  const resetIdRef = useRef<string | null>(null)
  useEffect(() => {
    if (playbook !== null && resetIdRef.current !== playbook.id) {
      form.reset({
        name: playbook.name,
        type: coercePlaybookType(playbook.content.type),
        description: playbook.content.description,
        bodyBlocks: plainTextToBlocks(playbook.content.body),
        tags: playbook.content.tags,
        triggers: splitTriggers(playbook.content.triggers ?? null),
      })
      resetIdRef.current = playbook.id
      setFormReady(true)
    }
  }, [playbook, form])

  const values = form.watch()
  const autoSave = useAutoSaveDraft<PlaybookEditorValues>({
    values,
    isReady: playbook !== null && formReady,
    patchFn: async (next) => {
      if (playbook === null) {
        return
      }
      await api.patchPlaybookDraft(playbook.id, toInput(next))
    },
    onSaved,
  })

  const initialBodyBlocks = useMemo(
    () => (playbook !== null ? plainTextToBlocks(playbook.content.body) : []),
    [playbook],
  )

  return { form, autoSave, initialBodyBlocks }
}

export { PLAYBOOK_TYPES }
