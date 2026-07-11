import { render, screen } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { UsedByList, type UsedByEntry } from './UsedByList'

const ITEMS: UsedByEntry[] = [
  { id: 'pb1', name: 'Coach', href: '/playbooks/pb1', meta: '2 Bloecke' },
  { id: 'pb2', name: 'Onboarding-Flow', href: '/playbooks/pb2', icon: FileText, iconTone: 'resource' },
]

function renderList(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('UsedByList', () => {
  it('rendert Link-Zeilen mit Name, Ziel und optionalem Meta', () => {
    renderList(<UsedByList items={ITEMS} aria-label="Verlinkt in" />)
    expect(screen.getByRole('list', { name: 'Verlinkt in' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Coach' })).toHaveAttribute('href', '/playbooks/pb1')
    expect(screen.getByText('2 Bloecke')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Onboarding-Flow' })).toBeInTheDocument()
  })

  it('rendert das empty-Slot-Fallback bei leerer Liste', () => {
    renderList(<UsedByList items={[]} empty={<p>Noch nicht verlinkt.</p>} />)
    expect(screen.getByText('Noch nicht verlinkt.')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('rendert nichts ohne empty-Slot bei leerer Liste', () => {
    const { container } = renderList(<UsedByList items={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
