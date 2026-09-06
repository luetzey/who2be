import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { Info } from 'lucide-react'
import { type ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface InfoTooltipProps {
  /** Tooltip-Inhalt — beliebiger ReactNode (Text, `<pre>`, Listen, etc.). */
  children: ReactNode
  /** Optional eigenes `aria-label` fuer den Trigger. */
  label?: string
  /** Optionaler Override fuer die Tooltip-Seite (default `top`). */
  side?: TooltipPrimitive.TooltipContentProps['side']
  className?: string
}

/**
 * Kleiner Info-Icon-Button mit Tooltip — fuer Hilfetexte, die nicht
 * dauerhaft im Layout liegen sollen (siehe `FormSection.help`). Hover,
 * Focus und Long-Press oeffnen den Tooltip; Escape schliesst ihn.
 * Content wird via Radix-Portal gerendert (keine Layout-Verschiebung).
 */
export function InfoTooltip({
  children,
  label = 'Hilfe einblenden',
  side = 'top',
  className,
}: InfoTooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={150} skipDelayDuration={0}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          <button
            type="button"
            aria-label={label}
            className={cn(
              'inline-flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground transition-colors duration-[var(--duration-fast)] ease-standard hover:bg-accent hover:text-accent-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
              className,
            )}
          >
            <Info className="size-4" aria-hidden="true" />
          </button>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            collisionPadding={8}
            className={cn(
              'w2b-anim-pop z-50 max-w-sm rounded-md border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-popover',
            )}
          >
            {children}
            <TooltipPrimitive.Arrow className="fill-popover" />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}
