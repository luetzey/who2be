import { describe, expect, it } from 'vitest'

import type { Playbook, ResourceLink } from '@/api/types'

import { buildMigratedBody } from './bodyMigration'

function pb(id: string, name: string): Playbook {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o-1',
    name,
    current_version: 1,
    type: 'workflow',
    tags: [],
    triggers: null,
    content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
    created_at: 't',
    updated_at: 't',
  }
}

// Sammelt alle Placeholder-Inline-Props aus den Bloecken ein.
function collectPills(
  blocks: ReturnType<typeof buildMigratedBody>,
): { kind: string; target_id: string; label: string }[] {
  const pills: { kind: string; target_id: string; label: string }[] = []
  for (const block of blocks) {
    const content = (block as { content?: unknown }).content
    if (!Array.isArray(content)) continue
    for (const inline of content) {
      if (
        inline !== null &&
        typeof inline === 'object' &&
        (inline as { type?: string }).type === 'placeholder'
      ) {
        pills.push((inline as { props: { kind: string; target_id: string; label: string } }).props)
      }
    }
  }
  return pills
}

describe('buildMigratedBody', () => {
  it('hebt Composes-Kinder als Playbook-Pills in den Body', () => {
    const blocks = buildMigratedBody('Schritt 1', [pb('pb-2', 'Sub A'), pb('pb-3', 'Sub B')], [])
    const pills = collectPills(blocks)
    expect(pills).toEqual(
      expect.arrayContaining([
        { kind: 'playbook', target_id: 'pb-2', label: 'Playbook: Sub A' },
        { kind: 'playbook', target_id: 'pb-3', label: 'Playbook: Sub B' },
      ]),
    )
  })

  it('hebt Resource-Links als Resource-Pills, mit #block_id bei link_scope=block', () => {
    const links: ResourceLink[] = [
      {
        resource_id: 'res-1',
        resource_name: 'FAQ',
        block_id: 'blk-9',
        position: 0,
        available: true,
        section_preview: 'Reset-Ablauf',
        preview: null,
        link_scope: 'block',
      },
      {
        resource_id: 'res-2',
        resource_name: 'Preisliste',
        block_id: null,
        position: 1,
        available: true,
        preview: null,
        link_scope: 'resource',
      },
    ]
    const blocks = buildMigratedBody('Body', [], links)
    const pills = collectPills(blocks)

    const blockPill = pills.find((p) => p.target_id.startsWith('res-1'))
    expect(blockPill?.target_id).toBe('res-1#blk-9')
    expect(blockPill?.kind).toBe('resource')
    expect(blockPill?.label).toContain('FAQ')
    expect(blockPill?.label).toContain('Reset-Ablauf')

    const wholePill = pills.find((p) => p.target_id === 'res-2')
    expect(wholePill).toEqual({
      kind: 'resource',
      target_id: 'res-2',
      label: 'Resource: Preisliste',
    })
  })

  it('konvertiert den Plain-Body in Paragraphen nach dem Pill-Paragraph', () => {
    const blocks = buildMigratedBody('Alpha\n\nBeta', [pb('pb-2', 'Sub')], [])
    // Erster Block = Pill-Paragraph, danach zwei Plain-Paragraphen.
    expect(blocks.length).toBe(3)
    expect(collectPills([blocks[0]]).length).toBe(1)
    const texts = blocks.slice(1).map((b) => {
      const content = (b as unknown as { content: { text?: string }[] }).content
      return content.map((c) => c.text ?? '').join('')
    })
    expect(texts).toEqual(['Alpha', 'Beta'])
  })

  it('liefert mindestens einen Block bei leerem Body ohne Relationen', () => {
    const blocks = buildMigratedBody('', [], [])
    expect(blocks.length).toBe(1)
  })
})
