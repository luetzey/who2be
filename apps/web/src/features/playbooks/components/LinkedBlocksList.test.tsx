import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ResourceLink } from '@/api/types'

import { LinkedBlocksList } from './LinkedBlocksList'

const available: ResourceLink = {
  resource_id: 'r-1',
  resource_name: 'Runbook',
  block_id: 'b-1',
  position: 0,
  available: true,
  preview: 'Erster Block',
}

const deleted: ResourceLink = {
  resource_id: 'r-1',
  resource_name: 'Runbook',
  block_id: 'b-2',
  position: 1,
  available: false,
  preview: null,
}

describe('LinkedBlocksList', () => {
  it('zeigt Verfuegbarkeit und "Block geloescht"-Badge', () => {
    render(<LinkedBlocksList links={[available, deleted]} onRemove={() => {}} />)
    expect(screen.getByText('Verfuegbar')).toBeInTheDocument()
    expect(screen.getByText('Block geloescht')).toBeInTheDocument()
    expect(screen.getByText('Erster Block')).toBeInTheDocument()
  })

  it('ruft onRemove mit dem Link beim Entfernen', () => {
    const onRemove = vi.fn()
    render(<LinkedBlocksList links={[available]} onRemove={onRemove} />)
    fireEvent.click(screen.getByRole('button', { name: 'Entfernen' }))
    expect(onRemove).toHaveBeenCalledWith(available)
  })

  it('zeigt Leerzustand ohne Links', () => {
    render(<LinkedBlocksList links={[]} onRemove={() => {}} />)
    expect(screen.getByText('Noch keine Bloecke verknuepft.')).toBeInTheDocument()
  })
})
