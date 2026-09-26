import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ResolutionSegments } from './ResolutionSegments'

describe('ResolutionSegments', () => {
  it('markiert den aktuellen Stand und laesst „Offen" als reine Anzeige', () => {
    render(<ResolutionSegments name="Onboarding" value="in_progress" onChange={vi.fn()} />)

    expect(screen.getByRole('button', { name: /In Arbeit — Onboarding/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    // Kein Reopen-Endpunkt: „Offen" markiert nur den Ausgangszustand.
    expect(screen.getByRole('button', { name: /Offen — Onboarding/ })).toBeDisabled()
  })

  // §4.4 Checklistenpunkt 1 (#565): vier Segmente nebeneinander sind auf 320px
  // breiter als die Karte, in der sie sitzen. Weiche 3 (`flex-wrap` statt
  // zweiter Render-Variante) gilt auch hier — die Gruppe bricht um.
  it('laesst die Segment-Gruppe umbrechen, statt sie auf eine Zeile zu erzwingen', () => {
    render(<ResolutionSegments name="Onboarding" value={null} onChange={vi.fn()} />)
    expect(screen.getByRole('group', { name: /Onboarding/ })).toHaveClass('flex-wrap')
  })

  // §11 A11y-Minimum: `h-7` sind 28px und liegen unter dem Floor (>= 32px,
  // Mobile bevorzugt 40px). Unterhalb der Mobile-Schwelle `md` werden die
  // Segmente auf `h-10` (40px) gehoben; die kompakte Desktop-Optik bleibt.
  it('haelt die Segmente unterhalb md auf Hit-Target-Hoehe', () => {
    render(<ResolutionSegments name="Onboarding" value={null} onChange={vi.fn()} />)
    for (const segment of screen.getAllByRole('button')) {
      expect(segment).toHaveClass('h-10', 'md:h-7')
      expect(segment.className).not.toMatch(/(^|\s)h-7(\s|$)/)
    }
  })
})
