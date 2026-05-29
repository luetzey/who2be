import type { DashboardActivity, DashboardEntityType } from '@/api/types'

// Mapping fuer das `event`-Property im Activity-Feed. Backend liefert das
// als Free-Form-String (z.B. `promoted_to_active`); Frontend uebersetzt
// die bekannten Events ins UI-Vokabular und faellt sonst auf den
// Roh-String zurueck.
const EVENT_LABELS: Record<string, string> = {
  promoted_to_active: 'aktiviert',
  submitted_for_review: 'zur Review eingereicht',
  rejected: 'abgelehnt',
  returned_to_draft: 'zurueck in Draft',
  deactivated: 'deaktiviert',
  created: 'angelegt',
  updated: 'aktualisiert',
  deleted: 'geloescht',
}

const ENTITY_LABELS: Record<DashboardEntityType, string> = {
  persona: 'Persona',
  playbook: 'Playbook',
  resource: 'Resource',
}

function eventText(event: string | undefined): string {
  if (!event) return 'geaendert'
  return EVENT_LABELS[event] ?? event.replaceAll('_', ' ')
}

interface ActivityRowProps {
  activity: DashboardActivity
}

export function ActivityRow({ activity }: ActivityRowProps) {
  // Defensiv lesen — alte Response-Varianten (vor Phase-3 Track 1) liefern
  // `actor` gar nicht; `display_name` kann null sein, `user_id` faellt am
  // Ende auf 'Unbekannt' zurueck, damit kein crash entsteht.
  const actor = activity.actor ?? null
  const actorName =
    actor?.display_name?.trim() || actor?.user_id || 'Unbekannt'
  const entityLabel = ENTITY_LABELS[activity.entity_type] ?? activity.entity_type
  const entityName = activity.entity_name ?? activity.entity_id
  const versionHint =
    activity.to_version !== null && activity.to_version !== undefined
      ? ` (v${activity.to_version})`
      : ''
  const date = activity.ts ? new Date(activity.ts) : null
  const dateLabel =
    date && !Number.isNaN(date.getTime())
      ? date.toLocaleString()
      : (activity.ts ?? '')

  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="min-w-0 truncate">
        <span className="font-medium">{actorName}</span>{' '}
        {eventText(activity.event)}{' '}
        <span className="text-muted-foreground">{entityLabel}</span>{' '}
        <span className="font-medium">{entityName}</span>
        {versionHint}
      </span>
      <time
        className="shrink-0 text-xs text-muted-foreground"
        dateTime={activity.ts}
      >
        {dateLabel}
      </time>
    </div>
  )
}
