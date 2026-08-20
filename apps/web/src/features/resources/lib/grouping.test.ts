import { describe, expect, it } from 'vitest'

import type { Resource } from '@/api/types'
import { groupResources, parseGroupMode } from './grouping'

function res(id: string, tags: string[] = []): Resource {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: `Resource ${id}`,
    slug: id,
    current_version: 1,
    content: { description: '', blocks: [], tags },
    created_at: '2026-07-09T10:00:00Z',
    updated_at: '2026-07-09T10:00:00Z',
  }
}

describe('parseGroupMode', () => {
  it('akzeptiert nur tag, alles andere wird none', () => {
    expect(parseGroupMode('tag')).toBe('tag')
    expect(parseGroupMode('')).toBe('none')
    expect(parseGroupMode('none')).toBe('none')
    expect(parseGroupMode('bogus')).toBe('none')
  })
})

describe('groupResources', () => {
  it('none: eine flache Gruppe mit allen Items', () => {
    const items = [res('a'), res('b')]
    expect(groupResources(items, 'none')).toEqual([{ key: 'all', items }])
  })

  it('tag: alphabetisch nach Tag, Mehrfach-Tags landen in jeder ihrer Gruppen', () => {
    const items = [res('a', ['coach', 'brain']), res('b', ['brain']), res('c', [])]
    const groups = groupResources(items, 'tag')
    expect(groups.map((g) => g.key)).toEqual(['brain', 'coach', ''])
    expect(groups.find((g) => g.key === 'brain')?.items.map((r) => r.id)).toEqual(['a', 'b'])
    expect(groups.find((g) => g.key === 'coach')?.items.map((r) => r.id)).toEqual(['a'])
    expect(groups.find((g) => g.key === '')?.items.map((r) => r.id)).toEqual(['c'])
  })

  it('tag: Resources ohne content.tags-Feld gelten als ohne Tag', () => {
    const withoutTagsField = { ...res('a'), content: { description: '', blocks: [] } } as Resource
    const groups = groupResources([withoutTagsField], 'tag')
    expect(groups.map((g) => g.key)).toEqual([''])
  })

  it('tag: leere Eingabe ergibt keine Gruppen', () => {
    expect(groupResources([], 'tag')).toEqual([])
  })
})
