import type { LucideIcon } from 'lucide-react'
import { Check, CircleDot, Pencil, Plus, RotateCcw, Send, Trash2, X } from 'lucide-react'

import type { DashboardActivity, DashboardEntityType } from '@/api/types'
import { cn } from '@/lib/utils'

// Mapping fuer das `event`-Property im Activity-Feed. Backend liefert das
// als Free-Form-String (z.B. `promoted_to_active`); Frontend uebersetzt
// die bekannten Events ins UI-Vokabular und faellt sonst auf den
// Roh-String zurueck.
const EVENT_LABELS: Record<string, string> = {
  promoted_to_active: 'aktivierte',
  submitted_for_review: 'reichte zur Review ein',
  rejected: 'lehnte ab',
  returned_to_draft: 'setzte zurueck zu Entwurf',
  deactivated: 'deaktivierte',
  created: 'erstellte',
  updated: 'aktualisierte',
  deleted: 'loeschte',
}

const ENTITY_LABELS: Record<DashboardEntityType, string> = {
  persona: 'Persona',
  playbook: 'Playbook',
  resource: 'Resource',
}

// Avatar-Tinte nach Entity-Typ (Pill-Token-Klassen — statisch, damit Tailwind
// sie behaelt; kein dynamischer Klassen-String).
const AVATAR_TONE: Record<DashboardEntityType, string> = {
  persona: 'bg-pill-persona text-pill-persona-fg',
  playbook: 'bg-pill-playbook text-pill-playbook-fg',
  resource: 'bg-pill-resource text-pill-resource-fg',
}

// Status-Punkt am Avatar: Event → Farb-Token + Icon. Reine Verstaerkung des
// bereits im Text stehenden Events (Farbe ist nie das alleinige Signal, §11).
const EVENT_DOT: Record<string, { color: string; icon: LucideIcon }> = {
  promoted_to_active: { color: 'var(--status-active)', icon: Check },
  submitted_for_review: { color: 'var(--status-review)', icon: Send },
  rejected: { color: 'var(--destructive)', icon: X },
  returned_to_draft: { color: 'var(--status-draft)', icon: RotateCcw },
  deactivated: { color: 'var(--status-inactive)', icon: CircleDot },
  created: { color: 'var(--status-draft)', icon: Plus },
  updated: { color: 'var(--status-active)', icon: Pencil },
  deleted: { color: 'var(--destructive)', icon: Trash2 },
}

function eventText(event: string | undefined): string {
  if (!event) return 'aenderte'
  return EVENT_LABELS[event] ?? event.replaceAll('_', ' ')
}

// Initialen aus dem Anzeigenamen (max. zwei Buchstaben, gross).
function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  const letters = parts.slice(0, 2).map((part) => part[0])
  return letters.join('').toUpperCase()
}

interface ActivityRowProps {
  activity: DashboardActivity
}

export function ActivityRow({ activity }: ActivityRowProps) {
  // Defensiv lesen — alte Response-Varianten (vor Phase-3 Track 1) liefern
  // `actor` gar nicht; `display_name` kann null sein, `user_id` faellt am
  // Ende auf 'Unbekannt' zurueck, damit kein crash entsteht.
  const actor = activity.actor ?? null
  const actorName = actor?.display_name?.trim() || actor?.user_id || 'Unbekannt'
  const entityLabel = ENTITY_LABELS[activity.entity_type] ?? activity.entity_type
  const entityName = activity.entity_name ?? activity.entity_id
  const versionHint =
    activity.to_version !== null && activity.to_version !== undefined
      ? ` v${activity.to_version}`
      : ''
  const date = activity.ts ? new Date(activity.ts) : null
  const dateLabel =
    date && !Number.isNaN(date.getTime()) ? date.toLocaleString() : (activity.ts ?? '')

  const dot = EVENT_DOT[activity.event] ?? { color: 'var(--status-inactive)', icon: CircleDot }
  const DotIcon = dot.icon

  return (
    <div className="flex items-center gap-3">
      <span className="relative flex-none" aria-hidden="true">
        <span
          className={cn(
            'flex size-8 items-center justify-center rounded-full text-xs font-semibold',
            AVATAR_TONE[activity.entity_type] ?? 'bg-muted text-muted-foreground',
          )}
        >
          {initialsOf(actorName)}
        </span>
        <span
          className="absolute -right-0.5 -bottom-0.5 flex size-4 items-center justify-center rounded-full border-2 border-card text-background [&_svg]:size-2.5"
          style={{ backgroundColor: dot.color }}
        >
          <DotIcon />
        </span>
      </span>
      <span className="min-w-0 flex-1 truncate text-sm leading-snug">
        <span className="font-medium">{actorName}</span> {eventText(activity.event)}{' '}
        <span className="text-muted-foreground">{entityLabel}</span>{' '}
        <span className="font-medium">{entityName}</span>
        {versionHint ? <span className="text-muted-foreground">{versionHint}</span> : null}
      </span>
      <time className="flex-none text-xs text-muted-foreground" dateTime={activity.ts}>
        {dateLabel}
      </time>
    </div>
  )
}
