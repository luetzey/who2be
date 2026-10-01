import type { TFunction } from 'i18next'
import type { LucideIcon } from 'lucide-react'
import { Check, CircleDot, Pencil, Plus, RotateCcw, Send, Trash2, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { DashboardActivity, DashboardEntityType } from '@/api/types'
import { cn } from '@/lib/utils'

// Das `event`-Property im Activity-Feed kommt als Free-Form-String (z.B.
// `promoted_to_active`). Bekannte Events stehen unter
// `dashboard:activity.events.*` (Audit A9: vorher fest verdrahtet deutsch,
// auch in der englischen Oberflaeche); unbekannte fallen auf den Roh-String
// zurueck.
const KNOWN_EVENTS: ReadonlySet<string> = new Set([
  'promoted_to_active',
  'submitted_for_review',
  'rejected',
  'returned_to_draft',
  'deactivated',
  'created',
  'updated',
  'deleted',
])

const KNOWN_ENTITIES: ReadonlySet<string> = new Set(['persona', 'playbook', 'resource'])

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

function eventText(t: TFunction<'dashboard'>, event: string | undefined): string {
  if (!event) return t('activity.events.changed')
  if (KNOWN_EVENTS.has(event)) return t(`activity.events.${event}`)
  return event.replaceAll('_', ' ')
}

function entityText(t: TFunction<'dashboard'>, entityType: DashboardEntityType): string {
  if (KNOWN_ENTITIES.has(entityType)) return t(`activity.entityTypes.${entityType}`)
  return entityType
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
  const { t } = useTranslation('dashboard')
  // Defensiv lesen — alte Response-Varianten (vor Phase-3 Track 1) liefern
  // `actor` gar nicht; `display_name` kann null sein, `user_id` faellt am
  // Ende auf „Unbekannt"/„Unknown" zurueck, damit kein crash entsteht.
  const actor = activity.actor ?? null
  const actorName =
    actor?.display_name?.trim() || actor?.user_id || t('activity.unknownActor')
  const entityLabel = entityText(t, activity.entity_type)
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
    // Mobil-Spec M6: Der Satz bricht um statt mit „…“ zu enden. Die Zeile ist
    // kein Link und hat keinen anderen Weg zum Volltext; bei 320 px blieben
    // vorher 75 px sichtbar. `items-start` haelt Avatar und Zeit an der
    // ersten Textzeile, wenn der Satz mehrzeilig wird. Unter `md` steht die
    // Zeit unter dem Satz, sonst nimmt sie ihm gut ein Drittel der Breite.
    <div className="flex items-start gap-3">
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
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 md:flex-row md:gap-3">
        <span
          data-testid="activity-text"
          className="min-w-0 text-sm leading-snug wrap-anywhere md:flex-1"
        >
          <span className="font-medium">{actorName}</span> {eventText(t, activity.event)}{' '}
          <span className="text-muted-foreground">{entityLabel}</span>{' '}
          <span className="font-medium">{entityName}</span>
          {versionHint ? <span className="text-muted-foreground">{versionHint}</span> : null}
        </span>
        <time
          className="text-xs text-muted-foreground md:flex-none md:pt-0.5"
          dateTime={activity.ts}
        >
          {dateLabel}
        </time>
      </div>
    </div>
  )
}
