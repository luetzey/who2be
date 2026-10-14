import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import type { MeasureEvent, MeasureEventKind, MeasureVerdict } from '@/api/types'

import {
  daysSince,
  deriveMeasureState,
  followUpDate,
  followUpStatus,
  isClosedState,
  isDue,
  isKnownMeasureEvent,
  isOnOrBeforeToday,
  parseDay,
} from './followUp'

// Fester lokaler Zeitpunkt mitten am Tag; die Logik vergleicht nur Kalendertage.
const TODAY = new Date(2026, 9, 14, 15, 30)

let seq = 0
function ev(event: MeasureEventKind | string, verdict: MeasureVerdict | null = null, at?: string): MeasureEvent {
  seq += 1
  return {
    id: `e${seq}`,
    measure_id: 'm1',
    event: event as MeasureEventKind,
    actor_kind: 'human',
    actor_id: null,
    version_entity_type: null,
    version_id: null,
    verdict,
    metrics: null,
    note: null,
    created_at: at ?? `2026-10-01T10:00:${String(seq % 60).padStart(2, '0')}Z`,
  }
}

const SESSION = { follow_up_at: '2026-10-20' }

describe('deriveMeasureState: jede Zeile der Zustandstabelle', () => {
  it.each([
    ['(keins) → agreed', [], 'agreed'],
    ['draft_linked', [ev('draft_linked')], 'draft_linked'],
    ['activated', [ev('draft_linked'), ev('activated')], 'activated'],
    [
      'follow_up_prepared',
      [ev('draft_linked'), ev('activated'), ev('follow_up_prepared')],
      'follow_up_prepared',
    ],
    ['reviewed effective', [ev('activated'), ev('reviewed', 'effective')], 'effective'],
    ['reviewed ineffective', [ev('activated'), ev('reviewed', 'ineffective')], 'ineffective'],
    [
      'reviewed not_measurable',
      [ev('activated'), ev('reviewed', 'not_measurable')],
      'not_measurable',
    ],
    ['withdrawn', [ev('draft_linked'), ev('withdrawn')], 'withdrawn'],
  ] as const)('%s', (_label, events, expected) => {
    expect(deriveMeasureState(events)).toBe(expected)
  })

  it('unbekanntes Event: der letzte bekannte Zustand bleibt', () => {
    expect(deriveMeasureState([ev('activated'), ev('archived_by_future_api')])).toBe('activated')
    expect(deriveMeasureState([ev('archived_by_future_api')])).toBe('agreed')
    expect(isKnownMeasureEvent('archived_by_future_api')).toBe(false)
    expect(isKnownMeasureEvent('activated')).toBe(true)
  })

  it('reviewed ohne verdict wirkt wie ein unbekanntes Event', () => {
    expect(deriveMeasureState([ev('activated'), ev('reviewed', null)])).toBe('activated')
  })

  it('das juengste Event nach created_at gilt, nicht die Listenposition', () => {
    const late = ev('activated', null, '2026-10-05T09:00:00Z')
    const early = ev('draft_linked', null, '2026-10-02T09:00:00Z')
    expect(deriveMeasureState([late, early])).toBe('activated')
  })

  it('erneutes Verknuepfen nach draft_linked bleibt draft_linked (QE4 a)', () => {
    expect(deriveMeasureState([ev('draft_linked'), ev('draft_linked')])).toBe('draft_linked')
  })
})

describe('isClosedState', () => {
  it.each(['effective', 'ineffective', 'not_measurable', 'withdrawn'] as const)(
    '%s ist abgeschlossen',
    (state) => expect(isClosedState(state)).toBe(true),
  )
  it.each(['agreed', 'draft_linked', 'activated', 'follow_up_prepared'] as const)(
    '%s ist offen',
    (state) => expect(isClosedState(state)).toBe(false),
  )
})

describe('Datum der Nachkontrolle', () => {
  it('nimmt das Datum der Aenderung', () => {
    expect(followUpDate({ follow_up_at: '2026-10-10' }, SESSION)).toBe('2026-10-10')
  })
  it('faellt ohne Datum an der Aenderung auf das Protokoll zurueck', () => {
    expect(followUpDate({ follow_up_at: null }, SESSION)).toBe('2026-10-20')
  })
  it('parseDay liest lokal, nicht UTC', () => {
    const d = parseDay('2026-10-14')
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours()]).toEqual([2026, 9, 14, 0])
    expect(Number.isNaN(parseDay('kein datum').getTime())).toBe(true)
  })
})

describe('Faellig: Tagesvergleich ohne Uhrzeit', () => {
  it('heute ist faellig (0 Tage), auch spaet am Tag', () => {
    expect(daysSince('2026-10-14', TODAY)).toBe(0)
    expect(isOnOrBeforeToday('2026-10-14', new Date(2026, 9, 14, 23, 59))).toBe(true)
    expect(isOnOrBeforeToday('2026-10-14', new Date(2026, 9, 14, 0, 0))).toBe(true)
  })
  it('gestern ist faellig (1 Tag)', () => {
    expect(daysSince('2026-10-13', TODAY)).toBe(1)
    expect(isOnOrBeforeToday('2026-10-13', TODAY)).toBe(true)
  })
  it('morgen ist nicht faellig', () => {
    expect(daysSince('2026-10-15', TODAY)).toBe(-1)
    expect(isOnOrBeforeToday('2026-10-15', new Date(2026, 9, 14, 23, 59))).toBe(false)
  })
})

// Sommerzeit: Die Zeitzone wird fest auf Europe/Berlin gesetzt, damit der
// Test auch in einer CI mit TZ=UTC eine Umstellung sieht. Der Waechter-Test
// prueft, dass die Umstellung wirklich greift, sonst bewiese der Rest nichts.
describe('Faellig: ganze Tage ueber die Zeitumstellung (Europe/Berlin)', () => {
  let previousTz: string | undefined
  beforeAll(() => {
    previousTz = process.env.TZ
    process.env.TZ = 'Europe/Berlin'
  })
  afterAll(() => {
    if (previousTz === undefined) delete process.env.TZ
    else process.env.TZ = previousTz
  })

  it('Waechter: die Zeitzone hat Sommer- und Winterzeit', () => {
    expect(new Date(2026, 0, 15).getTimezoneOffset()).toBe(-60)
    expect(new Date(2026, 6, 15).getTimezoneOffset()).toBe(-120)
  })
  it('Fruehjahr (29.03.2026, Tag mit 23 Stunden): kurz nach Mitternacht 10 Tage', () => {
    expect(daysSince('2026-03-20', new Date(2026, 2, 30, 0, 30))).toBe(10)
    expect(daysSince('2026-03-28', new Date(2026, 2, 29, 0, 30))).toBe(1)
  })
  it('Herbst (25.10.2026, Tag mit 25 Stunden): 10 Tage, auch kurz vor Mitternacht', () => {
    expect(daysSince('2026-10-20', new Date(2026, 9, 30, 8, 0))).toBe(10)
    expect(daysSince('2026-10-24', new Date(2026, 9, 25, 23, 59))).toBe(1)
  })
})

describe('followUpStatus: beide Faellig-Varianten und Endzustaende', () => {
  const today = { follow_up_at: '2026-10-14' }
  const yesterday = { follow_up_at: '2026-10-13' }
  const tomorrow = { follow_up_at: '2026-10-15' }

  it('aktiviert und Termin heute → due', () => {
    const s = followUpStatus({ ...today, events: [ev('activated')] }, SESSION, TODAY)
    expect(s).toEqual({ kind: 'due', state: 'activated', date: '2026-10-14', daysOverdue: 0 })
    expect(isDue(s)).toBe(true)
  })

  it('Kennzahlen bereit und Termin gestern → due, seit 1 Tag', () => {
    const s = followUpStatus(
      { ...yesterday, events: [ev('activated'), ev('follow_up_prepared')] },
      SESSION,
      TODAY,
    )
    expect(s.kind).toBe('due')
    expect(s.daysOverdue).toBe(1)
  })

  it.each([
    ['vereinbart', []],
    ['Entwurf verknuepft', [ev('draft_linked')]],
  ])('%s und faellig → due_not_active', (_label, events) => {
    const s = followUpStatus({ ...yesterday, events }, SESSION, TODAY)
    expect(s.kind).toBe('due_not_active')
    expect(isDue(s)).toBe(true)
  })

  it('Termin morgen → scheduled, nicht faellig', () => {
    const s = followUpStatus({ ...tomorrow, events: [ev('activated')] }, SESSION, TODAY)
    expect(s).toEqual({ kind: 'scheduled', state: 'activated', date: '2026-10-15', daysOverdue: null })
    expect(isDue(s)).toBe(false)
  })

  it('ohne Datum an der Aenderung gilt das Protokoll', () => {
    const s = followUpStatus(
      { follow_up_at: null, events: [ev('activated')] },
      { follow_up_at: '2026-10-01' },
      TODAY,
    )
    expect(s.kind).toBe('due')
    expect(s.date).toBe('2026-10-01')
    expect(s.daysOverdue).toBe(13)
  })

  it.each([
    ['effective', [ev('activated'), ev('reviewed', 'effective')]],
    ['ineffective', [ev('activated'), ev('reviewed', 'ineffective')]],
    ['not_measurable', [ev('activated'), ev('reviewed', 'not_measurable')]],
    ['withdrawn', [ev('withdrawn')]],
  ])('Endzustand %s ist nie faellig, auch lange ueberfaellig', (state, events) => {
    const s = followUpStatus({ follow_up_at: '2026-01-01', events }, SESSION, TODAY)
    expect(s).toEqual({ kind: 'closed', state, date: '2026-01-01', daysOverdue: null })
    expect(isDue(s)).toBe(false)
  })

  it('ungueltiges Datum gilt nicht als faellig', () => {
    const s = followUpStatus({ follow_up_at: 'x', events: [ev('activated')] }, SESSION, TODAY)
    expect(s.kind).toBe('scheduled')
  })
})
