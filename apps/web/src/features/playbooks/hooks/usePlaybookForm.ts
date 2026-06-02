import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type {
  Playbook,
  PlaybookInput,
  PlaybookType,
  ResourceBlock,
  SystemPromptBodyFormat,
} from '@/api/types'
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
  // `bodyBlocks` traegt entweder Legacy-Plain-Paragraphen ('plain') oder das
  // BlockNote-Dokument mit Inline-Pills ('blocknote'). Die Serialisierung im
  // `toInput` haengt am `body_format`.
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
  body_format: z.enum(['plain', 'blocknote']),
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

// `body_format` aus playbook.content lesen (Default 'plain' fuer alte
// Versions/Responses, die das Feld nicht garantieren).
function readBodyFormat(content: Playbook['content']): SystemPromptBodyFormat {
  return content.body_format === 'blocknote' ? 'blocknote' : 'plain'
}

// Initial-Bloecke fuer den Editor: blocknote → JSON.parse(body); plain →
// plainTextToBlocks (Legacy). JSON-Parse-Fehler fallen auf leer zurueck.
function deriveInitialBlocks(content: Playbook['content']): ResourceBlock[] {
  if (readBodyFormat(content) === 'blocknote') {
    if (content.body.trim() === '') return []
    try {
      return JSON.parse(content.body) as ResourceBlock[]
    } catch {
      return []
    }
  }
  return plainTextToBlocks(content.body)
}

function toInput(values: PlaybookEditorValues): PlaybookInput {
  // blocknote → JSON.stringify(blocks) (Pills bleiben erhalten); plain →
  // Legacy-Plain-Text-Snapshot.
  const body =
    values.body_format === 'blocknote'
      ? JSON.stringify(values.bodyBlocks)
      : blocksToPlainText(values.bodyBlocks)
  return {
    name: values.name,
    content: {
      description: values.description,
      body,
      type: values.type,
      tags: values.tags,
      triggers: joinTriggers(values.triggers),
      body_format: values.body_format,
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
  // Initial-Body-Format aus dem playbook-Prop. Form-State traegt diesen Wert
  // erst NACH dem ersten Mount (form.reset im Effect) — die Editor-Branch-
  // Auswahl im PlaybookEditorForm muss aber schon im ersten Render stimmen,
  // sonst landet ein blocknote-Body mit Placeholder-Pills im default-
  // schema-ResourceEditor und stuerzt mit "node type placeholder not found"
  // ab.
  initialBodyFormat: SystemPromptBodyFormat
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
      body_format: 'plain',
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
        bodyBlocks: deriveInitialBlocks(playbook.content),
        tags: playbook.content.tags,
        triggers: splitTriggers(playbook.content.triggers ?? null),
        body_format: readBodyFormat(playbook.content),
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
    () => (playbook !== null ? deriveInitialBlocks(playbook.content) : []),
    [playbook],
  )
  const initialBodyFormat: SystemPromptBodyFormat =
    playbook !== null ? readBodyFormat(playbook.content) : 'plain'

  return { form, autoSave, initialBodyBlocks, initialBodyFormat }
}

export { PLAYBOOK_TYPES }
