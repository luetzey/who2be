import { describe, expect, it } from 'vitest'

import type { CaseElement, CaseStatus, CaseTarget } from '@/api/types'

import { type CaseAction, type CaseMeasureRef, LINK_ACTIONS, nextStep, pickCaseMeasure } from './caseNextStep'

function el(target: CaseTarget, entityId: string | null = 'x1'): CaseElement {
  return {
    id: `el-${target}`,
    case_id: 'c1',
    target,
    entity_id: entityId,
    assigned_by_kind: 'human',
    assigned_by: 'u1',
    created_at: '2026-10-09T00:00:00Z',
  }
}

describe('nextStep (Spec S8 „Nächster Schritt in D“)', () => {
  it('open/reopened ohne Zuordnung: Zuordnen, sonst Einordnen', () => {
    for (const status of ['open', 'reopened'] as const) {
      expect(nextStep(status, [], false)).toEqual({
        primary: 'assign',
        menu: ['dismiss'],
        addressUnavailable: false,
      })
      expect(nextStep(status, [el('playbook')], false)).toEqual({
        primary: 'triage',
        menu: ['changeAssignment', 'dismiss'],
        addressUnavailable: false,
      })
    }
  })

  it('triaged: erst Prüffall, danach Review vorbereiten; Geändert nur im Menü, ohne versionierten Baustein ein Hinweis', () => {
    expect(nextStep('triaged', [el('playbook')], false)).toEqual({
      primary: 'createTestCase',
      menu: ['prepareSession', 'address', 'changeAssignment', 'dismiss'],
      addressUnavailable: false,
    })
    expect(nextStep('triaged', [el('playbook')], true)).toEqual({
      primary: 'prepareSession',
      menu: ['address', 'changeAssignment', 'dismiss'],
      addressUnavailable: false,
    })
    expect(nextStep('triaged', [el('tool_policy', null)], true)).toEqual({
      primary: 'prepareSession',
      menu: ['changeAssignment', 'dismiss'],
      addressUnavailable: true,
    })
    // Gedaechtnis ist nicht versioniert.
    expect(nextStep('triaged', [el('memory')], true).addressUnavailable).toBe(true)
  })

  it('Modellgrenze macht Verwerfen zur Hauptaktion', () => {
    expect(nextStep('open', [el('model_limit', null)], false)).toEqual({
      primary: 'dismiss',
      menu: ['triage', 'changeAssignment'],
      addressUnavailable: false,
    })
  })
})

describe('nextStep (E-Delta §6.3 „Nächster Schritt in E“)', () => {
  const openMeasure: CaseMeasureRef = { sessionId: 's1', measureId: 'm1', open: true }
  const closedMeasure: CaseMeasureRef = { ...openMeasure, open: false }

  it('triaged ohne Prüffall: Prüffall anlegen, Review vorbereiten im Menü', () => {
    const step = nextStep('triaged', [el('playbook')], false, null)
    expect(step.primary).toBe('createTestCase')
    expect(step.menu).toEqual(['prepareSession', 'address', 'changeAssignment', 'dismiss'])
  })

  it('triaged mit Prüffall: Review vorbereiten ist Hauptaktion', () => {
    const step = nextStep('triaged', [el('playbook')], true, null)
    expect(step.primary).toBe('prepareSession')
    expect(step.menu).toEqual(['address', 'changeAssignment', 'dismiss'])
  })

  it('in_progress: Zur Änderung, Menü Geändert und Verwerfen', () => {
    expect(nextStep('in_progress', [el('playbook')], true, openMeasure)).toEqual({
      primary: 'toMeasure',
      menu: ['address', 'dismiss'],
      addressUnavailable: false,
    })
  })

  it('in_progress ohne bekannte Änderung: keine Hauptaktion, Menü bleibt', () => {
    expect(nextStep('in_progress', [el('playbook')], true, null)).toEqual({
      primary: null,
      menu: ['address', 'dismiss'],
      addressUnavailable: false,
    })
    expect(nextStep('in_progress', [el('tool_policy', null)], true, openMeasure)).toEqual({
      primary: 'toMeasure',
      menu: ['dismiss'],
      addressUnavailable: true,
    })
  })

  it('addressed mit offener Änderung: Zur Nachkontrolle, Menü Wieder öffnen', () => {
    expect(nextStep('addressed', [el('playbook')], true, openMeasure)).toEqual({
      primary: 'toFollowUp',
      menu: ['reopen'],
      addressUnavailable: false,
    })
  })

  it('addressed ohne (offene) Änderung: Zur Version wie bisher', () => {
    for (const measure of [null, closedMeasure]) {
      expect(nextStep('addressed', [el('playbook')], true, measure)).toEqual({
        primary: 'toVersion',
        menu: ['reopen'],
        addressUnavailable: false,
      })
    }
  })

  it('verified: Zur Nachkontrolle ohne Menü; ohne Änderung nichts', () => {
    expect(nextStep('verified', [el('playbook')], true, closedMeasure)).toEqual({
      primary: 'toFollowUp',
      menu: [],
      addressUnavailable: false,
    })
    expect(nextStep('verified', [el('playbook')], true, null)).toEqual({
      primary: null,
      menu: [],
      addressUnavailable: false,
    })
  })

  it('dismissed: nichts, auch mit Änderung', () => {
    expect(nextStep('dismissed', [el('playbook')], true, openMeasure)).toEqual({
      primary: null,
      menu: [],
      addressUnavailable: false,
    })
  })

  const ALL: CaseStatus[] = ['open', 'reopened', 'triaged', 'in_progress', 'addressed', 'verified', 'dismissed']
  const variants: [boolean, CaseMeasureRef | null][] = [
    [false, null],
    [true, null],
    [true, openMeasure],
    [true, closedMeasure],
  ]

  it('„Als geändert markieren…“ ist nie Hauptaktion und fehlt bei verified/dismissed', () => {
    for (const status of ALL) {
      for (const [hasTestCase, measure] of variants) {
        const step = nextStep(status, [el('playbook')], hasTestCase, measure)
        expect(step.primary).not.toBe('address')
        if (status === 'verified' || status === 'dismissed') {
          expect(step.menu).not.toContain('address')
        }
      }
    }
  })

  it('kein Eintrag führt nach in_progress/verified: nur bekannte Aktionen, Phase-E-Aktionen sind Links', () => {
    // Abschliessende Liste: Status setzen nur `triage` (→ triaged), `address`
    // (→ addressed), `dismiss`, `reopen`; Zuordnen und Prüffall setzen keinen
    // Status. Alles andere muss ein Link sein. Eine neue Aktion faellt hier auf.
    const allowed = new Set<CaseAction>([
      'assign',
      'changeAssignment',
      'createTestCase',
      'triage',
      'address',
      'dismiss',
      'reopen',
      ...LINK_ACTIONS,
    ])
    for (const status of ALL) {
      for (const [hasTestCase, measure] of variants) {
        const step = nextStep(status, [el('playbook')], hasTestCase, measure)
        for (const action of [step.primary, ...step.menu]) {
          if (action !== null) expect(allowed).toContain(action)
        }
      }
    }
    expect([...LINK_ACTIONS].sort()).toEqual(['prepareSession', 'toFollowUp', 'toMeasure', 'toVersion'])
  })
})

describe('pickCaseMeasure', () => {
  const ref = (measureId: string, open: boolean): CaseMeasureRef => ({ sessionId: 's', measureId, open })

  it('ohne bekannte Änderung: null', () => {
    expect(pickCaseMeasure('in_progress', ['m1'], [])).toBeNull()
  })

  it('bevorzugt eine offene Änderung, darin die jüngst im Verlauf genannte', () => {
    const known = [ref('m-closed', false), ref('m-old', true), ref('m-new', true)]
    expect(pickCaseMeasure('addressed', ['m-closed', 'm-new', 'm-old'], known)?.measureId).toBe('m-new')
    // Ohne Verlaufsbezug gilt die Reihenfolge der Liste.
    expect(pickCaseMeasure('addressed', [], known)?.measureId).toBe('m-old')
  })

  it('nur abgeschlossene: die jüngst genannte', () => {
    const known = [ref('m1', false), ref('m2', false)]
    expect(pickCaseMeasure('addressed', ['m2'], known)?.measureId).toBe('m2')
  })

  it('verified: die Änderung des jüngsten Ereignisses, auch wenn eine andere offen ist', () => {
    const known = [ref('m-open', true), ref('m-effective', false)]
    expect(pickCaseMeasure('verified', ['m-effective', 'm-open'], known)?.measureId).toBe('m-effective')
  })
})
