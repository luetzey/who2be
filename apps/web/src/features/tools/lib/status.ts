// Spiegel der Status-State-Machine aus packages/models (Phase 2.1b §2.1.G).
// Bewusst pro Feature dupliziert — ESLint untersagt Cross-Feature-Imports,
// und ein gemeinsames @/lib/status.ts wuerde diese Klausel umgehen. Drift
// wird ueber StatusActionBar-Tests in allen Features ausgeglichen (siehe
// features/resources/lib/status.ts, dessen Muster hier 1:1 gespiegelt wird).

import type { VersionStatus } from '@/api/types'
import i18n from '@/i18n'

export const VERSION_STATUSES: readonly VersionStatus[] = [
  'draft',
  'review',
  'active',
  'inactive',
] as const

// `inactive → draft` reaktiviert inaktive Tool-Versionen wieder als Entwurf.
// Andere Transitionen wie bei Persona/Playbook/Resource.
export const ALLOWED_TRANSITIONS: Record<VersionStatus, readonly VersionStatus[]> = {
  draft: ['review'],
  review: ['active', 'draft'],
  active: [],
  inactive: ['draft'],
}

export type StatusBadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline'

export function statusLabel(status: VersionStatus): string {
  switch (status) {
    case 'draft':
      return i18n.t('common:status.draft')
    case 'review':
      return i18n.t('common:status.review')
    case 'active':
      return i18n.t('common:status.active')
    case 'inactive':
      return i18n.t('common:status.inactive')
  }
}

export function statusBadgeVariant(status: VersionStatus): StatusBadgeVariant {
  switch (status) {
    case 'active':
      return 'default'
    case 'review':
      return 'secondary'
    case 'draft':
    case 'inactive':
      return 'outline'
  }
}

export function canTransition(from: VersionStatus, to: VersionStatus): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to)
}
