import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import { DEFAULT_TOOL_POLICY, type Agent, type AgentToolPolicy } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'
import { notify } from '@/lib/feedback'

const readScope = z.enum(['all', 'assigned', 'none'])
// ADR-0044 — Agent-Memory-Policy (Speicher-Modus + Verbindlichkeit der
// Abfrage-Anweisung im System-Prompt).
const memoryMode = z.enum(['off', 'read_only', 'suggest', 'auto'])
const memoryDirective = z.enum(['required', 'recommended'])

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
  external_tool_read: readScope,
  persona_read: z.boolean(),
  persona_write: z.boolean(),
  playbook_write: z.boolean(),
  resource_write: z.boolean(),
  agent_write: z.boolean(),
  system_prompt_write: z.boolean(),
  external_tool_write: z.boolean(),
  feedback_write: z.boolean(),
  feedback_resolve: z.boolean(),
  promote_retire: z.boolean(),
  // ADR-0047 Arbeitsbereich + Knowledge Base. `kb_edge_write` ist bewusst ein
  // eigenes Recht: Kanten sind im MVP nicht loeschbar.
  workarea_write: z.boolean(),
  kb_write: z.boolean(),
  kb_edge_write: z.boolean(),
  // ADR-0039 Tag-Scope: erlaubte Tags je Domain als Liste (leer = alle). Als
  // string[] gefuehrt, damit der TagInput (Pills + Vorschlaege) direkt bindet.
  write_tags_persona: z.array(z.string()),
  write_tags_playbook: z.array(z.string()),
  write_tags_resource: z.array(z.string()),
  // ADR-0039 Transition-Grants: per-Domain Promote/Retire (nur mit promote_retire
  // wirksam). Beide an = ungeteilt (kein Eintrag); ein abgewaehlter Haken
  // schraenkt die Richtung in der Domain ein.
  tg_persona_promote: z.boolean(),
  tg_persona_retire: z.boolean(),
  tg_playbook_promote: z.boolean(),
  tg_playbook_retire: z.boolean(),
  tg_resource_promote: z.boolean(),
  tg_resource_retire: z.boolean(),
  // ADR-0039 Write-Rate-Limit: Mutationen/Minute als String (leer = unbegrenzt).
  write_rate_limit: z.string(),
  // ADR-0044 Agent-Memory.
  memory_mode: memoryMode,
  memory_directive: memoryDirective,
  // ADR-0047 Modell-Config (betreiber-gepflegt, kein Policy-Feld). Leerer
  // String ist ein gueltiger Wert und bedeutet beim Submit "explizit leeren"
  // — siehe `AgentUpdateInput`. Laengen prueft der Server (100/200).
  model_provider: z.string(),
  model_name: z.string(),
})

export type AgentEditorValues = z.infer<typeof editorSchema>

const TAG_DOMAINS = ['persona', 'playbook', 'resource'] as const

function tagFieldsFromPolicy(policy: AgentToolPolicy): Record<string, string[]> {
  return {
    write_tags_persona: policy.write_tags?.persona ?? [],
    write_tags_playbook: policy.write_tags?.playbook ?? [],
    write_tags_resource: policy.write_tags?.resource ?? [],
  }
}

// Fehlt ein Domain-Eintrag, gilt das ungeteilte promote_retire → beide Haken an.
function transitionFieldsFromPolicy(policy: AgentToolPolicy): Record<string, boolean> {
  const out: Record<string, boolean> = {}
  for (const domain of TAG_DOMAINS) {
    const grant = policy.transition_grants?.[domain]
    out[`tg_${domain}_promote`] = grant ? grant.promote : true
    out[`tg_${domain}_retire`] = grant ? grant.retire : true
  }
  return out
}

// Nur Domains mit einer Einschraenkung (nicht beide an) erhalten einen Eintrag.
function buildTransitionGrants(
  values: AgentEditorValues,
): Record<string, { promote: boolean; retire: boolean }> {
  const out: Record<string, { promote: boolean; retire: boolean }> = {}
  for (const domain of TAG_DOMAINS) {
    const promote = values[`tg_${domain}_promote` as keyof AgentEditorValues] as boolean
    const retire = values[`tg_${domain}_retire` as keyof AgentEditorValues] as boolean
    if (!(promote && retire)) out[domain] = { promote, retire }
  }
  return out
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
    external_tool_read: values.external_tool_read,
    persona_read: values.persona_read,
    persona_write: values.persona_write,
    playbook_write: values.playbook_write,
    resource_write: values.resource_write,
    agent_write: values.agent_write,
    system_prompt_write: values.system_prompt_write,
    external_tool_write: values.external_tool_write,
    feedback_write: values.feedback_write,
    feedback_resolve: values.feedback_resolve,
    promote_retire: values.promote_retire,
    workarea_write: values.workarea_write,
    kb_write: values.kb_write,
    kb_edge_write: values.kb_edge_write,
    write_tags: buildWriteTags(values),
    transition_grants: buildTransitionGrants(values),
    write_rate_limit: values.write_rate_limit.trim() === '' ? null : Number(values.write_rate_limit),
    memory_mode: values.memory_mode,
    memory_directive: values.memory_directive,
  }
}

// Baut das write_tags-Dict aus den drei Tag-Feldern; nur Domains mit Tags
// erscheinen (leer = keine Einschraenkung). Ersetzt bewusst base.write_tags,
// da das Formular dieses Feld nun verwaltet.
function buildWriteTags(values: AgentEditorValues): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const domain of TAG_DOMAINS) {
    const tags = values[`write_tags_${domain}` as keyof AgentEditorValues] as string[]
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
      ...transitionFieldsFromPolicy(DEFAULT_TOOL_POLICY),
      write_rate_limit: '',
      // Modell-Config liegt am Agenten, nicht in der Policy — daher kein
      // Spread-Treffer. Leer = "nicht hinterlegt".
      model_provider: '',
      model_name: '',
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
        // Der flache Spread traegt workarea_write/kb_write/kb_edge_write
        // bereits mit: sie sind in `AgentToolPolicy` NICHT optional, weil der
        // Server die Policy immer ueber das Pydantic-Modell serialisiert (eine
        // Bestands-JSONB ohne die Keys deserialisiert zum Default `false` und
        // kommt mit Keys zurueck). Deshalb kein `??`-Fallback wie unten bei
        // memory_* — dort ist das Feld im TS-Typ optional.
        ...agent.tool_policy,
        ...tagFieldsFromPolicy(agent.tool_policy),
        ...transitionFieldsFromPolicy(agent.tool_policy),
        write_rate_limit:
          agent.tool_policy.write_rate_limit != null
            ? String(agent.tool_policy.write_rate_limit)
            : '',
        // Fallback fuer Bestands-Policies ohne diese Felder (JSONB-abwaerts-
        // kompatibel, siehe DEFAULT_TOOL_POLICY).
        memory_mode: agent.tool_policy.memory_mode ?? 'off',
        memory_directive: agent.tool_policy.memory_directive ?? 'recommended',
        // ADR-0047: `null` (nicht hinterlegt) wird zum leeren Eingabefeld.
        model_provider: agent.model_provider ?? '',
        model_name: agent.model_name ?? '',
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
        // ADR-0047: IMMER mitsenden — anders als die Refs oben ist der leere
        // String hier kein "nicht gesetzt", sondern die explizite Anweisung
        // "auf NULL leeren". Wuerde man das Feld bei leerem Wert weglassen,
        // liesse sich ein falsch eingetragener Anbieter nie mehr entfernen und
        // die Compliance-Auskunft bliebe dauerhaft verfaelscht.
        model_provider: values.model_provider.trim(),
        model_name: values.model_name.trim(),
      })
      notify.success(i18n.t('agents:toast.saved'))
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
