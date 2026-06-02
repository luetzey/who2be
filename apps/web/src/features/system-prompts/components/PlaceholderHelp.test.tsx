import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { PlaceholderHelp } from './PlaceholderHelp'

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))

function open() {
  render(
    <MemoryRouter>
      <PlaceholderHelp />
    </MemoryRouter>,
  )
  fireEvent.click(screen.getByTestId('placeholder-help-trigger'))
}

describe('PlaceholderHelp', () => {
  it('zeigt die BlockNote-Slash-Placeholders im Popover', () => {
    open()
    expect(screen.getByText('/Playbook')).toBeInTheDocument()
    expect(screen.getByText('/Persona-Feld')).toBeInTheDocument()
    expect(screen.getByText('/Playbook-Katalog')).toBeInTheDocument()
    expect(screen.getByText('/Datum')).toBeInTheDocument()
  })

  it('zeigt KEINE Liquid-Tokens mehr (Track B: Nur-BlockNote)', () => {
    open()
    expect(screen.queryByText('{{ persona.name }}')).not.toBeInTheDocument()
    expect(screen.queryByText('{{ playbooks }}')).not.toBeInTheDocument()
  })

  it('verlinkt auf die Placeholder-Doku-Seite', () => {
    open()
    const link = screen.getByRole('link', { name: /Doku/ })
    expect(link).toHaveAttribute('href', '/w/ws-1/help/placeholders')
  })
})
