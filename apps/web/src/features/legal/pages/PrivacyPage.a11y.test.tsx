import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { PrivacyPage } from './PrivacyPage'

describe('PrivacyPage', () => {
  it('rendert die Pflicht-Abschnitte und sichtbare Platzhalter', () => {
    const { getByRole, container } = render(
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>,
    )
    expect(
      getByRole('heading', { level: 1, name: /Datenschutzerklaerung/i }),
    ).toBeInTheDocument()
    // Art.-13/14-Kernabschnitte.
    expect(getByRole('heading', { name: /Verantwortlicher/i })).toBeInTheDocument()
    expect(getByRole('heading', { name: /Cookies & Einwilligung/i })).toBeInTheDocument()
    expect(getByRole('heading', { name: /Deine Rechte/i })).toBeInTheDocument()
    expect(container.querySelectorAll('[data-placeholder]').length).toBeGreaterThan(0)
  })

  it('hat keine A11y-Verstoesse', async () => {
    const { container } = render(
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
