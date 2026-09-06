import * as SheetPrimitive from '@radix-ui/react-dialog'
import { cva, type VariantProps } from 'class-variance-authority'
import { X } from 'lucide-react'
import {
  type ComponentPropsWithoutRef,
  type ElementRef,
  forwardRef,
  type HTMLAttributes,
} from 'react'

import i18n from '@/i18n'
import { cn } from '@/lib/utils'

// Slide-in-Panel auf derselben Radix-Dialog-Basis wie `dialog.tsx`
// (`@radix-ui/react-dialog`, bereits im Stack) — kein zweites Overlay-System.
// Radix liefert Fokus-Trap, `role="dialog"`/`aria-modal` und die
// `aria-labelledby`-Verdrahtung zu `SheetTitle` automatisch; Escape und
// Overlay-Klick schliessen ueber `Root`/`Overlay` ohne eigenen Code.
//
// Kein Konsument heute (ADR-lose Vorarbeit fuer die Mobile-Wellen) — siehe
// Designsprache §4 „Responsive & Breakpoints".

export const Sheet = SheetPrimitive.Root
export const SheetTrigger = SheetPrimitive.Trigger
export const SheetPortal = SheetPrimitive.Portal
export const SheetClose = SheetPrimitive.Close

export const SheetOverlay = forwardRef<
  ElementRef<typeof SheetPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>
>(function SheetOverlay({ className, ...props }, ref) {
  return (
    <SheetPrimitive.Overlay
      ref={ref}
      data-testid="sheet-overlay"
      className={cn(
        'w2b-anim-overlay-slow fixed inset-0 z-50 bg-black/60',
        className,
      )}
      {...props}
    />
  )
})

const sheetVariants = cva(
  'fixed z-50 flex flex-col gap-4 bg-background p-6 shadow-modal',
  {
    variants: {
      side: {
        top: 'w2b-anim-sheet-top inset-x-0 top-0 border-b rounded-b-xl',
        bottom:
          'w2b-anim-sheet-bottom inset-x-0 bottom-0 border-t rounded-t-xl',
        left: 'w2b-anim-sheet-left inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm rounded-r-xl',
        right:
          'w2b-anim-sheet-right inset-y-0 right-0 h-full w-3/4 border-l sm:max-w-sm rounded-l-xl',
      },
    },
    defaultVariants: {
      side: 'right',
    },
  },
)

export interface SheetContentProps
  extends ComponentPropsWithoutRef<typeof SheetPrimitive.Content>,
    VariantProps<typeof sheetVariants> {}

export const SheetContent = forwardRef<
  ElementRef<typeof SheetPrimitive.Content>,
  SheetContentProps
>(function SheetContent({ side, className, children, ...props }, ref) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content
        ref={ref}
        className={cn(sheetVariants({ side }), className)}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="absolute top-4 right-4 rounded-sm opacity-70 ring-offset-background transition-opacity duration-[var(--duration-fast)] ease-standard hover:opacity-100 focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:outline-none disabled:pointer-events-none">
          <X className="h-4 w-4" />
          <span className="sr-only">{i18n.t('common:actions.close')}</span>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPortal>
  )
})

export function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex flex-col space-y-1.5 text-center sm:text-left', className)} {...props} />
  )
}

export function SheetFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)}
      {...props}
    />
  )
}

export const SheetTitle = forwardRef<
  ElementRef<typeof SheetPrimitive.Title>,
  ComponentPropsWithoutRef<typeof SheetPrimitive.Title>
>(function SheetTitle({ className, ...props }, ref) {
  return (
    <SheetPrimitive.Title
      ref={ref}
      className={cn('text-lg font-semibold tracking-tight text-foreground', className)}
      {...props}
    />
  )
})

export const SheetDescription = forwardRef<
  ElementRef<typeof SheetPrimitive.Description>,
  ComponentPropsWithoutRef<typeof SheetPrimitive.Description>
>(function SheetDescription({ className, ...props }, ref) {
  return (
    <SheetPrimitive.Description
      ref={ref}
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  )
})
