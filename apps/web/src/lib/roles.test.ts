import { describe, expect, it } from 'vitest'

import {
  AGENT_BOUND_MAX_ROLE,
  ROLE_ORDER,
  agentBoundRoleOptions,
  isDowngrade,
  roleLabel,
  rolesAtMost,
} from './roles'

describe('rolesAtMost', () => {
  it('bietet die eigene Rolle und alles darunter an', () => {
    expect(rolesAtMost('admin')).toEqual(['admin', 'editor', 'viewer'])
    expect(rolesAtMost('editor')).toEqual(['editor', 'viewer'])
    expect(rolesAtMost('viewer')).toEqual(['viewer'])
  })
})

describe('agentBoundRoleOptions', () => {
  // Der eigentliche Punkt dieser Gruppe: ein an einen Agenten gebundener Token
  // darf nie `admin` tragen. Das Backend lehnt es mit 403
  // `agent_bound_role_capped` ab — die Auswahl soll es deshalb nicht anbieten.
  it('laesst `admin` auch fuer einen Admin weg', () => {
    expect(agentBoundRoleOptions('admin')).toEqual(['editor', 'viewer'])
    expect(agentBoundRoleOptions('admin')).not.toContain('admin')
  })

  it('bleibt unter der eigenen Rolle, wenn die schwaecher ist als der Deckel', () => {
    // Der Deckel senkt nur, er hebt nicht: ein viewer bekommt kein `editor`.
    expect(agentBoundRoleOptions('viewer')).toEqual(['viewer'])
    expect(agentBoundRoleOptions('editor')).toEqual(['editor', 'viewer'])
  })

  it('gibt nie eine leere Liste — das Select haette sonst keinen Wert', () => {
    for (const role of ROLE_ORDER) {
      expect(agentBoundRoleOptions(role).length).toBeGreaterThan(0)
    }
  })

  it('haelt die erste Option als brauchbare Vorauswahl bereit', () => {
    // Die Komponente nimmt `roleOptions[0]` als Vorgabe. Waere das `admin`,
    // zeigte das Formular einen Wert, den der Server gleich verweigert.
    for (const role of ROLE_ORDER) {
      const first = agentBoundRoleOptions(role)[0]
      expect(first).not.toBe('admin')
      expect(agentBoundRoleOptions(role)).toContain(first)
    }
  })

  it('haelt die Obergrenze an einer Stelle fest', () => {
    // Regression gegen ein zweites, abweichendes `editor` im Code: die Grenze
    // hat genau eine Quelle.
    expect(AGENT_BOUND_MAX_ROLE).toBe('editor')
    expect(agentBoundRoleOptions('admin')[0]).toBe(AGENT_BOUND_MAX_ROLE)
  })
})

describe('roleLabel / isDowngrade', () => {
  it('benennt jede Rolle', () => {
    expect(ROLE_ORDER.map(roleLabel)).toEqual(['Admin', 'Editor', 'Viewer'])
  })

  it('erkennt nur echte Herabstufungen', () => {
    expect(isDowngrade('admin', 'editor')).toBe(true)
    expect(isDowngrade('editor', 'admin')).toBe(false)
    expect(isDowngrade('editor', 'editor')).toBe(false)
  })
})
