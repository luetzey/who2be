import type { VersionStatus } from '@/api/types'

// Lokales Label-Mapping fuer das Dashboard. Kein Cross-Feature-Import auf
// `features/personas/lib/status.ts` (ESLint-Verbot) — die Funktion ist
// trivial und liegt darum als lokales Modul vor.
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
