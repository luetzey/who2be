import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Create ist immer erlaubt (kein Status-Gate). `name` ist die einzige
// clientseitige Pflicht. Schema spiegelt `useToolForm`, damit
// `ToolEditorForm` mit beiden Hooks funktioniert (Muster `useCreateResource`).
const createSchema = z.object({
  name: z.string().min(1, 'Name ist erforderlich.'),
  displayName: z.string(),
  mcpServerName: z.string(),
  toolNames: z.array(z.string()),
  usageNotesBlocks: z.array(z.custom<ResourceBlock>()),
  fallbackNote: z.string(),
  tags: z.array(z.string()),
})

export type ToolCreateValues = z.infer<typeof createSchema>

export interface UseCreateToolResult {
  form: UseFormReturn<ToolCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreateTool(
  onCreated: (id: string) => void,
  // Content-i18n (ADR-0027): gewaehlte Sprachvarianten (mind. eine), Default ['de'].
  locales: string[] = ['de'],
): UseCreateToolResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<ToolCreateValues>({
    resolver: zodResolver(createSchema),
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

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createExternalTool({
        name: values.name,
        content: {
          display_name: values.displayName,
          mcp_server_name: values.mcpServerName,
          tool_names: values.toolNames,
          usage_notes: JSON.stringify(values.usageNotesBlocks),
          fallback_note: values.fallbackNote.trim() === '' ? null : values.fallbackNote,
          tags: values.tags,
        },
        locales,
      })
      notify.success('Externes Tool angelegt.')
      onCreated(created.id)
    } catch (cause: unknown) {
      setSaveError(cause instanceof Error ? cause.message : 'Anlegen fehlgeschlagen.')
    }
  })

  return { form, onSubmit, saveError }
}
