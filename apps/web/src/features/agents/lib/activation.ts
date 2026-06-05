import type { AgentMissing } from '@/api/types'
import i18n from '@/i18n'

/**
 * Klartext-Labels fuer die `missing`-Codes aus `AgentRead.missing`. Genutzt fuer
 * die „fehlt: …"-Anzeige sowie die Tooltips an Aktivieren-/Kopieren-Buttons.
 */
function getMissingLabel(item: AgentMissing): string {
  const key = `agents:form.missing.${item}` as const
  const translated = i18n.t(key)
  // Falls der Key unbekannt ist (kuenftige Backend-Erweiterung), wird der Code roh zurueckgegeben.
  return translated !== key ? translated : item
}

/**
 * Wandelt die `missing`-Codes eines Agenten in lesbare Labels —
 * unbekannte Codes (kuenftige Backend-Erweiterungen) werden roh durchgereicht.
 */
export function describeAgentMissing(missing: AgentMissing[]): string[] {
  return missing.map((item) => getMissingLabel(item))
}
