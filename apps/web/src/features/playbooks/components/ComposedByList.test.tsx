import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PlaybookRef } from '@/api/types'

import { ComposedByList } from './ComposedByList'

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))

describe('ComposedByList', () => {
  it('zeigt einen Hinweis, wenn keine Eltern vorhanden sind', () => {
    render(
      <MemoryRouter>
        <ComposedByList parents={[]} />
      </MemoryRouter>,
    )
    expect(
      screen.getByText('Kein Composite-Playbook referenziert dieses Playbook.'),
    ).toBeInTheDocument()
  })

  it('rendert Links zu allen Eltern-Playbooks', () => {
    const parents: PlaybookRef[] = [
      { id: 'parent-1', name: 'Composite Alpha' },
      { id: 'parent-2', name: 'Composite Beta' },
    ]
    render(
      <MemoryRouter>
        <ComposedByList parents={parents} />
      </MemoryRouter>,
    )

    const alpha = screen.getByRole('link', { name: 'Composite Alpha' })
    expect(alpha).toBeInTheDocument()
    expect(alpha).toHaveAttribute('href', '/w/ws-1/playbooks/parent-1')

    const beta = screen.getByRole('link', { name: 'Composite Beta' })
    expect(beta).toBeInTheDocument()
    expect(beta).toHaveAttribute('href', '/w/ws-1/playbooks/parent-2')
  })
})
