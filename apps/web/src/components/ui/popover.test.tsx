import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Popover, PopoverContent, PopoverTrigger } from './popover'

// Wie in `dialog.test.tsx`: JSDOM rechnet kein Tailwind, geprueft wird die
// durch `cn()`/tailwind-merge aufgeloeste Klassenliste des Content-Knotens.
const DEFAULT_CAP = 'max-w-[calc(100vw-1rem)]'

function Harness({ className }: { className?: string }) {
  return (
    <Popover>
      <PopoverTrigger>Oeffnen</PopoverTrigger>
      <PopoverContent className={className} data-testid="popover-content">
        Popover-Inhalt
      </PopoverContent>
    </Popover>
  )
}

function contentClasses(className?: string): string[] {
  render(<Harness className={className} />)
  fireEvent.click(screen.getByRole('button', { name: 'Oeffnen' }))
  const classes = screen.getByTestId('popover-content').className.split(/\s+/)
  cleanup()
  return classes
}

describe('PopoverContent — Viewport-Beschraenkung', () => {
  it('kappt die Breite per Default auf die Fensterbreite', () => {
    // 1rem passt zum Default `collisionPadding={8}` (8px je Seite).
    expect(contentClasses()).toContain(DEFAULT_CAP)
  })

  it('haelt eine feste Aufrufer-Breite innerhalb der Fensterbreite', () => {
    // Belegter Defektfall: PlaceholderHelp.tsx setzt `w-96` (384px) und lief
    // damit auf einem 320px-Viewport ueber den Rand.
    const classes = contentClasses('max-h-[70vh] w-96 overflow-auto')

    expect(classes).toContain('w-96')
    expect(classes).toContain(DEFAULT_CAP)
  })

  it.each([
    ['PlaceholderPreviewPopover', 'w-96 max-w-[min(24rem,90vw)]', 'max-w-[min(24rem,90vw)]'],
    ['PickerPopover', 'w-80 max-w-[min(20rem,90vw)]', 'max-w-[min(20rem,90vw)]'],
  ])('laesst den engeren Cap aus %s unveraendert gewinnen', (_name, className, cap) => {
    // Der Default-Cap ist gesetzt ...
    expect(contentClasses()).toContain(DEFAULT_CAP)

    // ... und wird vom engeren Aufrufer-Cap verdraengt: gleiche
    // tailwind-merge-Gruppe (`max-w`), der spaetere Eintrag gewinnt. Die
    // beiden bestehenden Caps wirken also unveraendert weiter.
    const classes = contentClasses(className)
    expect(classes).toContain(cap)
    expect(classes).not.toContain(DEFAULT_CAP)
  })
})
