/**
 * Pfadbau fuer die Who2Be-API — Schutz gegen Client-Side Path Traversal (CSPT).
 *
 * IDs und Slugs kommen im Web-Client auch aus der URL (`useParams` dekodiert
 * `%2F` in Segmenten, `?entry=` ist Freitext). Roh in einen Pfad gesetzt,
 * macht `../../x` aus `GET /workspaces/{ws}/memories/{id}` einen
 * authentifizierten Abruf auf einen beliebigen API-Pfad. Deshalb entsteht
 * jeder Pfad an genau einer Stelle:
 *
 * - `apiPath` (Tagged Template) setzt jeden interpolierten Wert als GENAU EIN
 *   Segment ein (`encodeURIComponent`). Werte, die kein Segment sein koennen
 *   (leer, `.`, enthaelt `..`, `/`, `\`, `?`, `#`), machen den Pfad ungueltig.
 * - `withQuery` haengt Query-Parameter ausschliesslich ueber `URLSearchParams` an.
 * - `resolveApiPath` prueft zentral in den request-Helfern: ungueltiger Pfad →
 *   Ablehnung ohne Netzabruf.
 *
 * Ein ungueltiger Wert wirft beim BAUEN nicht, sondern erst in `resolveApiPath`
 * (also im async request-Helfer): die Api-Methoden sind synchrone Arrows, ein
 * synchroner Wurf waere fuer `.then/.catch`-Aufrufer ein unbehandelter Fehler.
 * Die request-Helfer nehmen nur `ApiPath`, nie `string` — ein roher
 * Template-String kompiliert dort nicht.
 */

export class ApiPath {
  /** @internal — nur ueber `apiPath`/`withQuery` erzeugen. */
  constructor(
    readonly value: string,
    readonly invalid: string | null,
  ) {}

  toString(): string {
    return this.value
  }
}

const FORBIDDEN = /[/\\?#]/

/** Grund, warum `value` kein einzelnes Pfadsegment sein kann, sonst `null`. */
export function segmentProblem(value: string): string | null {
  if (value === '') return 'leer'
  if (value === '.' || value.includes('..')) return 'Punkt-Segment'
  if (FORBIDDEN.test(value)) return 'Trenner'
  return null
}

export function apiPath(
  strings: TemplateStringsArray,
  ...values: Array<string | number | ApiPath>
): ApiPath {
  let out = strings[0]
  // Query/Fragment nur ueber `withQuery` — sonst wuerde ein Wert hinter `?`
  // als Pfadsegment kodiert (`tag%3Dx`) und die Grenze Pfad/Query verwischt.
  let invalid: string | null = strings.some((s) => /[?#]/.test(s)) ? 'Query im Pfad' : null
  values.forEach((value, i) => {
    if (value instanceof ApiPath) {
      out += value.value
      invalid ??= value.invalid
      if (value.value.includes('?')) invalid ??= 'Query im Pfad'
    } else {
      const raw = String(value)
      const problem = segmentProblem(raw)
      if (problem !== null) invalid ??= problem
      out += encodeURIComponent(raw)
    }
    out += strings[i + 1]
  })
  return new ApiPath(out, invalid)
}

/** Haengt `params` als Query an; leere Parameter → Pfad unveraendert. */
export function withQuery(
  path: ApiPath,
  params: URLSearchParams | Record<string, string>,
): ApiPath {
  const query = new URLSearchParams(params).toString()
  if (path.value.includes('?')) return new ApiPath(path.value, path.invalid ?? 'Query doppelt')
  return query === '' ? path : new ApiPath(`${path.value}?${query}`, path.invalid)
}

/**
 * Liefert den Pfad-String fuer `fetch` oder `null`, wenn er abgelehnt wird:
 * ein Segment war ungueltig, oder die URL-Normalisierung (Punkt-Segmente,
 * auch `%2e%2e`) wuerde den Pfad veraendern — Abwehr in der Tiefe fuer den
 * Fall, dass ein statischer Pfadteil selbst so etwas enthaelt.
 */
export function resolveApiPath(path: ApiPath): string | null {
  if (path.invalid !== null) return null
  const raw = path.value.split('?')[0]
  const normalized = new URL(raw, 'http://who2be.invalid').pathname
  return normalized === raw ? path.value : null
}
