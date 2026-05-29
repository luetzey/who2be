import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ResourceLink } from '@/api/types'

import { LinkedBlocksList } from './LinkedBlocksList'

function link(
  block_id: string,
  overrides: Partial<ResourceLink> = {},
): ResourceLink {
  return {
    resource_id: 'r-1',
    resource_name: 'Runbook',
    block_id,
    position: 0,
    available: true,
    preview: null,
    ...overrides,
  }
}

describe('LinkedBlocksList', () => {
  it('zeigt drei Badge-Varianten anhand available_in', () => {
    const active = link('b-active', {
      available_in: 'active',
      section_preview: 'Aktive Section.',
      available: true,
    })
    const draft = link('b-draft', {
      available_in: 'draft',
      section_preview: 'Draft-Section.',
      available: true,
    })
    const deleted = link('b-deleted', {
      available_in: null,
      section_preview: null,
      available: false,
    })

    render(
      <LinkedBlocksList links={[active, draft, deleted]} onRemove={() => {}} />,
    )

    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByText('Nur in Draft')).toBeInTheDocument()
    expect(screen.getByText('Block geloescht')).toBeInTheDocument()
    expect(screen.getByText('Aktive Section.')).toBeInTheDocument()
    expect(screen.getByText('Draft-Section.')).toBeInTheDocument()
  })

  it('faellt auf das alte `available`-Boolean zurueck, wenn available_in fehlt', () => {
    const legacyOk = link('b-1', { preview: 'Erster Block', available: true })
    const legacyGone = link('b-2', { available: false })

    render(
      <LinkedBlocksList links={[legacyOk, legacyGone]} onRemove={() => {}} />,
    )

    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByText('Block geloescht')).toBeInTheDocument()
    expect(screen.getByText('Erster Block')).toBeInTheDocument()
  })

  it('ruft onRemove mit dem Link beim Entfernen', () => {
    const onRemove = vi.fn()
    const available = link('b-1', { available_in: 'active', preview: 'p' })
    render(<LinkedBlocksList links={[available]} onRemove={onRemove} />)
    fireEvent.click(screen.getByRole('button', { name: 'Entfernen' }))
    expect(onRemove).toHaveBeenCalledWith(available)
  })

  it('zeigt Leerzustand ohne Links', () => {
    render(<LinkedBlocksList links={[]} onRemove={() => {}} />)
    expect(screen.getByText('Noch keine Bloecke verknuepft.')).toBeInTheDocument()
  })
})
