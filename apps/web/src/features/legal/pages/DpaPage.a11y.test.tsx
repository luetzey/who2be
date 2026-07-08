import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { DpaPage } from './DpaPage'

describe('DpaPage', () => {
  it('rendert die AVV-Abschnitte und sichtbare Platzhalter', () => {
    const { getByRole, container } = render(
      <MemoryRouter>
        <DpaPage />
      </MemoryRouter>,
    )
    expect(
      getByRole('heading', { level: 1, name: /Auftragsverarbeitung/i }),
    ).toBeInTheDocument()
    // Kern-Klauseln nach Art. 28 DSGVO als Abschnitts-Headings.
    expect(getByRole('heading', { name: /Gegenstand & Dauer/i })).toBeInTheDocument()
    expect(getByRole('heading', { name: /Unterauftragsverarbeiter/i })).toBeInTheDocument()
    expect(
      getByRole('heading', { name: /Technische & organisatorische Massnahmen/i }),
    ).toBeInTheDocument()
    expect(container.querySelectorAll('[data-placeholder]').length).toBeGreaterThan(0)
  })

  it('hat keine A11y-Verstoesse', async () => {
    const { container } = render(
      <MemoryRouter>
        <DpaPage />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
