import { useCallback, useEffect, useState } from 'react'

import type {
  Agent,
  Persona,
  Playbook,
  SystemPromptTemplate,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : i18n.t('agents:toast.unknownError')
}

export interface UseAgentResult {
  agent: Agent | null
  persona: Persona | null
  template: SystemPromptTemplate | null
  playbooks: Playbook[]
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Laedt einen Agent + die referenzierte Persona/Template und alle
 * verlinkten Playbooks. Wir bauen den Tree client-seitig (statt ein
 * neues /agents/{id}/expanded-Endpoint einzufuehren) -- das hier ist die
 * einzige Stelle, die diese Verbund-Sicht braucht.
 */
export function useAgent(id: string | undefined): UseAgentResult {
  const api = useApi()
  const [agent, setAgent] = useState<Agent | null>(null)
  const [persona, setPersona] = useState<Persona | null>(null)
  const [template, setTemplate] = useState<SystemPromptTemplate | null>(null)
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [loading, setLoading] = useState(id !== undefined)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (id === undefined) {
      return
    }
    setLoading(true)
    setError(null)
    api
      .getAgent(id)
      .then(async (loadedAgent) => {
        setAgent(loadedAgent)
        // Leere Huelle: Persona/Template (und damit Playbooks) koennen fehlen.
        // Wir laden nur, was verknuepft ist -- sonst trifft die UI /null.
        const [loadedPersona, loadedTemplate, loadedPlaybooks] = await Promise.all([
          loadedAgent.persona_id !== null
            ? api.getPersona(loadedAgent.persona_id)
            : Promise.resolve(null),
          loadedAgent.system_prompt_template_id !== null
            ? api.getSystemPromptTemplate(loadedAgent.system_prompt_template_id)
            : Promise.resolve(null),
          loadedAgent.persona_id !== null
            ? api.listPersonaPlaybooks(loadedAgent.persona_id)
            : Promise.resolve([]),
        ])
        setPersona(loadedPersona)
        setTemplate(loadedTemplate)
        setPlaybooks(loadedPlaybooks)
      })
      .catch((cause: unknown) => setError(describeError(cause)))
      .finally(() => setLoading(false))
  }, [api, id])

  useEffect(load, [load])

  return { agent, persona, template, playbooks, loading, error, reload: load }
}
