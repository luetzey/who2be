// Shared Status-Label/Badge-Helfer fuer die generischen Versions-Komponenten.
// Liegt bewusst unter components/ (nicht in einem Feature) — die per-Feature
// `lib/status.ts` duerfen wegen der Cross-Feature-Lint-Regel nicht von hier
// importiert werden; diese Datei ist die geteilte Quelle fuer die
// Versions-UI-Insel.

import type { VersionStatus } from '@/api/types'

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
