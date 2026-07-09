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

import { joinTriggers, splitTriggers } from '@/lib/triggers'

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
  // `bodyBlocks` traegt das BlockNote-Dokument mit Inline-Pills (Track B:
  // immer BlockNote). `toInput` serialisiert es via JSON.stringify.
  bodyBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
})

export type PlaybookEditorValues = z.infer<typeof editorSchema>

function coercePlaybookType(value: string): PlaybookType {
  return (PLAYBOOK_TYPES as readonly string[]).includes(value)
    ? (value as PlaybookType)
    : 'workflow'
}

// Initial-Bloecke fuer den Editor: Track B — `body` ist immer ein
// stringifiziertes BlockNote-JSON-Dokument; JSON-Parse-Fehler/leerer Body
// fallen auf eine leere Block-Liste zurueck.
function deriveInitialBlocks(content: Playbook['content']): ResourceBlock[] {
  if (content.body.trim() === '') return []
  try {
    const parsed = JSON.parse(content.body)
    return Array.isArray(parsed) ? (parsed as ResourceBlock[]) : []
  } catch {
    return []
  }
}

function toInput(values: PlaybookEditorValues): PlaybookInput {
  return {
    name: values.name,
    content: {
      description: values.description,
      body: JSON.stringify(values.bodyBlocks),
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
        bodyBlocks: deriveInitialBlocks(playbook.content),
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
    () => (playbook !== null ? deriveInitialBlocks(playbook.content) : []),
    [playbook],
  )

  return { form, autoSave, initialBodyBlocks }
}

export { PLAYBOOK_TYPES }
