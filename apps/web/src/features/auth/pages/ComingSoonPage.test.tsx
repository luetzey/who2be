import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: { launchContact: '' },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import { ComingSoonPage } from './ComingSoonPage'

afterEach(() => {
  mockConfig.launchContact = ''
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/signup']}>
      <ComingSoonPage />
    </MemoryRouter>,
  )
}

describe('ComingSoonPage', () => {
  it('rendert eine main-Landmark mit genau einer H1', () => {
    renderPage()

    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(
      screen.getByRole('heading', { name: 'Wir arbeiten noch an Who2Be — bald verfügbar.' }),
    ).toBeInTheDocument()
  })

  it('verlinkt zurueck zur Anmeldung', () => {
    renderPage()

    expect(screen.getByRole('link', { name: 'Zurueck zur Anmeldung' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('zeigt ohne WHO2BE_LAUNCH_CONTACT keinen Kontakt-Block', () => {
    renderPage()

    expect(screen.queryByText(/Fragen\?/)).not.toBeInTheDocument()
  })

  it('zeigt mit gesetztem Kontakt einen mailto-Link', () => {
    mockConfig.launchContact = 'hello@who2be.dev'

    renderPage()

    expect(screen.getByText(/Fragen\?/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'hello@who2be.dev' })).toHaveAttribute(
      'href',
      'mailto:hello@who2be.dev',
    )
  })
})
