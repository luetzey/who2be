import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'

// Nur der Name ist Pflicht: ein Agent ist jederzeit speicherbar, auch ohne
// Persona/Template. Aktivierbarkeit wird separat (im Editor + Backend) geprueft.
const editorSchema = z.object({
  name: z.string().min(1, i18n.t('agents:form.nameRequired')),
  description: z.string(),
  persona_id: z.string(),
  system_prompt_template_id: z.string(),
  status: z.enum(['enabled', 'disabled']),
})

export type AgentEditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('agents:toast.unknownError')
}

export interface UseAgentFormResult {
  form: UseFormReturn<AgentEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useAgentForm(
  agent: Agent | null,
  onSaved: () => void,
): UseAgentFormResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<AgentEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: {
      name: '',
      description: '',
      persona_id: '',
      system_prompt_template_id: '',
      status: 'enabled',
    },
  })

  useEffect(() => {
    if (agent !== null) {
      form.reset({
        name: agent.name,
        description: agent.description,
        // Huelle: null-Refs werden zu leerer Auswahl ("— bitte wählen —").
        persona_id: agent.persona_id ?? '',
        system_prompt_template_id: agent.system_prompt_template_id ?? '',
        status: agent.status,
      })
    }
  }, [agent, form])

  const onSubmit = form.handleSubmit(async (values) => {
    if (agent === null) {
      return
    }
    setSaveError(null)
    try {
      // Leere Auswahl ⇒ Feld weglassen (Backend nutzt COALESCE: unveraendert).
      await api.updateAgent(agent.id, {
        name: values.name,
        description: values.description,
        persona_id: values.persona_id || undefined,
        system_prompt_template_id: values.system_prompt_template_id || undefined,
        status: values.status,
      })
      notify.success(i18n.t('agents:toast.saved'))
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
