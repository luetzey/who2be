import { safeInternalPath } from '@/lib/safePath'

// Open-Redirect-Schutz fuer `next` nach dem Login. Die Regel selbst lebt in
// `@/lib/safePath` (einzige Quelle, auch fuer `returnTo` nach der 2FA-
// Einrichtung); ungueltige Ziele fallen hier auf `/` zurueck.
export function sanitizeNext(raw: string | null): string {
  return safeInternalPath(raw) ?? '/'
}
