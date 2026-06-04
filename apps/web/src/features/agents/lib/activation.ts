import type { AgentMissing } from '@/api/types'

/**
 * Klartext-Labels fuer die `missing`-Codes aus `AgentRead.missing`. Genutzt fuer
 * die „fehlt: …"-Anzeige sowie die Tooltips an Aktivieren-/Kopieren-Buttons.
 */
const MISSING_LABELS: Record<AgentMissing, string> = {
  persona: 'Persona verknüpfen',
  template: 'Systemprompt verknüpfen',
  persona_active: 'verknüpfte Persona aktiv schalten',
}

/**
 * Wandelt die `missing`-Codes eines Agenten in lesbare deutsche Labels —
 * unbekannte Codes (kuenftige Backend-Erweiterungen) werden roh durchgereicht.
 */
export function describeAgentMissing(missing: AgentMissing[]): string[] {
  return missing.map((item) => MISSING_LABELS[item] ?? item)
}
