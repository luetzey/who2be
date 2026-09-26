import { Check } from 'lucide-react'
import { forwardRef, type InputHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

// Hit-Target (docs/frontend/design-language.md §11: Floor >= 32px): die
// sichtbare Box bleibt 16 x 16 px, die klickbare Flaeche ist es nicht.
// Deshalb sind Optik und Hitbox getrennt — der Huell-`span` traegt Rahmen,
// Fuellung und Fokus-Ring, der `input` ist eine transparente, ueber der Box
// zentrierte 32 x 32-px-Flaeche.
//
// Warum nicht anders geloest (jeweils gemessen):
//  - Ein Pseudoelement am `input` waere der naheliegende Weg, rendert aber
//    nicht: `<input>` ist ein replaced element (Hitbox blieb 16,5 px).
//  - `p-2` am `span` vergroessert die Box und damit die Zeilenhoehe auf 32 px,
//    ohne die Hitbox zu vergroessern — der `span` ist kein Control.
// Die Zustaende haengen jetzt per `has-[…]` am Elternknoten statt per
// `peer-[…]`: `peer-*` braucht ein Geschwister, der `span` ist aber der
// Elternknoten des `input`.
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, ...props },
  ref,
) {
  return (
    <span
      className={cn(
        'relative inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-input bg-background ring-offset-background has-[:checked]:border-primary has-[:checked]:bg-primary has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2 has-[:disabled]:opacity-50',
        className,
      )}
    >
      <input
        ref={ref}
        type="checkbox"
        className="peer absolute top-1/2 left-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 cursor-pointer appearance-none rounded-sm focus-visible:outline-none disabled:cursor-not-allowed"
        {...props}
      />
      <Check className="pointer-events-none h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100" />
    </span>
  )
})
