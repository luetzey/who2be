import { ArrowLeft, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { EntityIcon, type EntityTone } from './EntityIcon'

// Geteilter Detail-Page-Header (Design-Handoff „Detail-Redesign"). Identischer
// Block in System-Prompt-/Agent-/Resource-Detail: optionaler Zurueck-Link,
// EntityIcon-Kachel, H1, eine Reihe Badges (Slug/Status/Tags) als Slot,
// Beschreibung und ein rechter Action-Slot.
//
// Lebt unter `components/data/`, weil er die geteilte EntityIcon-Kachel + das
// Back-Link-Muster kapselt (ueber PageHeader hinaus).

interface DetailHeaderProps {
  icon: LucideIcon
  iconTone: EntityTone
  title: string
  /** Ziel des Zurueck-Links; ohne diesen Prop wird kein Link gerendert. */
  backHref?: string
  backLabel?: string
  /** Badges neben dem H1 (Slug / StatusBadge / Tags). */
  badges?: ReactNode
  description?: string
  /** Rechter Action-Slot (z. B. „Duplizieren"). */
  actions?: ReactNode
  className?: string
}

export function DetailHeader({
  icon,
  iconTone,
  title,
  backHref,
  backLabel,
  badges,
  description,
  actions,
  className,
}: DetailHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-5', className)}>
      {backHref !== undefined ? (
        <Button asChild variant="ghost" size="sm" className="w-fit gap-2 text-muted-foreground">
          <Link to={backHref}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            {backLabel}
          </Link>
        </Button>
      ) : null}

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-4">
          <EntityIcon icon={icon} tone={iconTone} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
              {badges}
            </div>
            {description !== undefined && description !== '' ? (
              <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
    </div>
  )
}
