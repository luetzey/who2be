import { ChevronRight, type LucideIcon } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { EntityAvatar, EntityIcon, type EntityTone } from './EntityIcon'

// Wiederverwendbare Listen-Karte (Design-Handoff „Karten-Redesign"). Ersetzt die
// bisher pro Feature (System-Prompts / Agents / Resources / Personae) duplizierten
// `renderItem`-Zeilen. Die ganze Karte ist per Stretched-Link klickbar (Titel-Link
// mit `after`-Overlay); rechte Actions und der optionale Expander liegen via
// `relative z-10` bzw. als Geschwister darueber.
//
// Default = schlichte klickbare Karte mit Chevron rechts (System-Prompts/Personae
// brauchen keine Zusatz-Props). Optional: Badges-, Status-, Meta- und Action-Slots
// plus ein zugaenglicher Expander (Sub-Resources / Sub-Playbooks).

interface EntityCardProps {
  icon: LucideIcon
  iconTone: EntityTone
  /** Optionale Initialen-Kachel statt Icon (z. B. Persona-Avatar). */
  avatar?: string
  title: string
  href: string
  /** Slug-/Version-Badges neben dem Titel. */
  badges?: ReactNode
  /** Status-Slot (i. d. R. `<StatusBadge …/>`, inkl. `pendingDraft`). */
  status?: ReactNode
  description?: string
  /** Meta-Zeile: MetaPills / Tags / „Verwendet von N" / „Verlinkt in N". */
  meta?: ReactNode
  /** Rechter Slot (z. B. Split-„Kopieren" oder „Einrichten"). Chevron folgt automatisch. */
  actions?: ReactNode

  // --- Expander (optional, z. B. Sub-Resources / Sub-Playbooks) ---
  /** Aufklappbarer Inhalt. Ohne diesen Prop bleibt die Karte eine einfache Zeile. */
  expandable?: ReactNode
  /** Fettes Label im Toggler (z. B. „2 Sub-Resources"). */
  expandLabel?: ReactNode
  /** Gedimmter Vorschautext im Toggler (z. B. Namen der Kinder). */
  expandSummary?: ReactNode
  /** Icon im Toggler (Default: das Karten-Icon). */
  expandIcon?: LucideIcon
  /** Kontrolliert: offen? (sonst unkontrolliert via `defaultOpen`). */
  open?: boolean
  defaultOpen?: boolean
  onOpenChange?: (open: boolean) => void

  className?: string
  'data-testid'?: string
}

// Innerer Karten-Body (Icon | Text | Actions+Chevron). Als eigene Funktion, damit
// die Expander-Variante ihn als Geschwister des Expanders wiederverwenden kann.
function CardBody({
  icon,
  iconTone,
  avatar,
  title,
  href,
  badges,
  status,
  description,
  meta,
  actions,
  interactiveSurface,
}: Pick<
  EntityCardProps,
  | 'icon'
  | 'iconTone'
  | 'avatar'
  | 'title'
  | 'href'
  | 'badges'
  | 'status'
  | 'description'
  | 'meta'
  | 'actions'
> & { interactiveSurface: boolean }) {
  return (
    <article
      className={cn(
        'relative flex items-center gap-4 p-4',
        interactiveSurface &&
          'rounded-xl border bg-card shadow-card transition-[box-shadow,border-color] duration-[var(--duration-fast)] ease-spring hover:shadow-popover',
      )}
    >
      {avatar !== undefined ? (
        <EntityAvatar initials={avatar} tone={iconTone} size="md" />
      ) : (
        <EntityIcon icon={icon} tone={iconTone} size="md" />
      )}

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={href}
            className="rounded-sm text-sm font-semibold text-foreground after:absolute after:inset-0 after:rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {title}
          </Link>
          {badges}
          {status}
        </div>

        {description !== undefined && description !== '' ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}

        {meta ? <div className="flex flex-wrap items-center gap-2">{meta}</div> : null}
      </div>

      <div className="relative z-10 flex flex-none items-center gap-3">
        {actions}
        <ChevronRight className="size-4 text-muted-foreground/60" aria-hidden="true" />
      </div>
    </article>
  )
}

export function EntityCard({
  icon,
  iconTone,
  avatar,
  title,
  href,
  badges,
  status,
  description,
  meta,
  actions,
  expandable,
  expandLabel,
  expandSummary,
  expandIcon,
  open,
  defaultOpen = false,
  onOpenChange,
  className,
  'data-testid': testId,
}: EntityCardProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen

  const toggle = () => {
    const next = !isOpen
    if (!isControlled) {
      setInternalOpen(next)
    }
    onOpenChange?.(next)
  }

  const body = (
    <CardBody
      icon={icon}
      iconTone={iconTone}
      avatar={avatar}
      title={title}
      href={href}
      badges={badges}
      status={status}
      description={description}
      meta={meta}
      actions={actions}
      interactiveSurface={expandable === undefined}
    />
  )

  if (expandable === undefined) {
    return (
      <div className={className} data-testid={testId}>
        {body}
      </div>
    )
  }

  const ExpandIcon = expandIcon ?? icon
  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border bg-card shadow-card',
        className,
      )}
      data-testid={testId}
    >
      {body}
      <div className="px-4 pb-4">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-expanded={isOpen}
          onClick={toggle}
          className="h-auto w-full justify-start gap-2 rounded-lg bg-pill-catalog/40 px-3 py-2 text-xs font-normal text-pill-catalog-fg hover:bg-pill-catalog/60 hover:text-pill-catalog-fg"
        >
          <ExpandIcon className="size-3.5" aria-hidden="true" />
          {expandLabel !== undefined ? (
            <span className="font-semibold">{expandLabel}</span>
          ) : null}
          {expandSummary !== undefined ? (
            <span className="min-w-0 flex-1 truncate text-left opacity-80">{expandSummary}</span>
          ) : null}
          <ChevronRight
            className={cn(
              'ml-auto size-3.5 transition-transform duration-[var(--duration-fast)] ease-standard',
              isOpen && 'rotate-90',
            )}
            aria-hidden="true"
          />
        </Button>
        {isOpen ? <div className="mt-2">{expandable}</div> : null}
      </div>
    </div>
  )
}
