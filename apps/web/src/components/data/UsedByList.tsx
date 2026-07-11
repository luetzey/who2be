import { ChevronRight, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

import { EntityIcon, type EntityTone } from './EntityIcon'

// Geteiltes Backlink-Listen-Muster (verallgemeinert `ResourceUsedByList` +
// `ComposedByList`): eine Liste von Link-Zeilen, jede mit optionaler
// EntityIcon-Kachel, Name und optionalem rechtsbuendigen Label/Count
// (z. B. „2 Bloecke", „Sub-Resource"). Die ganze Zeile ist per Stretched-Link
// klickbar (Row-Affordance analog DataList).

export interface UsedByEntry {
  id: string
  name: string
  href: string
  /** Fuehrende Icon-Kachel (optional). */
  icon?: LucideIcon
  iconTone?: EntityTone
  /** Rechtsbuendiges Label/Count (z. B. MetaPill oder Text). */
  meta?: ReactNode
}

interface UsedByListProps {
  items: UsedByEntry[]
  /** Anzeige bei leerer Liste (z. B. `<p>Noch nicht verlinkt.</p>`). */
  empty?: ReactNode
  'aria-label'?: string
  className?: string
}

export function UsedByList({ items, empty, className, ...props }: UsedByListProps) {
  if (items.length === 0) {
    return empty !== undefined ? <>{empty}</> : null
  }

  return (
    <ul className={cn('flex flex-col gap-1', className)} aria-label={props['aria-label']}>
      {items.map((entry) => (
        <li key={entry.id} className="relative">
          <div className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/40">
            {entry.icon !== undefined ? (
              <EntityIcon
                icon={entry.icon}
                tone={entry.iconTone ?? 'resource'}
                size="sm"
              />
            ) : null}
            <Link
              to={entry.href}
              className="min-w-0 flex-1 truncate rounded-sm font-medium text-foreground after:absolute after:inset-0 after:rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              {entry.name}
            </Link>
            {entry.meta !== undefined ? (
              <span className="relative z-10 flex-none text-xs text-muted-foreground">
                {entry.meta}
              </span>
            ) : null}
            <ChevronRight
              className="size-4 flex-none text-muted-foreground/60"
              aria-hidden="true"
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
