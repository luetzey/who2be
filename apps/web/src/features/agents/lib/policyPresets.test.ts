import { describe, expect, it } from 'vitest'

import {
  applyPolicyPreset,
  derivePolicyPreset,
  WRITE_CAP_FIELDS,
  type WriteCapValues,
} from './policyPresets'

function allValues(value: boolean): WriteCapValues {
  return Object.fromEntries(WRITE_CAP_FIELDS.map((field) => [field, value])) as WriteCapValues
}

describe('policyPresets', () => {
  describe('derivePolicyPreset', () => {
    it('erkennt „Nur lesen“ bei allen Write-Capabilities aus', () => {
      expect(derivePolicyPreset(allValues(false))).toBe('readOnly')
    })

    it('erkennt „Editor ohne Freigabe“ bei allen Writes an, promote_retire aus', () => {
      const values = { ...allValues(true), promote_retire: false }
      expect(derivePolicyPreset(values)).toBe('editorNoApproval')
    })

    it('erkennt „Editor mit Freigabe“ bei allen Writes inkl. promote_retire an', () => {
      expect(derivePolicyPreset(allValues(true))).toBe('editorWithApproval')
    })

    it('faellt auf „custom“ zurueck, wenn kein Muster passt', () => {
      const values = { ...allValues(false), playbook_write: true }
      expect(derivePolicyPreset(values)).toBe('custom')
    })

    it('faellt auf „custom“ zurueck, wenn nur promote_retire an ist (kein Write aktiv)', () => {
      const values = { ...allValues(false), promote_retire: true }
      expect(derivePolicyPreset(values)).toBe('custom')
    })

    it('faellt auf „custom“ zurueck bei teilweise gesetzten Writes ohne promote_retire', () => {
      const values = { ...allValues(true), promote_retire: false, kb_edge_write: false }
      expect(derivePolicyPreset(values)).toBe('custom')
    })
  })

  describe('applyPolicyPreset', () => {
    it('setzt bei „Nur lesen“ alle Felder auf aus', () => {
      const result = applyPolicyPreset('readOnly')
      expect(WRITE_CAP_FIELDS.every((field) => result[field] === false)).toBe(true)
    })

    it('setzt bei „Editor ohne Freigabe“ alle Writes an, promote_retire aus', () => {
      const result = applyPolicyPreset('editorNoApproval')
      expect(result.promote_retire).toBe(false)
      expect(
        WRITE_CAP_FIELDS.filter((field) => field !== 'promote_retire').every(
          (field) => result[field] === true,
        ),
      ).toBe(true)
    })

    it('setzt bei „Editor mit Freigabe“ alle Felder inkl. promote_retire an', () => {
      const result = applyPolicyPreset('editorWithApproval')
      expect(WRITE_CAP_FIELDS.every((field) => result[field] === true)).toBe(true)
    })

    it('ist die Umkehrung von derivePolicyPreset fuer jedes waehlbare Preset', () => {
      for (const preset of ['readOnly', 'editorNoApproval', 'editorWithApproval'] as const) {
        expect(derivePolicyPreset(applyPolicyPreset(preset))).toBe(preset)
      }
    })
  })
})
