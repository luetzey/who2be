import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function Container({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mx-auto w-full max-w-5xl px-4 py-6 sm:px-6', className)} {...props} />
}
