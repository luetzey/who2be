import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ExternalTool, ExternalToolInput, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import {
  useAutoSaveDraft,
  type UseAutoSaveDraftResult,
} from '@/hooks/useAutoSaveDraft'

// `usageNotesBlocks` traegt das BlockNote-Dokument fuer `content.usage_notes`
// (ein stringifiziertes BlockNote-JSON-Dokument, wie `PlaybookContent.body` —
// siehe `ExternalToolContent` in packages/models). `toInput` serialisiert es
// via JSON.stringify (Muster `usePlaybookForm.toInput`).
const schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  displayName: z.string(),
  mcpServerName: z.string(),
  toolNames: z.array(z.string()),
  usageNotesBlocks: z.array(z.custom<ResourceBlock>()),
  fallbackNote: z.string(),
  tags: z.array(z.string()),
})

export type ToolEditorValues = z.infer<typeof schema>

export interface UseToolFormResult {
  form: UseFormReturn<ToolEditorValues>
  autoSave: UseAutoSaveDraftResult
  // Initial-Snapshot der Usage-Notes-Bloecke, direkt vom tool-Prop abgeleitet.
  // `field.value` taugt dafuer nicht, weil form.reset erst nach dem Mount im
  // Effect laeuft (Muster `usePlaybookForm.initialBodyBlocks`).
  initialUsageNotesBlocks: ResourceBlock[]
}

// Track B (Playbook-Muster): `usage_notes` ist immer ein stringifiziertes
// BlockNote-JSON-Dokument; JSON-Parse-Fehler/leerer String fallen auf eine
// leere Block-Liste zurueck.
function deriveInitialBlocks(usageNotes: string): ResourceBlock[] {
  if (usageNotes.trim() === '') return []
  try {
    const parsed = JSON.parse(usageNotes)
    return Array.isArray(parsed) ? (parsed as ResourceBlock[]) : []
  } catch {
    return []
  }
}

function toInput(values: ToolEditorValues): ExternalToolInput {
  return {
    name: values.name,
    content: {
      display_name: values.displayName,
      mcp_server_name: values.mcpServerName,
      tool_names: values.toolNames,
      usage_notes: JSON.stringify(values.usageNotesBlocks),
      fallback_note: values.fallbackNote.trim() === '' ? null : values.fallbackNote,
      tags: values.tags,
    },
  }
}

export function useToolForm(
  tool: ExternalTool | null,
  onSaved?: () => void,
): UseToolFormResult {
  const api = useApi()
  const form = useForm<ToolEditorValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      displayName: '',
      mcpServerName: '',
      toolNames: [],
      usageNotesBlocks: [],
      fallbackNote: '',
      tags: [],
    },
  })
  // Siehe `usePersonaForm` — `formReady` verhindert das Default-Snapshot-Race.
  const [formReady, setFormReady] = useState(false)
  const resetIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (tool === null || resetIdRef.current === tool.id) {
      return
    }
    form.reset({
      name: tool.name,
      displayName: tool.content.display_name,
      mcpServerName: tool.content.mcp_server_name,
      toolNames: tool.content.tool_names,
      usageNotesBlocks: deriveInitialBlocks(tool.content.usage_notes),
      fallbackNote: tool.content.fallback_note ?? '',
      tags: tool.content.tags,
    })
    resetIdRef.current = tool.id
    setFormReady(true)
  }, [tool, form])

  const values = form.watch()
  const combined: ExternalToolInput = toInput(values)
  const autoSave = useAutoSaveDraft<ExternalToolInput>({
    values: combined,
    isReady: tool !== null && formReady,
    patchFn: async (next) => {
      if (tool === null) {
        return
      }
      await api.patchExternalToolDraft(tool.id, next)
    },
    onSaved,
  })

  const initialUsageNotesBlocks = useMemo(
    () => (tool !== null ? deriveInitialBlocks(tool.content.usage_notes) : []),
    [tool],
  )

  return { form, autoSave, initialUsageNotesBlocks }
}
