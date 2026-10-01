import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './table'

// Tabellen-Muster (Mobil-Spec M11). jsdom rechnet kein Layout: `scrollWidth`
// und `clientWidth` sind dort immer 0. Die Tests setzen deshalb die Masse des
// Scroll-Bereichs selbst (per Prototyp-Getter) und pruefen, was die
// Komponente daraus macht. Die Layout-Aussage selbst (fixierte Spalte,
// Hinweis nur unter md) ist am gebauten Stylesheet in Chromium gemessen und
// steht in `e2e/scroll-guard.spec.ts` („M11“).
let size = { scrollWidth: 0, clientWidth: 0 }
const originals = {
  scrollWidth: Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollWidth'),
  clientWidth: Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth'),
}

beforeEach(() => {
  size = { scrollWidth: 0, clientWidth: 0 }
  Object.defineProperty(HTMLElement.prototype, 'scrollWidth', {
    configurable: true,
    get(this: HTMLElement) {
      return this.dataset.testid === 'table-scroller' ? size.scrollWidth : 0
    },
  })
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get(this: HTMLElement) {
      return this.dataset.testid === 'table-scroller' ? size.clientWidth : 0
    },
  })
})

afterEach(() => {
  for (const key of ['scrollWidth', 'clientWidth'] as const) {
    const descriptor = originals[key]
    if (descriptor !== undefined) Object.defineProperty(HTMLElement.prototype, key, descriptor)
  }
})

function Example() {
  return (
    <section>
      <h2 id="preview-title">Daten</h2>
      <Table labelledBy="preview-title">
        <TableHeader>
          <TableRow>
            <TableHead>Kunde</TableHead>
            <TableHead>Region</TableHead>
            <TableHead>Umsatz</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Kunde 1 GmbH</TableCell>
            <TableCell>Nord</TableCell>
            <TableCell>99,90</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  )
}

describe('Table — Tabellen-Muster (Mobil-Spec M11)', () => {
  it('ohne Ueberlauf: kein Tab-Stopp, keine Region, kein Hinweis', () => {
    size = { scrollWidth: 300, clientWidth: 300 }
    render(<Example />)

    const scroller = screen.getByTestId('table-scroller')
    expect(scroller).not.toHaveAttribute('tabindex')
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
    expect(screen.queryByTestId('table-scroll-hint')).not.toBeInTheDocument()
    expect(screen.queryByTestId('table-scroll-shadow')).not.toBeInTheDocument()
    // Die Tabelle traegt den Namen trotzdem.
    expect(screen.getByRole('table', { name: 'Daten' })).toBeInTheDocument()
  })

  it('mit Ueberlauf: fokussierbare, benannte Region (ACT 0ssw9k), Hinweis und Verlauf', () => {
    size = { scrollWidth: 988, clientWidth: 238 }
    render(<Example />)

    const region = screen.getByRole('region', { name: 'Daten' })
    expect(region).toHaveAttribute('tabindex', '0')
    expect(region).toHaveAttribute('data-overflow', 'true')
    expect(region).toHaveClass('overflow-x-auto', 'overscroll-x-contain')
    // Erste Spalte fixiert — nur im Ueberlauf-Zustand, per data-Attribut.
    expect(region.className).toContain('data-[overflow=true]:[&_tr>*:first-child]:sticky')
    expect(region.className).toContain('data-[overflow=true]:[&_tr>*:first-child]:left-0')

    const hint = screen.getByTestId('table-scroll-hint')
    expect(hint).toHaveTextContent('Seitlich wischen für weitere Spalten')
    // Nur unter md sichtbar.
    expect(hint).toHaveClass('md:hidden')
    expect(screen.getByTestId('table-scroll-shadow')).toHaveAttribute('aria-hidden', 'true')
  })

  it('nach dem Scrollen: Kanten-Schatten an der ersten Spalte, am Ende kein Verlauf', () => {
    size = { scrollWidth: 988, clientWidth: 238 }
    render(<Example />)
    const region = screen.getByRole('region', { name: 'Daten' })
    expect(region).not.toHaveAttribute('data-scrolled')

    act(() => {
      region.scrollLeft = 120
      fireEvent.scroll(region)
    })
    expect(region).toHaveAttribute('data-scrolled', 'true')
    expect(region.className).toContain('data-[scrolled=true]:[&_tr>*:first-child]:after:absolute')
    expect(screen.getByTestId('table-scroll-shadow')).toBeInTheDocument()

    act(() => {
      region.scrollLeft = 750
      fireEvent.scroll(region)
    })
    expect(screen.queryByTestId('table-scroll-shadow')).not.toBeInTheDocument()
  })

  it('faellt ohne labelledBy auf aria-label zurueck', () => {
    size = { scrollWidth: 500, clientWidth: 200 }
    render(
      <Table aria-label="Schema">
        <TableBody>
          <TableRow>
            <TableCell>a</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    )
    expect(screen.getByRole('region', { name: 'Schema' })).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('table', { name: 'Schema' })).toBeInTheDocument()
  })

  it('hat keine axe-Violations im Ueberlauf-Zustand', async () => {
    size = { scrollWidth: 988, clientWidth: 238 }
    const { container } = render(<Example />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
