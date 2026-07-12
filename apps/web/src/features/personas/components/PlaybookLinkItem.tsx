import { Quote, Share2, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { EntityIcon } from '@/components/data/EntityIcon'
import { Badge } from '@/components/ui/badge'
import { Button, type ButtonProps } from '@/components/ui/button'

interface PlaybookReferencedBadgeProps {
  /** Sichtbares Label, z. B. „Im Text referenziert". */
  label: string
  /** Erklaerender Hinweistext (native Tooltip via `title`, rein informativ). */
  hint: string
}

/**
 * Kleiner, gedaempfter Info-Badge fuer verknuepfte Playbooks, die zusaetzlich im
 * Persona-Inhalt vorkommen (Identitaets-/Haltungs-Text oder ein Modus). REIN
 * informativ — er sperrt nichts. Anders als der Mockup-Marker „Aus Editor-Text"
 * behauptet er keine managed-/Editor-Herkunft (die es im Datenmodell nicht gibt),
 * sondern spiegelt nur eine tatsaechlich vorhandene Referenz wider.
 */
export function PlaybookReferencedBadge({ label, hint }: PlaybookReferencedBadgeProps) {
  return (
    <Badge variant="outline" title={hint} className="gap-1 font-normal text-muted-foreground">
      <Quote className="size-3 shrink-0" aria-hidden="true" />
      {label}
    </Badge>
  )
}

interface PlaybookLinkItemProps {
  /** Playbook-Name — der Titel der Zeile. */
  name: string
  /** Optionaler Status-Slot (StatusBadge), nur in der „Verknüpft"-Liste. */
  status?: ReactNode
  /**
   * Ob dieses Playbook zusaetzlich im Persona-Inhalt referenziert wird (Modus
   * oder Identitaets-/Haltungs-Text). Zeigt einen rein informativen Badge; das
   * Entfernen bleibt uneingeschraenkt moeglich (kein Lock).
   */
  referenced?: boolean
  /** Label des Referenz-Badges (i18n, aus der Card gereicht). */
  referencedLabel?: string
  /** Hinweistext des Referenz-Badges (i18n, aus der Card gereicht). */
  referencedHint?: string
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
 * Name (+ optionaler Status/Referenz-Badge) links, eine explizite Add-/Remove-
 * Schaltflaeche rechts. Beide Aktionen laufen ueber `onAction` (= `toggle(id)`),
 * die Verknuepfte-/Verfuegbar-Aufteilung liegt in `PersonaPlaybooksCard`.
 *
 * Ehrlicher Referenz-Hinweis statt fingierter Herkunft: Persona→Playbook-Links
 * haben — anders als Sub-Resources — KEINE „aus Editor-Text"/managed-Unter-
 * scheidung im Modell. Der Mockup-Marker „Aus Editor-Text" (managed, nicht
 * entfernbar) wird daher NICHT nachgebaut. Stattdessen zeigt `referenced` einen
 * rein informativen Badge, wenn das Playbook tatsaechlich im Persona-Inhalt
 * vorkommt — ohne das Entfernen zu blockieren.
 */
export function PlaybookLinkItem({
  name,
  status,
  referenced = false,
  referencedLabel,
  referencedHint,
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
        {referenced && referencedLabel !== undefined ? (
          <PlaybookReferencedBadge label={referencedLabel} hint={referencedHint ?? referencedLabel} />
        ) : null}
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
