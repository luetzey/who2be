import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { LegalLayout } from './LegalLayout'

// Responsive-Audit #567 (W3, Epic #431): Weiche 5 des Issues. Kein gemessener
// Defekt (die Kopfzeile passt auf 320px), aber vorentschieden und ohne
// Nebenwirkung — Muster `PageHeader.tsx#PageHeader`.
describe('LegalLayout — 320px (#567)', () => {
  it('laesst die Kopfzeile umbrechen statt zu ueberlaufen', () => {
    render(
      <MemoryRouter>
        <LegalLayout />
      </MemoryRouter>,
    )

    const row = screen.getByRole('link', { name: 'Who2Be' }).parentElement as HTMLElement
    const classes = row.className.split(/\s+/)
    expect(classes).toContain('flex-wrap')
    expect(classes).toContain('gap-x-4')
    expect(classes).toContain('gap-y-1')
  })
})
