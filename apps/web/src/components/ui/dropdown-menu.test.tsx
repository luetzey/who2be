import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it } from 'vitest'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './dropdown-menu'

// Radix DropdownMenu nutzt PointerCapture- und scrollIntoView-APIs, die jsdom
// nicht implementiert. Stub-Polyfill, damit der Trigger oeffnen kann.
beforeAll(() => {
  for (const name of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ]) {
    Object.defineProperty(window.HTMLElement.prototype, name, {
      value: () => undefined,
      configurable: true,
    })
  }
})

// Wie in `dialog.test.tsx`: JSDOM rechnet kein Tailwind, geprueft wird die
// durch `cn()`/tailwind-merge aufgeloeste Klassenliste des Content-Knotens.
const DEFAULT_CAP = 'max-w-[calc(100vw-1rem)]'

function Harness({ className }: { className?: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger data-testid="dropdown-trigger">Oeffnen</DropdownMenuTrigger>
      <DropdownMenuContent className={className} data-testid="dropdown-content">
        <DropdownMenuItem>Eintrag</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function contentClasses(className?: string): string[] {
  render(<Harness className={className} />)
  // Radix oeffnet auf pointerdown+up; in jsdom kommen wir per Enter ans Ziel.
  fireEvent.keyDown(screen.getByTestId('dropdown-trigger'), { key: 'Enter' })
  const classes = screen.getByTestId('dropdown-content').className.split(/\s+/)
  cleanup()
  return classes
}

describe('DropdownMenuContent — Viewport-Beschraenkung', () => {
  it('kappt die Breite per Default auf die Fensterbreite', () => {
    const classes = contentClasses()

    expect(classes).toContain(DEFAULT_CAP)
    // Die Mindestbreite bleibt unangetastet.
    expect(classes).toContain('min-w-32')
  })

  it('behaelt den Cap, wenn ein Aufrufer die Mindestbreite anhebt', () => {
    // WorkspaceSwitcher.tsx setzt `min-w-56` (224px) — andere
    // tailwind-merge-Gruppe als `max-w`, der Cap bleibt wirksam.
    const classes = contentClasses('min-w-56')

    expect(classes).toContain('min-w-56')
    expect(classes).toContain(DEFAULT_CAP)
    expect(classes).not.toContain('min-w-32')
  })
})
