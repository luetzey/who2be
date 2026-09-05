import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  type SheetContentProps,
} from './sheet'

function Harness({ side }: { side?: SheetContentProps['side'] }) {
  return (
    <Sheet>
      <SheetTrigger>Oeffnen</SheetTrigger>
      <SheetContent side={side}>
        <SheetHeader>
          <SheetTitle>Panel-Titel</SheetTitle>
          <SheetDescription>Panel-Beschreibung.</SheetDescription>
        </SheetHeader>
        <button type="button">Innere Aktion</button>
      </SheetContent>
    </Sheet>
  )
}

async function openSheet() {
  fireEvent.click(screen.getByRole('button', { name: 'Oeffnen' }))
  return screen.findByRole('dialog')
}

// Radix' `DismissableLayer` haengt seinen `pointerdown`-Outside-Listener erst
// nach einem `setTimeout(0)` ein (verhindert, dass der oeffnende Klick den
// Layer sofort wieder schliesst). Ein Makrotask-Tick zwischen Oeffnen und
// Outside-Interaktion stellt sicher, dass der Listener schon registriert ist.
function flushMacrotask() {
  return new Promise<void>((resolve) => setTimeout(resolve, 0))
}

describe('Sheet', () => {
  it('öffnet per Trigger und schließt per Schließen-Button', async () => {
    render(<Harness />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await openSheet()
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Schließen' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('schließt per Escape', async () => {
    render(<Harness />)
    const dialog = await openSheet()

    fireEvent.keyDown(dialog, { key: 'Escape' })

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('schließt per Klick auf das Overlay', async () => {
    render(<Harness />)
    await openSheet()
    await flushMacrotask()

    // Radix' modaler DismissableLayer verzoegert Outside-Pointerdowns
    // (`deferPointerDownOutside`) und wertet sie erst beim nachfolgenden
    // `click` aus (verhindert, dass ein Drag-Select ausserhalb den Layer
    // schliesst) — daher beide Events, wie im echten Browser-Klick.
    const overlay = screen.getByTestId('sheet-overlay')
    fireEvent.pointerDown(overlay)
    fireEvent.click(overlay)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('trägt role="dialog" und aria-labelledby auf den Titel', async () => {
    render(<Harness />)
    const dialog = await openSheet()
    const title = screen.getByText('Panel-Titel')

    expect(dialog).toHaveAttribute('role', 'dialog')
    expect(dialog).toHaveAttribute('aria-labelledby', title.id)
  })

  it('hält den Fokus im Panel (Focus-Trap)', async () => {
    render(<Harness />)
    const dialog = await openSheet()

    await waitFor(() => {
      expect(dialog.contains(document.activeElement)).toBe(true)
    })

    // Letztes fokussierbares Element im Panel manuell fokussieren und Tab
    // druecken — ohne Trap wuerde der Fokus aus dem Panel herauswandern.
    const focusable = dialog.querySelectorAll<HTMLElement>('button')
    focusable[focusable.length - 1]?.focus()
    fireEvent.keyDown(dialog, { key: 'Tab' })

    expect(dialog.contains(document.activeElement)).toBe(true)
  })

  it.each([['left'], ['right'], ['top'], ['bottom']] as const)(
    'rendert die side=%s-Variante',
    async (side) => {
      render(<Harness side={side} />)
      const dialog = await openSheet()
      expect(dialog).toBeInTheDocument()
      expect(screen.getByText('Panel-Titel')).toBeInTheDocument()
    },
  )
})
