import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TagList } from './TagList'

// Audit A13: unterhalb `md` nach 3 Tags „+n“, Klick klappt im Fluss auf.
// jsdom hat kein Layout — der Breakpoint ist ein Klassen-Vertrag (`hidden`
// + `md:contents` bzw. `md:hidden`); die Wirkung im Browser ist im Handoff
// der Karte t_648b4527 gemessen.

const TAGS = ['a', 'b', 'c', 'd', 'e']
const renderTag = (tag: string) => <span data-testid={`tag-${tag}`}>{tag}</span>

describe('TagList', () => {
  it('zeigt unter md drei Tags und „+n“ fuer den Rest', () => {
    render(<TagList tags={TAGS} renderTag={renderTag} />)
    const rest = screen.getByTestId('tag-list-rest')
    const more = screen.getByRole('button', { name: '2 weitere anzeigen' })

    expect(more).toHaveTextContent('+2')
    expect(more).toHaveClass('md:hidden')
    expect(more).toHaveAttribute('aria-expanded', 'false')
    expect(more).toHaveAttribute('aria-controls', rest.id)
    // Eingeklappt `hidden` (nicht im A11y-Tree), ab `md` immer da.
    expect(rest).toHaveClass('hidden', 'md:contents')
    for (const tag of ['a', 'b', 'c']) {
      expect(rest).not.toContainElement(screen.getByTestId(`tag-${tag}`))
    }
    for (const tag of ['d', 'e']) {
      expect(rest).toContainElement(screen.getByTestId(`tag-${tag}`))
    }
  })

  it('klappt per Klick auf und wieder zu, der Knopf bleibt fokussierbar', () => {
    render(<TagList tags={TAGS} renderTag={renderTag} />)
    const more = screen.getByTestId('tag-list-more')
    const rest = screen.getByTestId('tag-list-rest')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(more).toHaveTextContent('Weniger anzeigen')
    expect(rest).not.toHaveClass('hidden')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'false')
    expect(rest).toHaveClass('hidden')
  })

  it('liegt ueber dem Stretched-Link einer Karte, 44 px Trefferflaeche', () => {
    render(<TagList tags={TAGS} renderTag={renderTag} />)
    expect(screen.getByTestId('tag-list-more')).toHaveClass('relative', 'z-10', 'h-11')
  })

  it('rendert ohne Ueberhang keinen Knopf', () => {
    render(<TagList tags={['a', 'b', 'c']} renderTag={renderTag} />)
    expect(screen.queryByTestId('tag-list-more')).not.toBeInTheDocument()
    expect(screen.getByTestId('tag-c')).toBeInTheDocument()
  })

  it('rendert ohne Tags nichts', () => {
    const { container } = render(<TagList tags={[]} renderTag={renderTag} />)
    expect(container).toBeEmptyDOMElement()
  })
})
