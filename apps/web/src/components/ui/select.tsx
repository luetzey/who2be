import { forwardRef, type SelectHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement>

// Natives <select> als shadcn-konformes Primitive. Bewusst kein Radix-Select:
// fuer einen kompakten Rollen-Picker reicht das native Control (A11y „for free",
// react-hook-form-kompatibel via Spread). Styling spiegelt <Input> (h-10,
// rounded-md, border-input) — Tokens nur ueber globals.css.
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
})
