import { forwardRef, type HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export interface SectionProps extends HTMLAttributes<HTMLElement> {
  ariaLabel?: string
}

export const Section = forwardRef<HTMLElement, SectionProps>(function Section(
  { className, ariaLabel, ...props },
  ref,
) {
  return (
    <section
      ref={ref}
      aria-label={ariaLabel}
      className={cn('flex flex-col gap-4', className)}
      {...props}
    />
  )
})
