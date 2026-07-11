import { FileText, GitBranch, Server, Users, type LucideIcon } from 'lucide-react'

import type { FeedbackEntityType, FeedbackTarget } from '@/api/types'
import type { EntityTone } from '@/components/data'

// Icon + Pill-Ton je Feedback-Element-Typ. Ein Ort fuer die Zuordnung, die
// Posteingang, Kurations-Liste und Detail-Seite gemeinsam nutzen. Bewusst im
// Feature (keine neue geteilte Komponente).

interface EntityMeta {
  icon: LucideIcon
  tone: EntityTone
  /** Listen-Pfad-Segment der Element-Detailseite. */
  segment: FeedbackTarget | null
}

const META: Record<FeedbackEntityType, EntityMeta> = {
  persona: { icon: Users, tone: 'persona', segment: 'persona' },
  playbook: { icon: GitBranch, tone: 'playbook', segment: 'playbook' },
  resource: { icon: FileText, tone: 'resource', segment: 'resource' },
  // Zielloses System-/MCP-Feedback hat kein Element → kein Segment, tools-Ton.
  system: { icon: Server, tone: 'tools', segment: null },
}

export function entityMeta(type: FeedbackEntityType): EntityMeta {
  return META[type]
}

// entity_type → Listen-Pfad-Segment der Element-Detailseite (Plural-Route).
export const DETAIL_SEGMENT: Record<FeedbackTarget, string> = {
  persona: 'personas',
  playbook: 'playbooks',
  resource: 'resources',
}
