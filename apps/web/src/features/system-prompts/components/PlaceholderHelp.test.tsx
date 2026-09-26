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

// Responsive-Audit #566 (W3, Epic #431). jsdom hat kein Layout — geprueft wird
// der Klassen-Vertrag; die Layout-Aussagen sind am gerenderten Baum belegt
// (Plandatei .claude/plan/2026-09-23-0700_566-…): bei 320px Viewport misst das
// Popover 304px (left 8 / right 312), und ein trennstellenfreier
// Platzhaltername laesst body.scrollWidth auf 465 springen, waehrend das Icon
// auf Breite 0 gequetscht wird.
describe('PlaceholderHelp — 320px (#566)', () => {
  // AK 2: der Cap sitzt im Primitive (W2/#513, Weiche 1) — `w-96` an der
  // Aufrufstelle bleibt unveraendert und loescht ihn nicht aus, weil `w-*` und
  // `max-w-*` verschiedene tailwind-merge-Familien sind.
  it('rendert das Popover mit dem Primitive-Cap neben der unveraenderten w-96', () => {
    open()
    const classes = screen.getByTestId('placeholder-help').className.split(/\s+/)
    expect(classes).toContain('max-w-[calc(100vw-1rem)]')
    expect(classes).toContain('w-96')
  })

  // AK 6 / Weiche 3: lange Platzhalternamen kuerzen kontrolliert, statt
  // umzubrechen — ein umgebrochenes `/Playbook-Katalog` waere nicht mehr als
  // ein Token lesbar. Der Volltext bleibt ueber `title` erreichbar.
  it('kuerzt lange Platzhalternamen kontrolliert statt sie umzubrechen', () => {
    open()
    const name = screen.getByText('/Playbook-Katalog')
    const classes = name.className.split(/\s+/)
    expect(classes).toContain('truncate')
    expect(classes).toContain('min-w-0')
    expect(name).toHaveAttribute('title', '/Playbook-Katalog')
  })

  it('haelt die dt-Zelle schrumpffaehig und das Icon in voller Groesse', () => {
    open()
    const dt = screen.getByText('/Playbook-Katalog').closest('dt')
    expect(dt?.className.split(/\s+/)).toContain('min-w-0')
    const icon = dt?.querySelector('svg')
    expect(icon?.getAttribute('class')?.split(/\s+/)).toContain('shrink-0')
  })
})
