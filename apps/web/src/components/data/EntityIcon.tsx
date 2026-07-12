import { cva, type VariantProps } from 'class-variance-authority'
import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

// Farbige, abgerundete Icon-Kachel (Design-Handoff „Karten-Redesign"). Traegt
// die kategorie-spezifische Pill-Tinte (`--pill-{tone}-bg`/`-fg`) und ist rein
// dekorativ — das Icon ist `aria-hidden`, den Kontext liefert der Titel daneben.
//
// Lebt unter `components/data/`, weil sie ueber alle Listen-/Detail-Features
// geteilt wird und semantisch Datendarstellung ist (Muster: StatusBadge).

// Kategorie-Tinten aus globals.css (§2.4 Erweiterungsklausel). Geteilter Typ,
// den MetaPill / EntityCard / DetailHeader / UsedByList mitbenutzen.
export type EntityTone = 'playbook' | 'resource' | 'persona' | 'date' | 'tools' | 'catalog'

export type EntityIconSize = 'sm' | 'md' | 'lg'

const entityIconVariants = cva('inline-flex flex-none items-center justify-center', {
  variants: {
    tone: {
      playbook: 'bg-pill-playbook text-pill-playbook-fg',
      resource: 'bg-pill-resource text-pill-resource-fg',
      persona: 'bg-pill-persona text-pill-persona-fg',
      date: 'bg-pill-date text-pill-date-fg',
      tools: 'bg-pill-tools text-pill-tools-fg',
      catalog: 'bg-pill-catalog text-pill-catalog-fg',
    },
    size: {
      // sm ~ Sub-Resource-Kachel, md ~ Listen-Karte (44px), lg ~ Detail-Header (48px).
      sm: 'size-8 rounded-md',
      md: 'size-11 rounded-xl',
      lg: 'size-12 rounded-xl',
    },
  },
  defaultVariants: { tone: 'tools', size: 'md' },
})

const iconSizeClass: Record<EntityIconSize, string> = {
  sm: 'size-4',
  md: 'size-5',
  lg: 'size-6',
}

interface EntityIconProps extends VariantProps<typeof entityIconVariants> {
  icon: LucideIcon
  tone: EntityTone
  className?: string
}

export function EntityIcon({ icon: Icon, tone, size, className }: EntityIconProps) {
  const resolvedSize: EntityIconSize = size ?? 'md'
  return (
    <span className={cn(entityIconVariants({ tone, size: resolvedSize }), className)}>
      <Icon className={iconSizeClass[resolvedSize]} aria-hidden="true" />
    </span>
  )
}

// Text-Schriftgroesse je Kachelgroesse — die Initialen sollen die Kachel fuellen
// wie das Icon in EntityIcon.
const avatarTextClass: Record<EntityIconSize, string> = {
  sm: 'text-[11px]',
  md: 'text-sm',
  lg: 'text-base',
}

// Ableiten der Initialen aus einem Namen (max. zwei Zeichen, Grossbuchstaben).
export function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

interface EntityAvatarProps extends VariantProps<typeof entityIconVariants> {
  initials: string
  tone: EntityTone
  className?: string
}

// Wie EntityIcon, zeigt aber Initialen statt eines Icons (Design-Handoff:
// Persona-Kachel). Dekorativ — den Kontext liefert der Name daneben.
export function EntityAvatar({ initials, tone, size, className }: EntityAvatarProps) {
  const resolvedSize: EntityIconSize = size ?? 'md'
  return (
    <span
      className={cn(
        entityIconVariants({ tone, size: resolvedSize }),
        'font-semibold',
        avatarTextClass[resolvedSize],
        className,
      )}
      aria-hidden="true"
    >
      {initials}
    </span>
  )
}

export { entityIconVariants }
