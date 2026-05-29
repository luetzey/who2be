// Spiegel der Status-State-Machine aus packages/models (Phase 2.1b §2.1.G).
// Bewusst pro Feature dupliziert — ESLint untersagt Cross-Feature-Imports,
// und ein gemeinsames @/lib/status.ts wuerde diese Klausel umgehen. Drift
// wird ueber StatusActionBar-Tests in allen Features ausgeglichen.

import type { VersionStatus } from '@/api/types'

export const VERSION_STATUSES: readonly VersionStatus[] = [
  'draft',
  'review',
  'active',
  'inactive',
] as const

export const ALLOWED_TRANSITIONS: Record<VersionStatus, readonly VersionStatus[]> = {
  draft: ['review'],
  review: ['active', 'draft'],
  active: [],
  inactive: [],
}

export type StatusBadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline'

export function statusLabel(status: VersionStatus): string {
  switch (status) {
    case 'draft':
      return 'Entwurf'
    case 'review':
      return 'In Review'
    case 'active':
      return 'Aktiv'
    case 'inactive':
      return 'Inaktiv'
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
