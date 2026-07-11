import { cva, type VariantProps } from 'class-variance-authority'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

// Brand-weiche (Default) bzw. destruktive Callout-Band (Design-Handoff
// „Detail-Redesign" + Dashboard). Fuehrende Icon-Kachel, Titel, Beschreibung,
// rechter Action-Slot. Einsatz: Review-/Entwurf-Banner auf Detail-Pages
// („Version 3 liegt zur Review" → Aktivieren / Zurueck zu Entwurf) und die
// Dashboard-Band „Braucht jetzt deine Aufmerksamkeit".
//
// Der Brand-Charakter kommt aus Flaeche + Border (`bg-brand/10` — etablierter
// Soft-Brand-Move, vgl. PlaybookRow); das Icon bleibt neutral bzw. destruktiv
// (design-language §8: nie `text-brand` auf Icons), die einzige Brand-Fill ist
// eine CTA im `actions`-Slot.

const attentionBannerVariants = cva(
  'flex flex-wrap items-center gap-3 rounded-xl border p-4',
  {
    variants: {
      variant: {
        brand: 'border-brand/25 bg-brand/10',
        destructive: 'border-destructive/30 bg-destructive/10',
      },
    },
    defaultVariants: { variant: 'brand' },
  },
)

const iconTileVariants = cva(
  'inline-flex size-9 flex-none items-center justify-center rounded-lg bg-card shadow-card [&_svg]:size-5',
  {
    variants: {
      variant: {
        brand: 'text-foreground',
        destructive: 'text-destructive',
      },
    },
    defaultVariants: { variant: 'brand' },
  },
)

interface AttentionBannerProps extends VariantProps<typeof attentionBannerVariants> {
  icon: LucideIcon
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function AttentionBanner({
  icon: Icon,
  title,
  description,
  actions,
  variant,
  className,
}: AttentionBannerProps) {
  return (
    <div className={cn(attentionBannerVariants({ variant }), className)}>
      <span className={iconTileVariants({ variant })}>
        <Icon aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">{title}</div>
        {description !== undefined ? (
          <div className="mt-0.5 text-xs text-muted-foreground">{description}</div>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export { attentionBannerVariants }
