import { describe, expect, it } from 'vitest'

import type { Playbook } from '@/api/types'
import { groupPlaybooks, parseGroupMode } from './grouping'

function pb(id: string, type: string, isComposite = false): Playbook {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: `PB ${id}`,
    current_version: 1,
    type,
    tags: [],
    triggers: null,
    content: { description: '', body: '', type, tags: [], triggers: null },
    created_at: '2026-07-09T10:00:00Z',
    updated_at: '2026-07-09T10:00:00Z',
    is_composite: isComposite,
  }
}

describe('parseGroupMode', () => {
  it('akzeptiert nur type und composite, alles andere wird none', () => {
    expect(parseGroupMode('type')).toBe('type')
    expect(parseGroupMode('composite')).toBe('composite')
    expect(parseGroupMode('')).toBe('none')
    expect(parseGroupMode('none')).toBe('none')
    expect(parseGroupMode('bogus')).toBe('none')
  })
})

describe('groupPlaybooks', () => {
  it('none: eine flache Gruppe mit allen Items', () => {
    const items = [pb('a', 'workflow'), pb('b', 'prompt')]
    expect(groupPlaybooks(items, 'none')).toEqual([{ key: 'all', items }])
  })

  it('composite: Composite vor Standalone, Reihenfolge innerhalb bleibt', () => {
    const items = [pb('a', 'workflow'), pb('b', 'prompt', true), pb('c', 'faq', true)]
    const groups = groupPlaybooks(items, 'composite')
    expect(groups.map((g) => g.key)).toEqual(['composite', 'standalone'])
    expect(groups[0].items.map((p) => p.id)).toEqual(['b', 'c'])
    expect(groups[1].items.map((p) => p.id)).toEqual(['a'])
  })

  it('composite: leere Gruppen fallen weg', () => {
    const groups = groupPlaybooks([pb('a', 'workflow')], 'composite')
    expect(groups.map((g) => g.key)).toEqual(['standalone'])
  })

  it('type: alphabetisch nach Typ, ohne Typ ans Ende', () => {
    const items = [pb('a', 'workflow'), pb('b', ''), pb('c', 'prompt'), pb('d', 'workflow')]
    const groups = groupPlaybooks(items, 'type')
    expect(groups.map((g) => g.key)).toEqual(['prompt', 'workflow', ''])
    expect(groups.find((g) => g.key === 'workflow')?.items.map((p) => p.id)).toEqual(['a', 'd'])
    expect(groups.find((g) => g.key === '')?.items.map((p) => p.id)).toEqual(['b'])
  })

  it('type: leere Eingabe ergibt keine Gruppen', () => {
    expect(groupPlaybooks([], 'type')).toEqual([])
    expect(groupPlaybooks([], 'composite')).toEqual([])
  })
})
