// Open-Redirect-Schutz fuer alle In-App-Ruecksprungziele (`next` nach dem
// Login, `returnTo` nach der 2FA-Einrichtung). Einzige Quelle der Regel —
// `features/auth/lib/sanitize-next.ts` delegiert hierher.
//
// Ein gueltiges Ziel ist ein Pfad derselben App:
// - beginnt mit genau einem `/` (`//evil.example` ist protokoll-relativ),
// - enthaelt keinen Backslash (Browser normalisieren `/\evil.example` zu
//   `//evil.example`),
// - enthaelt kein `://` und kein Steuerzeichen (Browser entfernen Tab/CR/LF
//   aus URLs, `/\t/evil.example` wird so zu `//evil.example`),
// - bleibt beim Aufloesen gegen einen Platzhalter-Origin auf diesem Origin
//   (Gegenprobe gegen Parser-Eigenheiten, die die Einzelregeln verfehlen).
// `javascript:`, `https://…` und relative Pfade scheitern bereits an der
// ersten Regel.

const PROBE_ORIGIN = 'https://who2be.invalid'

// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u001F\u007F]/

/** Liefert `raw`, wenn es ein sicherer In-App-Pfad ist, sonst `null`. */
export function safeInternalPath(raw: string | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === '') return null
  if (!raw.startsWith('/') || raw.startsWith('//')) return null
  if (raw.includes('\\') || raw.includes('://') || CONTROL_CHARS.test(raw)) return null
  try {
    if (new URL(raw, PROBE_ORIGIN).origin !== PROBE_ORIGIN) return null
  } catch {
    return null
  }
  return raw
}
