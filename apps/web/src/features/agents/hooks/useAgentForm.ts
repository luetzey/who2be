import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  persona_id: z.string().min(1, 'Persona erforderlich.'),
  system_prompt_template_id: z.string().min(1, 'Template erforderlich.'),
  status: z.enum(['enabled', 'disabled']),
})

export type AgentEditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
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
        persona_id: agent.persona_id,
        system_prompt_template_id: agent.system_prompt_template_id,
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
      await api.updateAgent(agent.id, {
        name: values.name,
        description: values.description,
        persona_id: values.persona_id,
        system_prompt_template_id: values.system_prompt_template_id,
        status: values.status,
      })
      notify.success('Agent gespeichert.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
