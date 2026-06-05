import type { VersionStatus } from '@/api/types'
import i18n from '@/i18n'

// Lokales Label-Mapping fuer das Dashboard. Kein Cross-Feature-Import auf
// `features/personas/lib/status.ts` (ESLint-Verbot) — die Funktion ist
// trivial und liegt darum als lokales Modul vor.
export function statusLabel(status: VersionStatus): string {
  return i18n.t(`common:status.${status}`)
}
