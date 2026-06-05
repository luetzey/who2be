// Shared Status-Label/Badge-Helfer fuer die generischen Versions-Komponenten.
// Liegt bewusst unter components/ (nicht in einem Feature) — die per-Feature
// `lib/status.ts` duerfen wegen der Cross-Feature-Lint-Regel nicht von hier
// importiert werden; diese Datei ist die geteilte Quelle fuer die
// Versions-UI-Insel.

import type { VersionStatus } from '@/api/types'
import i18n from '@/i18n'

export type StatusBadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline'

export function statusLabel(status: VersionStatus): string {
  return i18n.t(`common:status.${status}`)
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
