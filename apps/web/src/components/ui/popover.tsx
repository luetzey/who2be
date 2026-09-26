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
          // Breiten-Cap passend zum Default `collisionPadding={8}`: der Panel
          // bleibt auf schmalen Viewports innerhalb der Fensterbreite, auch
          // wenn ein Aufrufer eine feste `w-*` setzt. Engere Aufrufer-Caps
          // stehen im `className` dahinter und gewinnen ueber tailwind-merge.
          //
          // Hoehen-Cap als Gegenstueck (Befund B8): Radix' `size`-Middleware
          // schreibt den tatsaechlich verfuegbaren Platz als
          // `--radix-popper-available-height` an den Content-Knoten, den
          // Popover als `--radix-popover-content-available-height`
          // re-exportiert. Das beruecksichtigt Ankerposition und
          // `collisionPadding` — eine feste `vh`-Pauschale nicht. `max-h` +
          // `overflow-y-auto` laesst zu hohen Inhalt in sich scrollen, statt
          // ihn unter die Viewport-Unterkante zu schieben; der Popper-Wrapper
          // ist `position: fixed`, dort rettet kein Dokument-Scroll. Gleiches
          // Muster wie `dialog.tsx`. Bewusst KEIN zweites `max-h-*` hier —
          // `cn()` laeuft ueber tailwind-merge, zwei `max-h-*` im selben
          // String loeschen einander aus.
          'w2b-anim-pop z-50 max-h-[var(--radix-popover-content-available-height)] max-w-[calc(100vw-1rem)] overflow-y-auto rounded-lg border bg-popover p-4 text-popover-foreground shadow-popover outline-none',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
})
