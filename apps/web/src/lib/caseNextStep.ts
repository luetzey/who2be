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
  // Phase E (E-Delta §6.3): Links, keine Uebergaenge.
  | 'prepareSession'
  | 'toMeasure'
  | 'toFollowUp'

/** Aktionen, die nur navigieren und nie einen Status setzen. */
export const LINK_ACTIONS: ReadonlySet<CaseAction> = new Set<CaseAction>([
  'toVersion',
  'prepareSession',
  'toMeasure',
  'toFollowUp',
])

/**
 * Die Aenderung (Massnahme), auf die der Fall zeigt, wie der Server sie
 * liefert. `open` = Server-Zustand nicht abgeschlossen (weder eingestuft
 * noch zurueckgezogen); `null` = keine bekannte Aenderung.
 */
export interface CaseMeasureRef {
  sessionId: string
  measureId: string
  open: boolean
}

export interface NextStep {
  /** Hauptaktion (`brand`, bei Links ausser `prepareSession` `default`); `null` = keine. */
  primary: CaseAction | null
  /** Status-Menue (`outline`), in Anzeigereihenfolge. */
  menu: CaseAction[]
  /** Nicht klickbarer Hinweis statt „Als geändert markieren…“. */
  addressUnavailable: boolean
}

/**
 * Waehlt die Aenderung, auf die „Zur Änderung“ bzw. „Zur Nachkontrolle“
 * zeigen. `known` sind nur Aenderungen, die der Server diesem Fall zuordnet
 * (in Reihenfolge der Review-Liste); `eventMeasureIds` die `measure_id` der
 * Fall-Ereignisse, neueste zuerst. Bei `verified` gilt die Aenderung des
 * juengsten Ereignisses (die, die gewirkt hat); sonst zuerst eine offene,
 * innerhalb dessen die juengst im Verlauf genannte. Rein, ohne Netz.
 */
export function pickCaseMeasure(
  status: CaseStatus,
  eventMeasureIds: readonly string[],
  known: readonly CaseMeasureRef[],
): CaseMeasureRef | null {
  if (known.length === 0) return null
  const rank = (ref: CaseMeasureRef) => {
    const index = eventMeasureIds.indexOf(ref.measureId)
    return index === -1 ? Number.MAX_SAFE_INTEGER : index
  }
  const byEvent = known
    .map((ref, index) => ({ ref, index }))
    .sort((a, b) => rank(a.ref) - rank(b.ref) || a.index - b.index)
    .map(({ ref }) => ref)
  if (status === 'verified') return byEvent[0]
  return byEvent.find((ref) => ref.open) ?? byEvent[0]
}

/**
 * „Nächster Schritt“ (Spec S8 fuer D, E-Delta §6.3 fuer E). Hoechstens eine
 * Hauptaktion je Zustand. Kein Eintrag setzt `in_progress` oder `verified`:
 * beides macht nur der Server (W-E2 a, ADR-0053 3.6).
 *
 * „Als geändert markieren…“ (`address`) steht nie als Hauptaktion da, nur im
 * Menue (E-Delta §6.3 Fussnote ¹, QE7 a, PM-8), und nur mit versioniertem
 * Baustein; sonst ein Hinweis.
 *
 * Abweichungen mit Beleg (Plan D6d): Bei `dismissed` gibt es kein „Wieder
 * öffnen…“, weil der Server die Kante nicht kennt (ADR-0053 3.3,
 * `case_service._EDGES`). Ist „Modellgrenze“ zugeordnet, ist „Verwerfen…“
 * die Hauptaktion (Spec S8 „Zuordnen“); der Rest der Zeile wandert ins
 * Menue. Ohne bekannte Aenderung entfallen „Zur Änderung“/„Zur
 * Nachkontrolle“, statt ins Leere zu fuehren.
 */
export function nextStep(
  status: CaseStatus,
  elements: readonly CaseElement[],
  hasTestCase: boolean,
  measure: CaseMeasureRef | null = null,
): NextStep {
  const assigned = elements.length > 0
  const modelLimit = elements.some((element) => element.target === 'model_limit')
  const canAddress = versionedElements(elements).length > 0
  const address: CaseAction[] = canAddress ? ['address'] : []
  let row: CaseAction[]
  let addressUnavailable = false
  switch (status) {
    case 'open':
    case 'reopened':
      row = assigned ? ['triage', 'changeAssignment', 'dismiss'] : ['assign', 'dismiss']
      break
    case 'triaged':
      addressUnavailable = !canAddress
      row = hasTestCase
        ? ['prepareSession', ...address, 'changeAssignment', 'dismiss']
        : ['createTestCase', 'prepareSession', ...address, 'changeAssignment', 'dismiss']
      break
    case 'in_progress':
      return {
        primary: measure !== null ? 'toMeasure' : null,
        menu: [...address, 'dismiss'],
        addressUnavailable: !canAddress,
      }
    case 'addressed':
      return {
        primary: measure?.open === true ? 'toFollowUp' : 'toVersion',
        menu: ['reopen'],
        addressUnavailable: false,
      }
    case 'verified':
      return { primary: measure !== null ? 'toFollowUp' : null, menu: [], addressUnavailable: false }
    default:
      // `dismissed`: Endzustand.
      return { primary: null, menu: [], addressUnavailable: false }
  }
  if (modelLimit) {
    return { primary: 'dismiss', menu: row.filter((action) => action !== 'dismiss'), addressUnavailable }
  }
  const [primary, ...menu] = row
  return { primary, menu, addressUnavailable }
}
