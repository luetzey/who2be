// "Angemeldet bleiben" — der gesamte Zustand dazu, an EINER Stelle (Issue
// #430, ADR-0052). Vorher lagen dieselben Key-Literale doppelt in
// `lib/supabase.ts` und `auth/SessionProvider.tsx`; der Security-Review hat
// gezeigt, dass genau diese Verdopplung die Loecher aufgemacht hat (Flag und
// Session-Blob wurden an verschiedenen Stellen und in verschiedenen
// Reihenfolgen angefasst). Dieses Modul ist bewusst frei von
// Supabase-Imports: `lib/supabase.ts`, `auth/SessionProvider.tsx` und
// `features/settings/.../AccountPage.tsx` importieren es alle, ohne dass die
// vielen `vi.mock('@/lib/supabase', …)`-Stubs der Bestandstests etwas davon
// mitbekommen.

/** GoTrue-`storageKey`. Einzige Quelle — `lib/supabase.ts` importiert ihn. */
export const SESSION_STORAGE_KEY = 'who2be.auth.session'

// EIN Key statt zwei. Vorher standen Flag (`…remember`) und Zeitstempel
// (`…signed_in_at`) getrennt, geschrieben mit zwei `setItem`-Aufrufen: schlug
// der zweite fehl (Quota) oder wurde der Zeitstempel manipuliert, blieb ein
// "angemeldet bleiben" OHNE Obergrenze stehen — die Kappung war damit
// abschaltbar. Ein Wert, ein Schreibvorgang, und ein Marker ohne gueltigen
// Zeitstempel gilt als abgelaufen (siehe `rememberedSessionExpired`).
const REMEMBER_KEY = 'who2be.auth.remember'

interface RememberMarker {
  signedInAt: number
}

function localStore(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch {
    // Privacy-Mode/deaktiviertes Storage.
    return null
  }
}

/** Roher Marker-Wert — nur fuer `restoreRememberMarker` (Login-Fehlerpfad). */
export function readRememberMarker(): string | null {
  try {
    return localStore()?.getItem(REMEMBER_KEY) ?? null
  } catch {
    return null
  }
}

/**
 * Liegt die Session im `localStorage`? Bewusst nur "Marker vorhanden", nicht
 * "Marker gueltig": ein kaputter Marker bedeutet, dass die Session trotzdem
 * dort liegt — der Adapter muss sie finden, damit `signOut()` sie auch
 * loeschen kann. Die Gueltigkeit entscheidet allein
 * `rememberedSessionExpired`, und die faellt bei kaputtem Marker fail-closed.
 */
export function hasRememberMarker(): boolean {
  return readRememberMarker() !== null
}

/** Setzt Marker + Login-Zeitstempel in EINEM Schreibvorgang. */
export function markRememberedLogin(now: number = Date.now()): void {
  try {
    const marker: RememberMarker = { signedInAt: now }
    localStore()?.setItem(REMEMBER_KEY, JSON.stringify(marker))
  } catch {
    // Quota/Privacy-Mode: der Login laeuft weiter, faellt aber effektiv auf
    // Tab-Lifetime zurueck (der Adapter findet keinen Marker).
  }
}

export function clearRememberMarker(): void {
  try {
    localStore()?.removeItem(REMEMBER_KEY)
  } catch {
    // s. o. — es war ohnehin nichts persistiert.
  }
}

/** Stellt den Marker-Stand von vor einem fehlgeschlagenen Login wieder her. */
export function restoreRememberMarker(raw: string | null): void {
  if (raw === null) {
    clearRememberMarker()
    return
  }
  try {
    localStore()?.setItem(REMEMBER_KEY, raw)
  } catch {
    // s. o.
  }
}

/**
 * Entfernt den Session-Blob aus dem Backend, das nach einem Wechsel NICHT
 * mehr zustaendig ist. Ohne diesen Schritt blieb der Refresh-Token des
 * vorherigen Modus liegen — und weil der Marker mitgeloescht wurde, fiel er
 * zugleich aus der Ablaufpruefung heraus: eine Datenleiche ohne Obergrenze.
 */
export function purgeStoredSessionFrom(kind: 'local' | 'session'): void {
  if (typeof window === 'undefined') return
  try {
    const store = kind === 'local' ? window.localStorage : window.sessionStorage
    store.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // s. o.
  }
}

/**
 * Ist eine "angemeldet bleiben"-Session ueber ihrer absoluten Obergrenze?
 *
 * Fail-closed in beide Richtungen, die etwas anderes als einen intakten
 * Marker vorfinden:
 *   - kein Marker            → `false` (normale Tab-Lifetime-Session, sie hat
 *                              gar keine Obergrenze und endet mit dem Tab)
 *   - Marker, aber kaputt    → `true`  (kein Zeitstempel = keine Kappung
 *                              waere die Umgehung, die der Security-Review
 *                              gefunden hat)
 *   - Marker mit Zeitstempel → Altersvergleich
 */
export function rememberedSessionExpired(maxAgeMs: number, now: number = Date.now()): boolean {
  const raw = readRememberMarker()
  if (raw === null) return false
  let signedInAt: unknown
  try {
    signedInAt = (JSON.parse(raw) as Partial<RememberMarker>).signedInAt
  } catch {
    return true
  }
  if (typeof signedInAt !== 'number' || !Number.isFinite(signedInAt)) return true
  return now - signedInAt > maxAgeMs
}
