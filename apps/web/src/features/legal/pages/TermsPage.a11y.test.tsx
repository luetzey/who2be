import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { TermsPage } from './TermsPage'

describe('TermsPage', () => {
  it('rendert die B2B/B2C-Abschnitte und sichtbare Platzhalter', () => {
    const { getByRole, container } = render(
      <MemoryRouter>
        <TermsPage />
      </MemoryRouter>,
    )
    expect(getByRole('heading', { level: 1, name: /Geschaeftsbedingungen/i })).toBeInTheDocument()
    // Gruppen-Abschnitte als h2 (A. Allgemein, B. Verbraucher, C. Unternehmer).
    expect(getByRole('heading', { level: 2, name: /Verbraucher \(B2C\)/i })).toBeInTheDocument()
    expect(getByRole('heading', { level: 2, name: /Unternehmer \(B2B\)/i })).toBeInTheDocument()
    // SLA-Geruest + Widerruf + E-Rechnung als Klausel-Headings (h3).
    expect(getByRole('heading', { level: 3, name: /Service-Level/i })).toBeInTheDocument()
    expect(getByRole('heading', { level: 3, name: /Widerrufsrecht/i })).toBeInTheDocument()
    expect(getByRole('heading', { level: 3, name: /Elektronische Rechnung/i })).toBeInTheDocument()
    expect(container.querySelectorAll('[data-placeholder]').length).toBeGreaterThan(0)
  })

  it('hat keine A11y-Verstoesse', async () => {
    const { container } = render(
      <MemoryRouter>
        <TermsPage />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
