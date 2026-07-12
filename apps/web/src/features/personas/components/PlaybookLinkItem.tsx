import { Share2, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { EntityIcon } from '@/components/data/EntityIcon'
import { Button, type ButtonProps } from '@/components/ui/button'

interface PlaybookLinkItemProps {
  /** Playbook-Name — der Titel der Zeile. */
  name: string
  /** Optionaler Status-Slot (StatusBadge), nur in der „Verknüpft"-Liste. */
  status?: ReactNode
  /** Beschriftung der Aktions-Schaltflaeche (z. B. „Verknüpfen"/„Entfernen"). */
  actionLabel: string
  /** Lucide-Icon der Aktion (Plus zum Verknuepfen, X zum Entfernen). */
  actionIcon: LucideIcon
  actionVariant?: ButtonProps['variant']
  onAction: () => void
  disabled?: boolean
}

/**
 * Zeile der Persona-Playbook-Verknuepfung im Bearbeiten-Modus (WP-E,
 * Mockup `pbEditing`). Ersetzt den frueheren Checkbox-Picker: Icon-Kachel +
 * Name (+ optionaler Status) links, eine explizite Add-/Remove-Schaltflaeche
 * rechts. Beide Aktionen laufen ueber `onAction` (= `toggle(id)`), die
 * Verknuepfte-/Verfuegbar-Aufteilung liegt in `PersonaPlaybooksCard`.
 *
 * Hinweis (Daten-Luecke): Persona→Playbook-Links haben — anders als
 * Sub-Resources — KEINE „aus Editor-Text"/managed-Unterscheidung im Modell.
 * Der Mockup-Marker „Aus Editor-Text" wird daher bewusst weggelassen.
 */
export function PlaybookLinkItem({
  name,
  status,
  actionLabel,
  actionIcon: ActionIcon,
  actionVariant = 'outline',
  onAction,
  disabled,
}: PlaybookLinkItemProps) {
  return (
    <li className="flex items-center gap-3 px-3 py-2">
      <EntityIcon icon={Share2} tone="playbook" size="sm" />
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <span className="truncate text-sm font-medium">{name}</span>
        {status}
      </div>
      <Button
        type="button"
        variant={actionVariant}
        size="sm"
        onClick={onAction}
        disabled={disabled}
      >
        <ActionIcon aria-hidden="true" />
        {actionLabel}
      </Button>
    </li>
  )
}
