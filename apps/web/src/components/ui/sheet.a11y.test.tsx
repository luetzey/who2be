import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  type SheetContentProps,
} from './sheet'

// `SheetContent` portalt nach `document.body` (Radix-Portal) — ausserhalb des
// `container`, den `render()` zurueckgibt. Deshalb scannt axe hier bewusst
// `document.body`, nicht nur `container` (siehe `tabs.a11y.test.tsx` fuer das
// Nicht-Portal-Pendant).
function Harness({ side }: { side?: SheetContentProps['side'] }) {
  return (
    <Sheet defaultOpen>
      <SheetContent side={side}>
        <SheetHeader>
          <SheetTitle>Filter</SheetTitle>
          <SheetDescription>Grenze die Liste ein.</SheetDescription>
        </SheetHeader>
      </SheetContent>
    </Sheet>
  )
}

describe('Sheet (a11y)', () => {
  it('hat keine axe-Violations im offenen Zustand', async () => {
    render(<Harness />)
    await screen.findByRole('dialog')

    expect(await axe(document.body)).toHaveNoViolations()
  })

  it.each([['left'], ['right'], ['top'], ['bottom']] as const)(
    'hat keine axe-Violations fuer side=%s',
    async (side) => {
      render(<Harness side={side} />)
      await screen.findByRole('dialog')

      expect(await axe(document.body)).toHaveNoViolations()
    },
  )
})
