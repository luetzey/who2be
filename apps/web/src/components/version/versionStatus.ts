// Einzige Quelle der Status-UI (State-Machine + Label/Badge-Helfer) fuer die
// generischen Versions-Komponenten. Liegt bewusst unter components/ (nicht in
// einem Feature) — die frueheren per-Feature `lib/status.ts`-Kopien in
// personas/playbooks/resources/tools sind entfallen; diese Datei ist jetzt
// die geteilte Quelle, von der aus die Versions-UI-Insel (inkl.
// StatusActionBar) importiert.

import type { VersionStatus } from '@/api/types'
import i18n from '@/i18n'

// Spiegel der Status-State-Machine aus packages/models (Phase 2.1b §2.1.G).
export const VERSION_STATUSES: readonly VersionStatus[] = [
  'draft',
  'review',
  'active',
  'inactive',
] as const

// Erlaubte Status-Uebergaenge laut §2.1.C. Reject = Review zurueck auf
// Draft. `inactive → draft` ist die Reaktivierung (Phase 3-C) — damit
// inaktive Bestaende wieder bearbeitbar werden, ohne eine neue Version
// anzulegen. Active → Inactive bleibt fuer kuenftige Iteration reserviert.
export const ALLOWED_TRANSITIONS: Record<VersionStatus, readonly VersionStatus[]> = {
  draft: ['review'],
  review: ['active', 'draft'],
  active: [],
  inactive: ['draft'],
}

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

export function canTransition(from: VersionStatus, to: VersionStatus): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to)
}
