import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { ImpressumPage } from './ImpressumPage'

describe('ImpressumPage', () => {
  it('rendert die Pflicht-Ueberschrift und sichtbare Platzhalter', () => {
    const { getByRole, container } = render(
      <MemoryRouter>
        <ImpressumPage />
      </MemoryRouter>,
    )
    expect(getByRole('heading', { level: 1, name: /Impressum/i })).toBeInTheDocument()
    expect(container.querySelectorAll('[data-placeholder]').length).toBeGreaterThan(0)
  })

  it('hat keine A11y-Verstoesse', async () => {
    const { container } = render(
      <MemoryRouter>
        <ImpressumPage />
      </MemoryRouter>,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
