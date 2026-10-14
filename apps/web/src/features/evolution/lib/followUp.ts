// Nachkontroll-Logik der Weiterentwicklung (ADR-0053 3.6, PM-3; Spec
// Neuschnitt §1, E5-Delta §0.4). Rein und ohne React, damit Review-Ergebnis,
// Agent-Tab, „Zu erledigen“ und Rueckmeldung dasselbe rechnen.
//
// - Zustand einer Aenderung: aus dem juengsten Event abgeleitet, nicht
//   gespeichert. Unbekannte Event-Arten (neuere API) aendern den Zustand
//   nicht; der letzte bekannte gilt, und das Event erscheint im Verlauf als
//   „Aenderung“ (`isKnownMeasureEvent`).
// - Datum der Nachkontrolle: das der Aenderung, sonst das des Protokolls.
// - Faellig: Datum heute oder frueher, im lokalen Kalender des Browsers ohne
//   Uhrzeit, und die Aenderung ist nicht abgeschlossen. „Faellig“ ist kein
//   Zustand, sondern eine berechnete Markierung. Achtung: Der Server rechnet
//   `due` und `due_measure_count` mit dem UTC-Kalendertag; wie die Abweichung zum
//   lokalen Tag aufgeloest wird, ist noch offen.
//
// Nutzertexte stehen nicht hier: Die Funktionen liefern Tokens, die UI
// uebersetzt sie (Keys nach den Begriffen „Aenderung“, „Nachkontrolle“).

import type {
  MeasureEvent,
  MeasureEventKind,
  MeasureRead,
  MeasureState,
  SessionRead,
} from '@/api/types'

const KNOWN_EVENTS: ReadonlySet<string> = new Set<MeasureEventKind>([
  'draft_linked',
  'activated',
  'follow_up_prepared',
  'reviewed',
  'withdrawn',
])

// Abgeschlossen: hier ist nie eine Nachkontrolle faellig (Server
// `MEASURE_CLOSED_STATES`).
const CLOSED_STATES: ReadonlySet<MeasureState> = new Set<MeasureState>([
  'effective',
  'ineffective',
  'not_measurable',
  'withdrawn',
])

// Noch nicht aktiviert: faellig heisst dann „Aenderung noch nicht aktiv“.
const NOT_ACTIVE_STATES: ReadonlySet<MeasureState> = new Set<MeasureState>([
  'agreed',
  'draft_linked',
])

/** Ist die Event-Art dem Web bekannt? Unbekannte zeigt der Verlauf als „Aenderung“. */
export function isKnownMeasureEvent(kind: string): kind is MeasureEventKind {
  return KNOWN_EVENTS.has(kind)
}

/** Abgeschlossener Zustand (Hat gewirkt, Hat nicht gewirkt, Nicht messbar, Zurueckgezogen). */
export function isClosedState(state: MeasureState): boolean {
  return CLOSED_STATES.has(state)
}

// Zustand nach einem bekannten Event; `null` = Event ohne Wirkung auf den
// Zustand (`reviewed` ohne gueltiges `verdict` ist laut DB-CHECK unmoeglich,
// wird aber wie ein unbekanntes Event behandelt statt zu werfen).
function stateAfter(event: MeasureEvent): MeasureState | null {
  if (!isKnownMeasureEvent(event.event)) return null
  if (event.event === 'reviewed') {
    switch (event.verdict) {
      case 'effective':
      case 'ineffective':
      case 'not_measurable':
        return event.verdict
      default:
        return null
    }
  }
  return event.event
}

/**
 * Zustand aus dem Verlauf. Ohne Event `agreed` („Vereinbart“). Die
 * Reihenfolge folgt `created_at`, nicht der Position in der Liste; bei
 * gleicher Zeit gilt die Listenreihenfolge (die API liefert aelteste zuerst).
 */
export function deriveMeasureState(events: readonly MeasureEvent[]): MeasureState {
  const ordered = events
    .map((event, index) => ({ event, index }))
    .sort((a, b) => {
      const diff = Date.parse(a.event.created_at) - Date.parse(b.event.created_at)
      return diff !== 0 && !Number.isNaN(diff) ? diff : a.index - b.index
    })
  let state: MeasureState = 'agreed'
  for (const { event } of ordered) {
    state = stateAfter(event) ?? state
  }
  return state
}

/**
 * Kalendertag `YYYY-MM-DD` als lokales Datum um 00:00. `new Date('2026-10-14')`
 * waere UTC-Mitternacht und laege westlich von UTC am Vortag.
 */
export function parseDay(value: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (match === null) return new Date(Number.NaN)
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
}

function startOfDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

/**
 * Ganze Kalendertage von `from` bis `to` (lokal, ohne Uhrzeit). Ueber den
 * UTC-Wert der Tagesdaten gerechnet, damit Sommer-/Winterzeit keinen Tag
 * verschluckt.
 */
function daysBetween(from: Date, to: Date): number {
  const a = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate())
  const b = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate())
  return Math.round((b - a) / 86_400_000)
}

/** Datum der Nachkontrolle: das der Aenderung, sonst das des Protokolls. */
export function followUpDate(
  measure: Pick<MeasureRead, 'follow_up_at'>,
  session: Pick<SessionRead, 'follow_up_at'>,
): string {
  return measure.follow_up_at ?? session.follow_up_at
}

/**
 * Tage seit dem Termin: 0 = heute faellig, 1 = seit gestern; negativ = der
 * Termin liegt in der Zukunft. Fuer „seit {{count}} Tagen faellig“.
 */
export function daysSince(day: string, today: Date = new Date()): number {
  return daysBetween(parseDay(day), startOfDay(today))
}

/** Liegt der Termin heute oder frueher (lokaler Kalendertag)? */
export function isOnOrBeforeToday(day: string, today: Date = new Date()): boolean {
  return daysSince(day, today) >= 0
}

/**
 * Markierung einer Aenderung:
 * - `due`: faellig, die Aenderung ist aktiviert („Nachkontrolle faellig“).
 * - `due_not_active`: faellig, aber noch Vereinbart oder Entwurf verknuepft
 *   („Nachkontrolle faellig, Aenderung noch nicht aktiv“).
 * - `scheduled`: offen, Termin in der Zukunft („Nachkontrolle am {{date}}“).
 * - `closed`: abgeschlossen, keine Nachkontrolle mehr.
 */
export type FollowUpKind = 'due' | 'due_not_active' | 'scheduled' | 'closed'

export interface FollowUpStatus {
  kind: FollowUpKind
  state: MeasureState
  /** Datum der Nachkontrolle (`YYYY-MM-DD`). */
  date: string
  /** Tage seit dem Termin, nur bei faelligen Aenderungen (0 = heute). */
  daysOverdue: number | null
}

/** Zustand plus Faellig-Markierung einer Aenderung im Kontext ihres Protokolls. */
export function followUpStatus(
  measure: Pick<MeasureRead, 'follow_up_at' | 'events'>,
  session: Pick<SessionRead, 'follow_up_at'>,
  today: Date = new Date(),
): FollowUpStatus {
  const state = deriveMeasureState(measure.events)
  const date = followUpDate(measure, session)
  if (isClosedState(state)) {
    return { kind: 'closed', state, date, daysOverdue: null }
  }
  const days = daysSince(date, today)
  if (Number.isNaN(days) || days < 0) {
    return { kind: 'scheduled', state, date, daysOverdue: null }
  }
  return {
    kind: NOT_ACTIVE_STATES.has(state) ? 'due_not_active' : 'due',
    state,
    date,
    daysOverdue: days,
  }
}

/** Ist die Aenderung faellig (eine der beiden Faellig-Varianten)? */
export function isDue(status: FollowUpStatus): boolean {
  return status.kind === 'due' || status.kind === 'due_not_active'
}
