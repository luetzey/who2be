import { sanitizeNext } from './sanitize-next'

// Baut eine absolute Redirect-URL fuer GoTrue-Flows (OAuth, Recovery, Signup-
// Confirm). GoTrue gleicht `redirect_to` gegen seine Allowlist ab und haengt
// danach die Session-Tokens an — das Ziel muss daher ein vollqualifizierter
// In-App-Pfad auf *unserem* Origin sein. `window.location.origin` ist der
// aktuell geladene (vertrauenswuerdige) Origin; den fragen wir nie aus
// User-Input ab. Ein optionaler `next` (In-App-Pfad, wohin es nach dem Flow
// weitergeht) wird ueber `sanitizeNext` gegen Open-Redirect gehaertet und nur
// dann angehaengt, wenn er vom Default `/` abweicht.
export function buildRedirectTo(path: string, next?: string | null): string {
  const origin = window.location.origin
  const safeNext = sanitizeNext(next ?? null)
  if (safeNext === '/') {
    return `${origin}${path}`
  }
  return `${origin}${path}?next=${encodeURIComponent(safeNext)}`
}
