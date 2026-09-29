import { ArrowLeft, Ellipsis, type LucideIcon } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
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
  /**
   * Audit A13 / Issue #624 (Owner-Entscheidung C): unterhalb `md` liegen die
   * Aktionen hinter einem „Mehr"-Knopf neben dem Titel, damit Statusleiste
   * und erster Inhalt im ersten Viewport stehen. Nur fuer reine
   * Sekundaeraktionen (Feedback, Duplizieren, Export) setzen — traegt der
   * Slot die primaere Aktion der Seite (Agent: „Copy"), bleibt er offen.
   * Ab `md` wirkt der Prop nicht.
   */
  collapseActionsBelowMd?: boolean
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
  collapseActionsBelowMd = false,
  className,
}: DetailHeaderProps) {
  const { t } = useTranslation('common')
  const [actionsOpen, setActionsOpen] = useState(false)
  const actionsId = useId()
  const collapsible = collapseActionsBelowMd && Boolean(actions)

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {backHref !== undefined ? (
        <Button asChild variant="ghost" size="sm" className="w-fit gap-2 text-muted-foreground">
          <Link to={backHref}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            {backLabel}
          </Link>
        </Button>
      ) : null}

      <header className="flex flex-wrap items-start justify-between gap-4">
        {/* `flex-1` (Basis 0) haelt den „Mehr"-Knopf auf dem Phone in der
            Titelzeile, statt ihn bei langem Titel in eine eigene Zeile zu
            umbrechen. Ohne Einklappen bleibt das bisherige Verhalten. */}
        <div className={cn('flex min-w-0 gap-4', collapsible && 'flex-1')}>
          <EntityIcon icon={icon} tone={iconTone} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="min-w-0 text-2xl font-semibold tracking-tight break-words">{title}</h1>
              {badges}
            </div>
            {description !== undefined && description !== '' ? (
              <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
            ) : null}
          </div>
        </div>
        {collapsible ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0 md:hidden"
            aria-label={t('actions.more')}
            aria-expanded={actionsOpen}
            aria-controls={actionsId}
            data-testid="detail-header-more"
            onClick={() => setActionsOpen((open) => !open)}
          >
            <Ellipsis aria-hidden="true" />
          </Button>
        ) : null}
        {actions ? (
          <div
            id={actionsId}
            className={cn(
              'flex-wrap items-center gap-2',
              // Mobile-first (§4.4): Basis ist der Phone-Fall — eingeklappt
              // `hidden`, aufgeklappt eigene volle Zeile; `md:flex` schaltet
              // die Aktionen ab Tablet immer ein.
              collapsible ? cn(actionsOpen ? 'flex w-full' : 'hidden', 'md:flex md:w-auto') : 'flex',
            )}
          >
            {actions}
          </div>
        ) : null}
      </header>
    </div>
  )
}
