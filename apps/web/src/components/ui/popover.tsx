import * as PopoverPrimitive from '@radix-ui/react-popover'
import { type ComponentPropsWithoutRef, type ElementRef, forwardRef } from 'react'

import { cn } from '@/lib/utils'

/**
 * Minimal-Form eines Anker-Ziels (strukturkompatibel zu Radix' `Measurable`).
 * Erfuellt von DOM-Elementen ebenso wie von virtuellen Caret-Objekten —
 * fuer `PopoverAnchor virtualRef={…}`.
 */
export type Measurable = { getBoundingClientRect: () => DOMRect }

/**
 * Schreibbarer Anker-Ref fuer `virtualRef`. Bewusst ein eigenes Objekt-Typ
 * (nicht `RefObject`, dessen `current` in den React-Typen read-only ist), damit
 * Aufrufer den Anker imperativ setzen koennen (Pill bzw. Caret).
 */
export type AnchorRef = { current: Measurable | null }

// Nicht-blockierendes, schwebendes Panel (Layer 2, design-language §6 —
// `shadow-popover`). Radix-`Root` ist per Default `modal={false}`: kein
// Scroll-Lock/Focus-Trap, Dismiss via Aussenklick/Escape eingebaut. Anker
// wahlweise ueber `PopoverTrigger` oder `PopoverAnchor` (auch `virtualRef`
// fuer externe DOM-Knoten / Caret).
export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export const PopoverAnchor = PopoverPrimitive.Anchor

export const PopoverContent = forwardRef<
  ElementRef<typeof PopoverPrimitive.Content>,
  ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(function PopoverContent(
  { className, align = 'start', sideOffset = 6, collisionPadding = 8, ...props },
  ref,
) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        collisionPadding={collisionPadding}
        className={cn(
          'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 z-50 rounded-lg border bg-popover p-4 text-popover-foreground shadow-popover duration-[var(--duration-fast)] ease-standard outline-none',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
})
