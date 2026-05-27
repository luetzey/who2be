import type { ComponentType, ReactNode, SVGProps } from 'react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  className?: string
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-muted/30 px-6 py-10 text-center',
        className,
      )}
    >
      {Icon ? (
        <Icon className="size-12 text-muted-foreground/60" aria-hidden="true" />
      ) : null}
      <div className="space-y-1">
        <p className="text-sm font-medium">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  )
}
