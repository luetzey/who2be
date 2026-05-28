import type { DashboardActivity } from '@/api/types'

// Mapping fuer das `event`-Property im Activity-Feed. Backend liefert das
// als Free-Form-String (z.B. `promoted_to_active`); Frontend uebersetzt
// die bekannten Events ins UI-Vokabular und faellt sonst auf den
// Roh-String zurueck.
const EVENT_LABELS: Record<string, string> = {
  promoted_to_active: 'aktiviert',
  submitted_for_review: 'zur Review eingereicht',
  rejected: 'abgelehnt',
  created: 'angelegt',
  updated: 'aktualisiert',
  deleted: 'geloescht',
}

const ENTITY_LABELS: Record<DashboardActivity['entity_type'], string> = {
  persona: 'Persona',
  playbook: 'Playbook',
}

function eventText(event: string): string {
  return EVENT_LABELS[event] ?? event.replaceAll('_', ' ')
}

interface ActivityRowProps {
  activity: DashboardActivity
}

export function ActivityRow({ activity }: ActivityRowProps) {
  const actorName = activity.actor.display_name ?? activity.actor.user_id
  const entityName = activity.entity_name ?? activity.entity_id
  const versionHint =
    activity.to_version !== null && activity.to_version !== undefined
      ? ` (v${activity.to_version})`
      : ''
  const date = new Date(activity.ts)
  const dateLabel = Number.isNaN(date.getTime())
    ? activity.ts
    : date.toLocaleString()

  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="min-w-0 truncate">
        <span className="font-medium">{actorName}</span>{' '}
        {eventText(activity.event)}{' '}
        <span className="text-muted-foreground">
          {ENTITY_LABELS[activity.entity_type]}
        </span>{' '}
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
