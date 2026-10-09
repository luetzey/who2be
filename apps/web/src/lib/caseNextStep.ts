import type { CaseElement, CaseStatus, CaseTarget, VersionedEntityType } from '@/api/types'

const VERSIONED: ReadonlySet<CaseTarget> = new Set<VersionedEntityType>([
  'persona',
  'playbook',
  'resource',
  'external_tool',
  'system_prompt_template',
])

export function isVersionedTarget(target: CaseTarget): target is VersionedEntityType {
  return VERSIONED.has(target)
}

/** Die zugeordneten Elemente, aus denen eine Version waehlbar ist. */
export function versionedElements(elements: readonly CaseElement[]): CaseElement[] {
  return elements.filter((element) => isVersionedTarget(element.target) && element.entity_id !== null)
}

export type CaseAction =
  | 'assign'
  | 'changeAssignment'
  | 'triage'
  | 'createTestCase'
  | 'address'
  | 'toVersion'
  | 'dismiss'
  | 'reopen'

export interface NextStep {
  /** Hauptaktion (`brand`, bei `toVersion` `default`); `null` = keine. */
  primary: CaseAction | null
  /** Status-Menue (`outline`), in Anzeigereihenfolge. */
  menu: CaseAction[]
  /** Nicht klickbarer Hinweis statt „Als umgesetzt markieren…“. */
  addressUnavailable: boolean
}

/**
 * „Nächster Schritt in D“ (Spec S8, Tabelle). Genau eine Hauptaktion je
 * Zustand; `in_progress`/`verified` haben in Phase D keine Aktion (D2a).
 *
 * Zwei Abweichungen mit Beleg (Plan D6d): Bei `dismissed` gibt es kein
 * „Wieder öffnen…“, weil der Server die Kante nicht kennt (ADR-0053 3.3,
 * `case_service._EDGES`). Und ist „Modellgrenze“ zugeordnet, ist
 * „Verwerfen…“ die Hauptaktion (Spec S8 „Zuordnen“); der Rest der Zeile
 * wandert ins Menue.
 */
export function nextStep(
  status: CaseStatus,
  elements: readonly CaseElement[],
  hasTestCase: boolean,
): NextStep {
  const assigned = elements.length > 0
  const modelLimit = elements.some((element) => element.target === 'model_limit')
  const canAddress = versionedElements(elements).length > 0
  let row: CaseAction[]
  let addressUnavailable = false
  switch (status) {
    case 'open':
    case 'reopened':
      row = assigned ? ['triage', 'changeAssignment', 'dismiss'] : ['assign', 'dismiss']
      break
    case 'triaged': {
      const address: CaseAction[] = canAddress ? ['address'] : []
      addressUnavailable = !canAddress
      row = hasTestCase
        ? [...address, 'changeAssignment', 'dismiss']
        : ['createTestCase', ...address, 'changeAssignment', 'dismiss']
      break
    }
    case 'addressed':
      return { primary: 'toVersion', menu: ['reopen'], addressUnavailable: false }
    default:
      // `dismissed` (Endzustand), `in_progress`/`verified` (Phase E).
      return { primary: null, menu: [], addressUnavailable: false }
  }
  if (modelLimit) {
    return { primary: 'dismiss', menu: row.filter((action) => action !== 'dismiss'), addressUnavailable }
  }
  const [primary, ...menu] = row
  return { primary, menu, addressUnavailable }
}
