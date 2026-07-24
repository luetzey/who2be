import { cva, type VariantProps } from 'class-variance-authority'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import type { EntityTone } from './EntityIcon'

// Kleine Inline-Pille: optionales Lucide-Icon + Text. Zwei Anwendungsmuster aus
// dem Design-Handoff:
//   1. neutrale `muted`-Pille mit tonal gefaerbtem Icon (Agent-Meta:
//      Persona/Template/Playbook) — via `iconTone`.
//   2. voll tonale Pille (Resource-Tags) — via `tone="resource"` o. ae.
// Dazu ein `destructive`-Ton fuer Warn-Marker („Persona fehlt").
//
// Lebt unter `components/data/` (geteilte Datendarstellung, Muster: StatusBadge).

const metaPillVariants = cva(
  'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      tone: {
        muted: 'bg-muted text-foreground',
        playbook: 'bg-pill-playbook text-pill-playbook-fg',
        resource: 'bg-pill-resource text-pill-resource-fg',
        persona: 'bg-pill-persona text-pill-persona-fg',
        date: 'bg-pill-date text-pill-date-fg',
        tools: 'bg-pill-tools text-pill-tools-fg',
        catalog: 'bg-pill-catalog text-pill-catalog-fg',
        destructive: 'bg-destructive/10 text-destructive',
        // Aufmerksamkeits-Marker (Brand-Flaeche wie AttentionBanner §8:
        // Tinte bleibt Foreground, nie text-brand auf Icons).
        brand: 'bg-brand/10 text-foreground',
      },
    },
    defaultVariants: { tone: 'muted' },
  },
)

// Icon-Only-Tinte fuer das `muted`-Muster (Icon traegt die Kategorie-Farbe,
// die Pille bleibt neutral).
const iconToneClass: Record<EntityTone, string> = {
  playbook: 'text-pill-playbook-fg',
  resource: 'text-pill-resource-fg',
  persona: 'text-pill-persona-fg',
  date: 'text-pill-date-fg',
  tools: 'text-pill-tools-fg',
  catalog: 'text-pill-catalog-fg',
}

interface MetaPillProps extends VariantProps<typeof metaPillVariants> {
  icon?: LucideIcon
  /** Faerbt nur das Icon (fuer das neutrale `muted`-Muster). */
  iconTone?: EntityTone
  children: ReactNode
  className?: string
}

export function MetaPill({ icon: Icon, iconTone, tone, className, children }: MetaPillProps) {
  return (
    <span className={cn(metaPillVariants({ tone }), className)}>
      {Icon ? (
        <Icon
          className={cn('size-3.5', iconTone ? iconToneClass[iconTone] : undefined)}
          aria-hidden="true"
        />
      ) : null}
      {children}
    </span>
  )
}

export { metaPillVariants }
