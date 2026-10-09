import { describe, expect, it } from 'vitest'

import type { CaseElement, CaseTarget } from '@/api/types'

import { nextStep } from './caseNextStep'

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

  it('triaged: erst Prüffall, danach Umsetzen; ohne versionierten Baustein ein Hinweis', () => {
    expect(nextStep('triaged', [el('playbook')], false)).toEqual({
      primary: 'createTestCase',
      menu: ['address', 'changeAssignment', 'dismiss'],
      addressUnavailable: false,
    })
    expect(nextStep('triaged', [el('playbook')], true).primary).toBe('address')
    expect(nextStep('triaged', [el('tool_policy', null)], true)).toEqual({
      primary: 'changeAssignment',
      menu: ['dismiss'],
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

  it('addressed: Zur Version + Wieder öffnen; dismissed/in_progress/verified: nichts', () => {
    expect(nextStep('addressed', [el('playbook')], true)).toEqual({
      primary: 'toVersion',
      menu: ['reopen'],
      addressUnavailable: false,
    })
    for (const status of ['dismissed', 'in_progress', 'verified'] as const) {
      expect(nextStep(status, [el('playbook')], true)).toEqual({
        primary: null,
        menu: [],
        addressUnavailable: false,
      })
    }
  })
})
