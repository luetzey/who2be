import { Check } from 'lucide-react'
import { forwardRef, type InputHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, ...props },
  ref,
) {
  return (
    <span className={cn('relative inline-flex h-4 w-4 shrink-0 items-center justify-center', className)}>
      <input
        ref={ref}
        type="checkbox"
        className="peer absolute inset-0 h-4 w-4 cursor-pointer appearance-none rounded-sm border border-input bg-background ring-offset-background checked:border-primary checked:bg-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        {...props}
      />
      <Check className="pointer-events-none h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100" />
    </span>
  )
})
