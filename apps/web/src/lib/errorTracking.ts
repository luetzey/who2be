// Fehler-Tracking der Web-App (Stabilitaet A3, ADR-0062, Weiche W1: GlitchTip
// selbst gehostet, Sentry-kompatibel).
//
// Aus, solange kein DSN gesetzt ist: dann wird `@sentry/react` NICHT geladen
// (dynamischer Import, eigener Chunk) und es gibt keinen einzigen Netzaufruf.
// Der DSN kommt nur zur Laufzeit aus `/config.js` (`WHO2BE_SENTRY_DSN`).
//
// Mit DSN gilt dieselbe PII-Linie wie im Backend
// (`packages/models/src/who2be_models/error_tracking.py`): kein Nutzer, keine
// Cookies, Header, Bodies oder Query-Strings, kein Session-Replay, kein
// Tracing, keine Session-Pings. Tokens, JWTs, Bearer-Werte und E-Mail-Adressen
// werden in Meldungen und Breadcrumbs maskiert.
//
// Hinweis: Damit der Browser Events senden darf, muss die CSP `connect-src`
// die Tracker-Domain erlauben. Das regelt das Infra-Paket, nicht dieser Code.

import type { ErrorInfo } from 'react'

import { config } from '@/config'

type BrowserOptions = import('@sentry/react').BrowserOptions
type ErrorEvent = import('@sentry/react').ErrorEvent
type Breadcrumb = import('@sentry/react').Breadcrumb

// Nur die Funktion, die nach dem Start noch gebraucht wird.
interface LoadedTracker {
  captureReactException: (error: unknown, info: ErrorInfo) => void
}

export interface ErrorTrackingConfig {
  sentryDsn: string
  sentryEnvironment: string
  sentryRelease: string
}

const MASK = '[Filtered]'

// Textmuster wie im Backend (`_TEXT_PATTERNS`).
const TEXT_PATTERNS: readonly RegExp[] = [
  // Who2Be-API-Tokens.
  /w2b_[A-Za-z0-9_-]+/g,
  // JWTs (drei Base64url-Teile, Header beginnt mit eyJ).
  /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g,
  // Bearer-Werte.
  /bearer\s+[A-Za-z0-9._~+/-]+=*/gi,
  // E-Mail-Adressen.
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g,
  // Query-Strings in URLs (OAuth-`code`, `token`, Supabase-Hash u. a.).
  /\?[^\s"'#]*=[^\s"'#]*/g,
]

// Request-Felder, die nie mitgeschickt werden. Uebrig bleibt die URL ohne
// Query-String und Fragment.
const REQUEST_DROP = ['data', 'cookies', 'headers', 'query_string', 'env'] as const

// Integrationen, die zusaetzliche Daten oder Aufrufe erzeugen, die wir nicht
// wollen: Session-Pings (eigener Netzaufruf je Seitenaufruf).
const DROPPED_INTEGRATIONS = new Set(['BrowserSession'])

/** Maskiert Tokens, JWTs, Bearer-Werte, E-Mail-Adressen und Query-Strings. */
export function scrubText(value: string): string {
  let out = value
  for (const pattern of TEXT_PATTERNS) {
    out = out.replace(pattern, MASK)
  }
  return out
}

/** Entfernt Query-String und Fragment (Supabase legt Tokens in den Hash). */
export function stripUrl(url: string): string {
  return url.split('#', 1)[0].split('?', 1)[0]
}

function scrubDeep(node: unknown, seen: WeakSet<object> = new WeakSet()): unknown {
  if (typeof node === 'string') return scrubText(node)
  if (node === null || typeof node !== 'object') return node
  if (seen.has(node)) return node
  seen.add(node)
  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i++) node[i] = scrubDeep(node[i], seen)
    return node
  }
  const record = node as Record<string, unknown>
  for (const key of Object.keys(record)) {
    record[key] = scrubDeep(record[key], seen)
  }
  return record
}

/** Letzte Schranke vor dem Versand eines Fehler-Events. Exportiert fuer Tests. */
export function beforeSend(event: ErrorEvent): ErrorEvent {
  delete event.user
  const request = event.request
  if (request) {
    for (const key of REQUEST_DROP) delete request[key]
    if (typeof request.url === 'string') request.url = stripUrl(request.url)
  }
  scrubDeep(event)
  return event
}

/** Breadcrumbs tragen Konsolen-Zeilen und HTTP-Ziele: gleiche Maskierung. */
export function beforeBreadcrumb(crumb: Breadcrumb): Breadcrumb {
  const data = crumb.data
  if (data) {
    for (const key of ['url', 'from', 'to']) {
      const value = data[key]
      if (typeof value === 'string') data[key] = stripUrl(value)
    }
    delete data['http.query']
    delete data['http.fragment']
  }
  scrubDeep(crumb)
  return crumb
}

/** Baut die SDK-Optionen. Exportiert fuer Tests (PII-Linie belegbar). */
export function buildOptions(cfg: ErrorTrackingConfig): BrowserOptions {
  return {
    dsn: cfg.sentryDsn,
    environment: cfg.sentryEnvironment,
    ...(cfg.sentryRelease !== '' ? { release: cfg.sentryRelease } : {}),
    // Kein Tracing (Weiche B7 erst in Stufe B), kein Replay (nicht importiert).
    tracesSampleRate: 0,
    sendClientReports: false,
    maxBreadcrumbs: 30,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      stackFrameVariables: false,
      graphQL: { document: false, variables: false },
      genAI: { inputs: false, outputs: false },
      databaseQueryData: false,
      queues: false,
    },
    integrations: (defaults) =>
      defaults.filter((integration) => !DROPPED_INTEGRATIONS.has(integration.name)),
    beforeSend,
    beforeBreadcrumb,
  }
}

let loading: Promise<LoadedTracker | null> | null = null

/**
 * Startet das Fehler-Tracking, wenn ein DSN gesetzt ist. Ohne DSN passiert
 * nichts: kein Import, kein Netzaufruf, Rueckgabe `false`.
 */
export function initErrorTracking(cfg: ErrorTrackingConfig = config): Promise<boolean> {
  if (cfg.sentryDsn === '') return Promise.resolve(false)
  // Destrukturierter dynamischer Import: so kann der Bundler alles, was hier
  // nicht genannt ist (Replay, Feedback, Tracing, Router-Integrationen), aus
  // dem SDK-Chunk entfernen.
  loading ??= import('@sentry/react')
    .then(({ init, captureReactException }): LoadedTracker => {
      init(buildOptions(cfg))
      return { captureReactException }
    })
    .catch((error: unknown) => {
      // Ein fehlender Chunk darf die App nicht stoeren; Tracking bleibt aus.
      console.warn('[who2be] Fehler-Tracking konnte nicht starten:', error)
      return null
    })
  return loading.then((tracker) => tracker !== null)
}

/**
 * Meldet einen von einer React-Error-Boundary gefangenen Fehler. No-op, wenn
 * das Tracking nicht gestartet wurde (kein DSN).
 */
export function reportBoundaryError(error: unknown, info: ErrorInfo): void {
  if (loading === null) return
  void loading.then((tracker) => {
    tracker?.captureReactException(error, info)
  })
}

/** Nur fuer Tests: Modulzustand zuruecksetzen. */
export function resetErrorTrackingForTests(): void {
  loading = null
}
