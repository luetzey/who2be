import { cn } from '@/lib/utils'

import { playbookTypeMeta } from '../lib/typeMeta'

// Quadratischer Typ-Icon-Chip (Design-Handoff §Row/Hero): Pill-Tint je Typ,
// rein dekorativ (aria-hidden) — der Typ steht daneben als Text/Select.

interface PlaybookTypeIconProps {
  type: string | undefined
  className?: string
}

export function PlaybookTypeIcon({ type, className }: PlaybookTypeIconProps) {
  const meta = playbookTypeMeta(type)
  const Icon = meta.icon
  return (
    <span
      className={cn(
        'flex size-10 shrink-0 items-center justify-center rounded-lg',
        meta.tint,
        className,
      )}
      aria-hidden="true"
      data-testid="playbook-type-icon"
    >
      <Icon className="size-5" />
    </span>
  )
}
