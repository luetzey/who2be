import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import { type ComponentPropsWithoutRef, type ElementRef, forwardRef } from 'react'

import { cn } from '@/lib/utils'

export const RadioGroup = forwardRef<
  ElementRef<typeof RadioGroupPrimitive.Root>,
  ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Root>
>(function RadioGroup({ className, ...props }, ref) {
  return <RadioGroupPrimitive.Root ref={ref} className={cn('grid gap-2', className)} {...props} />
})

export const RadioGroupItem = forwardRef<
  ElementRef<typeof RadioGroupPrimitive.Item>,
  ComponentPropsWithoutRef<typeof RadioGroupPrimitive.Item>
>(function RadioGroupItem({ className, ...props }, ref) {
  return (
    <RadioGroupPrimitive.Item
      ref={ref}
      className={cn(
        'relative aspect-square h-4 w-4 shrink-0 rounded-full border border-input text-primary ring-offset-background',
        // Hit-Target (design-language.md §11: Floor >= 32px): die sichtbare
        // Box bleibt 16 x 16 px, die klickbare Flaeche waechst per
        // Pseudoelement auf 32 x 32 px. Anders als beim Checkbox-Primitive
        // geht das hier direkt am Control: der Radix-`Item` rendert ein
        // `<button>`, kein replaced element.
        'before:absolute before:top-1/2 before:left-1/2 before:h-8 before:w-8 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[""]',
        'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
        {/* Gefuellter Punkt als Selektions-Indikator — kein Icon-Import noetig
            (analog zum Checkbox-Primitive bleibt das Token-Set: primary). */}
        <span className="h-2 w-2 rounded-full bg-primary" />
      </RadioGroupPrimitive.Indicator>
    </RadioGroupPrimitive.Item>
  )
})
