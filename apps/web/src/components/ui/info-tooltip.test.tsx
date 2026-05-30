import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { InfoTooltip } from './info-tooltip'

describe('InfoTooltip', () => {
  it('rendert den Icon-Trigger mit deutschem aria-label', () => {
    render(<InfoTooltip>Hilfe-Inhalt</InfoTooltip>)
    expect(
      screen.getByRole('button', { name: 'Hilfe einblenden' }),
    ).toBeInTheDocument()
  })

  it('uebernimmt ein eigenes Label', () => {
    render(<InfoTooltip label="Mehr Infos">Hilfe-Inhalt</InfoTooltip>)
    expect(screen.getByRole('button', { name: 'Mehr Infos' })).toBeInTheDocument()
  })

  it('zeigt den Tooltip-Content erst auf Focus (Portal-Render)', async () => {
    render(<InfoTooltip>Erklaer-Text</InfoTooltip>)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()

    fireEvent.focus(screen.getByRole('button', { name: 'Hilfe einblenden' }))

    await waitFor(() => {
      expect(screen.getAllByRole('tooltip').length).toBeGreaterThan(0)
    })
    // Mindestens eine der Tooltip-Instanzen (sichtbar + SR-only) zeigt den Text.
    const tooltips = screen.getAllByRole('tooltip')
    expect(tooltips.some((node) => node.textContent?.includes('Erklaer-Text'))).toBe(true)
  })

  it('schliesst den Tooltip mit Escape', async () => {
    render(<InfoTooltip>Erklaer-Text</InfoTooltip>)
    const trigger = screen.getByRole('button', { name: 'Hilfe einblenden' })
    fireEvent.focus(trigger)

    await waitFor(() => {
      expect(screen.getAllByRole('tooltip').length).toBeGreaterThan(0)
    })

    fireEvent.keyDown(document.activeElement ?? trigger, { key: 'Escape' })

    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    })
  })

  it('akzeptiert ReactNode-Children — z. B. ein <pre>-Snippet', async () => {
    render(
      <InfoTooltip>
        <pre data-testid="snippet">Code-Beispiel</pre>
      </InfoTooltip>,
    )
    fireEvent.focus(screen.getByRole('button', { name: 'Hilfe einblenden' }))

    await waitFor(() => {
      expect(screen.getAllByTestId('snippet').length).toBeGreaterThan(0)
    })
  })
})
