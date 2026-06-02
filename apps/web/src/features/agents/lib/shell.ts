import type { Agent } from '@/api/types'

/**
 * Unvollstaendige Huelle: Persona ODER Template fehlt. Eine Huelle ist nicht
 * render- und nicht kopierbar (Backend antwortet 409). Spiegelt die
 * `AgentRead.is_shell`-Logik aus dem Backend.
 */
export function isAgentShell(
  agent: Pick<Agent, 'persona_id' | 'system_prompt_template_id'>,
): boolean {
  return agent.persona_id === null || agent.system_prompt_template_id === null
}
