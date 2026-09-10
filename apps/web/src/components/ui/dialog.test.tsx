import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog'

// Die Viewport-Beschraenkung ist eine reine CSS-Entscheidung im Primitive;
// JSDOM rechnet weder Tailwind noch Layout. Geprueft wird deshalb die durch
// `cn()`/tailwind-merge aufgeloeste Klassenliste des Content-Knotens — genau
// die Stelle, an der die Entscheidung faellt (die 16 Aufrufstellen setzen
// nichts davon).
function Harness({ className }: { className?: string }) {
  return (
    <Dialog>
      <DialogTrigger>Oeffnen</DialogTrigger>
      <DialogContent className={className} data-testid="dialog-content">
        <DialogHeader>
          <DialogTitle>Dialog-Titel</DialogTitle>
          <DialogDescription>Dialog-Beschreibung.</DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}

function contentClasses(className?: string): string[] {
  render(<Harness className={className} />)
  fireEvent.click(screen.getByRole('button', { name: 'Oeffnen' }))
  const classes = screen.getByTestId('dialog-content').className.split(/\s+/)
  cleanup()
  return classes
}

describe('DialogContent — Viewport-Beschraenkung', () => {
  it('laesst auf schmalen Viewports links und rechts Abstand zum Fensterrand', () => {
    const classes = contentClasses()

    // min(100vw - 2rem, 32rem): auf 320px bleiben 16px je Seite sichtbar.
    expect(classes).toContain('w-[calc(100vw-2rem)]')
    expect(classes).not.toContain('w-full')
    expect(classes).toContain('max-w-lg')
  })

  it('bleibt unterhalb sm zentriert und gerundet (kein Fullscreen)', () => {
    const classes = contentClasses()

    expect(classes).toContain('w-[calc(100vw-2rem)]')
    expect(classes).toContain('sm:rounded-lg')
    expect(classes).toContain('top-1/2')
    expect(classes).toContain('left-1/2')
    expect(classes).toContain('-translate-x-1/2')
    expect(classes).toContain('-translate-y-1/2')
    // Kein Fullscreen-Umschalter unter sm.
    expect(classes).not.toContain('inset-0')
    expect(classes).not.toContain('h-full')
  })

  it('begrenzt die Hoehe und scrollt zu hohen Inhalt in sich', () => {
    const classes = contentClasses()

    expect(classes).toContain('max-h-[calc(100vh-2rem)]')
    expect(classes).toContain('overflow-y-auto')
  })

  it('behaelt den Inset, wenn ein Aufrufer max-w ueberschreibt', () => {
    // ResourceBlockLinkPicker.tsx setzt `max-w-3xl`. `w-*` und `max-w-*` sind
    // getrennte tailwind-merge-Gruppen — der Aufrufer verdraengt nur das
    // Default-`max-w`, nie die Viewport-Breite.
    const classes = contentClasses('max-w-3xl')

    expect(classes).toContain('w-[calc(100vw-2rem)]')
    expect(classes).toContain('max-w-3xl')
    expect(classes).not.toContain('max-w-lg')
  })
})
