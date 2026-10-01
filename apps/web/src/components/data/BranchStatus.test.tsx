import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { BranchStatus } from './BranchStatus'

describe('BranchStatus', () => {
  it('rendert active + draft als zwei Branch-Nodes', () => {
    render(
      <BranchStatus
        activeVersion={3}
        draftVersion={4}
        currentVersion={4}
        actions={[]}
      />,
    )
    expect(screen.getByTestId('branch-node-active').textContent).toContain('v3 active')
    expect(screen.getByTestId('branch-node-draft').textContent).toContain('v4 draft')
    expect(screen.getByText('(du bearbeitest)')).toBeInTheDocument()
  })

  it('Audit A12: der aktuelle Knoten hat dunkle Schrift auf der Brand-Flaeche, kein text-brand', () => {
    render(<BranchStatus activeVersion={3} draftVersion={4} currentVersion={4} actions={[]} />)
    const current = screen.getByTestId('branch-node-draft')
    expect(current.className).toContain('bg-brand/10')
    expect(current.className).toContain('text-foreground')
    expect(current.className).not.toMatch(/(^|\s)text-brand(\s|$)/)
    // Der Punkt erbt die Schriftfarbe; die Form unterscheidet den aktuellen Stand.
    const dot = current.querySelector('[aria-hidden="true"]')
    expect(dot?.textContent).toBe('●')
    expect(dot?.getAttribute('class') ?? '').not.toContain('text-brand')
    expect(screen.getByTestId('branch-node-active').querySelector('[aria-hidden="true"]')?.textContent).toBe('○')
  })

  it('rendert nur die uebergebenen Actions als Buttons', () => {
    const onClick = vi.fn()
    render(
      <BranchStatus
        currentVersion={1}
        draftVersion={1}
        actions={[
          { key: 'submit', label: 'Draft abschliessen', variant: 'brand', onClick },
        ]}
      />,
    )
    const button = screen.getByRole('button', { name: 'Draft abschliessen' })
    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('rendert eine aria-live Region fuer den Save-Status', () => {
    render(
      <BranchStatus
        currentVersion={1}
        draftVersion={1}
        actions={[]}
        saveState={{ status: 'saving', lastSavedAt: null, errorMessage: null }}
      />,
    )
    const indicator = screen.getByTestId('branch-save-indicator')
    expect(indicator.getAttribute('aria-live')).toBe('polite')
    expect(indicator.textContent).toContain('Speichert')
  })

  it('zeigt eine Error-Message im Save-Indicator', () => {
    render(
      <BranchStatus
        currentVersion={1}
        draftVersion={1}
        actions={[]}
        saveState={{ status: 'error', lastSavedAt: null, errorMessage: 'Netz weg.' }}
      />,
    )
    expect(screen.getByTestId('branch-save-indicator').textContent).toContain('Netz weg.')
  })

  it('rendert kein active-Node, wenn nur draft gesetzt ist', () => {
    render(
      <BranchStatus currentVersion={1} draftVersion={1} actions={[]} />,
    )
    expect(screen.queryByTestId('branch-node-active')).toBeNull()
  })
})
