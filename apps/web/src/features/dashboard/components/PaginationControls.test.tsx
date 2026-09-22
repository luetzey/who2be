import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PaginationControls } from './PaginationControls'

describe('PaginationControls', () => {
  it('rendert nichts, solange es nur eine Seite gibt', () => {
    const { container } = render(
      <PaginationControls page={1} totalPages={1} onPageChange={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  // §4.4 Checklistenpunkt 1: zwei Buttons plus Positionsanzeige passen auf
  // 320px nicht auf eine Zeile, sobald die Anzeige mehrsprachig lang wird.
  // Weiche 2 aus #563: umbrechen lassen (W2-Muster `PageHeader`), keine
  // breakpoint-abhaengige zweite Render-Variante.
  it('laesst die Leiste umbrechen, statt sie auf einer Zeile zu erzwingen', () => {
    render(<PaginationControls page={2} totalPages={5} onPageChange={vi.fn()} />)
    expect(screen.getByRole('navigation')).toHaveClass('flex-wrap')
  })

  // §4.4 Checklistenpunkt 4 / §11 A11y-Minimum: Hit-Targets unterhalb `md`
  // bleiben >= 40px. `size="sm"` liefert `h-9` (36px) — unterhalb `md` wird
  // das auf `h-10` (40px) angehoben und erst ab `md` verdichtet.
  it('haelt die Buttons unterhalb md auf 40px Hit-Target', () => {
    render(<PaginationControls page={2} totalPages={5} onPageChange={vi.fn()} />)
    for (const button of screen.getAllByRole('button')) {
      expect(button).toHaveClass('h-10', 'md:h-9')
    }
  })
})
