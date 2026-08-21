// Erkennung + Auto-Reload fuer "stale chunk"-Fehler nach einem Deploy.
//
// Ursache (siehe .claude/plan/2026-08-21-1216_stale-chunk-auto-reload.md):
// Ein Browser-Tab mit altem index.html/Entry-Chunk fordert beim Navigieren
// einen React.lazy-Chunk mit veraltetem Content-Hash an. Der alte Chunk
// existiert nach einem Deploy nicht mehr (404) -> der dynamische `import()`
// wird rejected. Statt der Fehlerseite soll GENAU EIN automatischer Reload
// passieren (danach laedt der Browser das neue index.html + neue Chunks).

/** Bekannte Browser-Fehlermeldungen fuer fehlgeschlagene dynamische Imports. */
const STALE_CHUNK_PATTERNS: readonly RegExp[] = [
  /importing a module script failed/i, // Safari
  /failed to fetch dynamically imported module/i, // Chrome
  /error loading dynamically imported module/i, // Firefox
]

/**
 * Extrahiert eine Fehlermeldung aus Error-Instanzen und Event-aehnlichen
 * Objekten (z. B. `PromiseRejectionEvent.reason`, `ErrorEvent.message`).
 * Alles andere liefert `null`.
 */
function extractMessage(error: unknown): string | null {
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'object' && error !== null) {
    const candidate = error as { message?: unknown; reason?: unknown }
    if (typeof candidate.message === 'string') {
      return candidate.message
    }
    if (candidate.reason instanceof Error) {
      return candidate.reason.message
    }
    if (typeof candidate.reason === 'string') {
      return candidate.reason
    }
  }
  return null
}

/**
 * Prueft, ob `error` einem bekannten "stale chunk"-Fehler eines
 * fehlgeschlagenen dynamischen Imports entspricht (case-insensitiv).
 */
export function isStaleChunkError(error: unknown): boolean {
  const message = extractMessage(error)
  if (message === null) {
    return false
  }
  return STALE_CHUNK_PATTERNS.some((pattern) => pattern.test(message))
}

const GUARD_STORAGE_KEY = 'who2be:stale-chunk-reload'
const GUARD_WINDOW_MS = 60_000

/**
 * Loest genau EINEN Seiten-Reload pro Zeitfenster aus (sessionStorage-Guard).
 * Verhindert einen Reload-Loop, falls der Fehler in Wahrheit eine andere
 * Ursache hat (der neu geladene Chunk waere sonst wieder kaputt und wuerde
 * erneut denselben Fehler werfen).
 *
 * Rueckgabe `true`, wenn ein Reload ausgeloest wurde, sonst `false`
 * (Guard noch aktiv ODER sessionStorage nicht verfuegbar — z. B.
 * Private-Mode-Safari wirft dort synchron; in dem Fall bewusst KEIN
 * Reload, damit kein unkontrollierbarer Loop entstehen kann, und der
 * Aufrufer faellt auf die normale Fehleranzeige zurueck).
 */
export function reloadOnStaleChunk(): boolean {
  try {
    const stored = window.sessionStorage.getItem(GUARD_STORAGE_KEY)
    if (stored !== null) {
      const lastReloadAt = Number(stored)
      if (Number.isFinite(lastReloadAt) && Date.now() - lastReloadAt < GUARD_WINDOW_MS) {
        return false
      }
    }
    window.sessionStorage.setItem(GUARD_STORAGE_KEY, String(Date.now()))
  } catch {
    return false
  }
  window.location.reload()
  return true
}
