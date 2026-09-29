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
          // Kontrast (Audit A4, WCAG 1.4.3): `text-muted-foreground` auf der
          // Brand-Flaeche mass 4,31:1 bei 12 px. `text-foreground/80` bleibt
          // sichtbar sekundaer und liegt in beiden Themes ueber 4,5:1.
          <div className="mt-0.5 text-xs text-foreground/80">{description}</div>
        ) : null}
      </div>
      {actions ? (
        // `min-w-0 max-w-full`: lange Link-Beschriftungen (Audit A4, Direktlinks
        // mit Entitaetsnamen) kuerzen statt auf 390 px aus dem Banner zu laufen.
        <div className="flex max-w-full min-w-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  )
}

export { attentionBannerVariants }
