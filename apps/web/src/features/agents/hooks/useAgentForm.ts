import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import { DEFAULT_TOOL_POLICY, type Agent, type AgentToolPolicy } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'

const readScope = z.enum(['all', 'assigned', 'none'])

// Nur der Name ist Pflicht: ein Agent ist jederzeit speicherbar, auch ohne
// Persona/Template. Aktivierbarkeit wird separat (im Editor + Backend) geprueft.
// Die Tool-Policy liegt flach im Formular (RHF-freundlich) und wird beim Submit
// wieder zu einem AgentToolPolicy-Objekt zusammengesetzt.
const editorSchema = z.object({
  name: z.string().min(1, i18n.t('agents:form.nameRequired')),
  description: z.string(),
  persona_id: z.string(),
  system_prompt_template_id: z.string(),
  status: z.enum(['enabled', 'disabled']),
  playbook_read: readScope,
  resource_read: readScope,
  agent_read: readScope,
  persona_read: z.boolean(),
  persona_write: z.boolean(),
  playbook_write: z.boolean(),
  resource_write: z.boolean(),
  agent_write: z.boolean(),
  system_prompt_write: z.boolean(),
  feedback_write: z.boolean(),
  promote_retire: z.boolean(),
  // ADR-0039 Tag-Scope: kommaseparierte erlaubte Tags je Domain (leer = alle).
  write_tags_persona: z.string(),
  write_tags_playbook: z.string(),
  write_tags_resource: z.string(),
})

export type AgentEditorValues = z.infer<typeof editorSchema>

const TAG_DOMAINS = ['persona', 'playbook', 'resource'] as const

function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
}

function tagFieldsFromPolicy(policy: AgentToolPolicy): Record<string, string> {
  return {
    write_tags_persona: (policy.write_tags?.persona ?? []).join(', '),
    write_tags_playbook: (policy.write_tags?.playbook ?? []).join(', '),
    write_tags_resource: (policy.write_tags?.resource ?? []).join(', '),
  }
}

// `base` erhaelt Policy-Felder, die das Formular (noch) nicht editiert
// (z. B. transition_grants/write_tags, ADR-0039). Der PUT ersetzt die Policy
// ganz — ohne diesen Merge wuerden sie beim Speichern stillschweigend geloescht.
function valuesToPolicy(values: AgentEditorValues, base: AgentToolPolicy): AgentToolPolicy {
  return {
    ...base,
    playbook_read: values.playbook_read,
    resource_read: values.resource_read,
    agent_read: values.agent_read,
    persona_read: values.persona_read,
    persona_write: values.persona_write,
    playbook_write: values.playbook_write,
    resource_write: values.resource_write,
    agent_write: values.agent_write,
    system_prompt_write: values.system_prompt_write,
    feedback_write: values.feedback_write,
    promote_retire: values.promote_retire,
    write_tags: buildWriteTags(values),
  }
}

// Baut das write_tags-Dict aus den drei Tag-Feldern; nur Domains mit Tags
// erscheinen (leer = keine Einschraenkung). Ersetzt bewusst base.write_tags,
// da das Formular dieses Feld nun verwaltet.
function buildWriteTags(values: AgentEditorValues): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const domain of TAG_DOMAINS) {
    const tags = parseTags(values[`write_tags_${domain}` as keyof AgentEditorValues] as string)
    if (tags.length > 0) out[domain] = tags
  }
  return out
}

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
      ...DEFAULT_TOOL_POLICY,
      ...tagFieldsFromPolicy(DEFAULT_TOOL_POLICY),
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
        ...agent.tool_policy,
        ...tagFieldsFromPolicy(agent.tool_policy),
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
        tool_policy: valuesToPolicy(values, agent.tool_policy),
      })
      notify.success(i18n.t('agents:toast.saved'))
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
