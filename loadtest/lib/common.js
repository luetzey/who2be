// Gemeinsame Bausteine der Belastungstest-Suite (Paket A4, ADR-0062 §8):
// Prod-Schutz, Ziel-Konfiguration, Seed-Daten, API-Aufrufe mit Tags,
// SLO-Schwellen (ADR-0062 §7, vorlaeufig nach Weiche W8) und die API-Strecken.
//
// Jede Szenario-Datei importiert dieses Modul. Der Prod-Schutz laeuft deshalb
// beim Laden im Init-Kontext von k6, bevor ein einziger Request gesendet wird.

import http from 'k6/http'
import encoding from 'k6/encoding'
import { check, sleep } from 'k6'
import { SharedArray } from 'k6/data'
import exec from 'k6/execution'
import { Counter, Rate } from 'k6/metrics'

// ---------------------------------------------------------------------------
// Prod-Schutz
// ---------------------------------------------------------------------------

/** Die Produktiv-Instanz. Sie und jede Subdomain sind als Ziel gesperrt. */
export const PRODUCTION_DOMAIN = 'who2be.de'

/** Wert, den W2B_LOADTEST_CONFIRM tragen muss. Ohne ihn startet nichts. */
export const CONFIRM_VALUE = 'synthetic-non-production'

/**
 * Hostname einer URL, klein geschrieben, ohne Port, Userinfo und Schluss-Punkt.
 * k6 bringt keine WHATWG-URL mit, daher ein bewusst enger Parser: nur
 * http/https, alles andere liefert `null` und gilt als unzulaessig.
 */
export function hostOf(url) {
  const match = /^(https?):\/\/([^/?#]*)/i.exec(String(url ?? '').trim())
  if (match === null) return null
  let authority = match[2]
  const at = authority.lastIndexOf('@')
  if (at >= 0) authority = authority.slice(at + 1)
  let host
  if (authority.startsWith('[')) {
    const end = authority.indexOf(']')
    host = end < 0 ? authority : authority.slice(0, end + 1)
  } else {
    host = authority.split(':')[0]
  }
  host = host.toLowerCase().replace(/\.+$/, '')
  return host === '' ? null : host
}

/** true fuer who2be.de und jede Subdomain davon. */
export function isProductionHost(host) {
  return host === PRODUCTION_DOMAIN || host.endsWith(`.${PRODUCTION_DOMAIN}`)
}

/** Gruende, aus denen der Lauf nicht starten darf (leer = zulaessig). */
export function unsafeTargetReasons(targets, confirm) {
  const reasons = []
  if (confirm !== CONFIRM_VALUE) {
    reasons.push(
      `W2B_LOADTEST_CONFIRM ist nicht gesetzt (erwartet: ${CONFIRM_VALUE}). ` +
        'Der Schalter bestaetigt: Ziel ist eine Testumgebung mit synthetischen Daten.',
    )
  }
  for (const [name, url] of Object.entries(targets)) {
    const host = hostOf(url)
    if (host === null) {
      reasons.push(`${name} ist keine http(s)-URL: ${String(url)}`)
    } else if (isProductionHost(host)) {
      reasons.push(`${name} zeigt auf die Produktion (${host}). Lasttests nie gegen Prod.`)
    }
  }
  return reasons
}

/** Bricht den Lauf im Init-Kontext ab, wenn ein Ziel unzulaessig ist. */
export function assertSafeTarget(targets, confirm) {
  const reasons = unsafeTargetReasons(targets, confirm)
  if (reasons.length > 0) {
    throw new Error(`Lasttest abgebrochen:\n- ${reasons.join('\n- ')}`)
  }
}

// ---------------------------------------------------------------------------
// Konfiguration (nur Env, keine Hosts im Repo)
// ---------------------------------------------------------------------------

function requiredEnv(name) {
  const value = __ENV[name]
  if (value === undefined || value === '') {
    throw new Error(`Env ${name} fehlt (siehe loadtest/README.md).`)
  }
  return value
}

function trimSlash(url) {
  return String(url).replace(/\/+$/, '')
}

/** API-Basis, z. B. http://localhost:8000 oder https://api.<DOMAIN>. */
export const BASE_URL = trimSlash(requiredEnv('BASE_URL'))
/** Streamable-HTTP-Endpunkt des MCP-Servers, z. B. https://mcp.<DOMAIN>/mcp. */
export const MCP_URL = trimSlash(requiredEnv('MCP_URL'))
export const PROFILE = __ENV.PROFILE || 'smoke'

assertSafeTarget({ BASE_URL, MCP_URL }, __ENV.W2B_LOADTEST_CONFIRM)

const SMOKE = PROFILE === 'smoke'
const THINK_MIN = Number(__ENV.THINK_MIN ?? (SMOKE ? 0.5 : 2))
const THINK_MAX = Number(__ENV.THINK_MAX ?? (SMOKE ? 1 : 5))
export const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '30s'

/** Denkzeit zwischen zwei Schritten eines Nutzers (Bericht §4.3: 2–5 s). */
export function think() {
  if (THINK_MAX <= 0) return
  sleep(THINK_MIN + Math.random() * Math.max(0, THINK_MAX - THINK_MIN))
}

/** Zahl aus Env mit Default. */
export function envNumber(name, fallback) {
  const raw = __ENV[name]
  if (raw === undefined || raw === '') return fallback
  const value = Number(raw)
  if (!Number.isFinite(value)) throw new Error(`Env ${name} ist keine Zahl: ${raw}`)
  return value
}

// ---------------------------------------------------------------------------
// Seed-Daten (nur synthetisch, Owner-Weiche W6)
// ---------------------------------------------------------------------------

export const SEED_MARKER = 'who2be-loadtest-seed'

/**
 * Workspaces aus der Seed-Datei (`seed/seed.py`). Die Datei muss das
 * Synthetik-Kennzeichen tragen und fuer dieselbe BASE_URL erzeugt sein.
 * SEED_FILE absolut angeben: k6 loest relative Pfade in `open()` relativ zu
 * DIESER Datei (lib/) auf, nicht zum Arbeitsverzeichnis.
 */
export const workspaces = new SharedArray('workspaces', () => {
  const data = JSON.parse(open(requiredEnv('SEED_FILE')))
  if (data.generator !== SEED_MARKER || data.synthetic !== true) {
    throw new Error('SEED_FILE stammt nicht aus loadtest/seed/seed.py (synthetic=true fehlt).')
  }
  if (trimSlash(data.api_url) !== BASE_URL) {
    throw new Error(`SEED_FILE wurde fuer ${data.api_url} erzeugt, BASE_URL ist ${BASE_URL}.`)
  }
  if (!Array.isArray(data.workspaces) || data.workspaces.length === 0) {
    throw new Error('SEED_FILE enthaelt keine Workspaces.')
  }
  return data.workspaces
})

/** Workspace dieses virtuellen Nutzers (stabil je VU, reihum verteilt). */
export function myWorkspace() {
  return workspaces[(exec.vu.idInTest - 1) % workspaces.length]
}

/** Laufende Nummer dieses VU innerhalb seines Workspaces (0-basiert). */
export function mySlot() {
  return Math.floor((exec.vu.idInTest - 1) / workspaces.length)
}

export function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

// ---------------------------------------------------------------------------
// Metriken und API-Aufrufe
// ---------------------------------------------------------------------------

/** Anteil fehlgeschlagener Requests: Status 0 (Timeout, Verbindung) oder 5xx. */
export const errors = new Rate('errors')
/** 429-Antworten. Sie sind kein Fehler, sondern das gewollte Ueberlast-Verhalten. */
export const rateLimited = new Counter('rate_limited')
/** 409-Antworten bei konkurrierenden Schreibzugriffen auf dasselbe Element. */
export const conflicts = new Counter('conflicts')
/** Strecken, die die Testumgebung nicht anbietet (z. B. Ingest ohne Blob-Store). */
export const skipped = new Counter('skipped')

export function isServerError(status) {
  return status === 0 || status >= 500
}

/**
 * Ein API-Aufruf mit Tags. `name` ist die Routen-Vorlage (keine IDs), damit
 * die Auswertung je Strecke gruppiert und keine IDs in Metrik-Labels landen.
 * `tolerate(res)` erlaubt einer Strecke, eine bekannte Nicht-Faehigkeit der
 * Umgebung (nicht: Ueberlast) aus der Fehlerquote zu nehmen.
 */
export function api(method, path, { token, body, kind, name, tolerate } = {}) {
  const headers = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  let payload = null
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const tags = { kind, name }
  const res = http.request(method, `${BASE_URL}${path}`, payload, {
    headers,
    tags,
    timeout: REQUEST_TIMEOUT,
    responseCallback: http.expectedStatuses({ min: 200, max: 299 }, 409, 429),
  })
  const tolerated = tolerate !== undefined && tolerate(res)
  const failed = !tolerated && isServerError(res.status)
  errors.add(failed, tags)
  if (res.status === 429) rateLimited.add(1, tags)
  if (res.status === 409) conflicts.add(1, tags)
  if (tolerated) skipped.add(1, tags)
  // Zwei Pruefungen: 5xx ist ein Kapazitaetsfehler (Fehlerbudget), jede andere
  // unerwartete Antwort (4xx ausser 409/429) ein Fehler der Suite selbst
  // (falsche Payload, fehlende Rechte) und laesst `checks` reissen.
  const expected =
    tolerated || (res.status >= 200 && res.status < 300) || res.status === 409 || res.status === 429
  check(
    res,
    {
      [`${name}: kein 5xx`]: () => !failed,
      [`${name}: Status erwartet`]: () => expected,
    },
    tags,
  )
  if (!expected && !failed) {
    console.warn(`${method} ${name}: unerwarteter Status ${res.status} ${String(res.body).slice(0, 200)}`)
  }
  return res
}

export function json(res) {
  try {
    return res.json()
  } catch (_err) {
    return null
  }
}

function reasonOf(res) {
  const body = json(res)
  return body !== null && typeof body === 'object' ? body.reason : undefined
}

// ---------------------------------------------------------------------------
// SLO-Schwellen (ADR-0062 §7, Bericht §4.5, Owner-Weiche W8: vorlaeufig)
// ---------------------------------------------------------------------------

/** Je Strecke (Tag `kind`) die vorlaeufigen Ziele. */
export const SLO = {
  read: ['p(95)<300', 'p(99)<1000'],
  write: ['p(95)<800'],
  activate: ['p(95)<1000'],
  search: ['p(95)<800'],
  mcp_call: ['p(95)<500', 'p(99)<1500'],
  mcp_session: ['p(95)<500'],
}

/** Fehlerquote 5xx (ohne 429) unter 0,5 %. */
export const ERROR_BUDGET = 'rate<0.005'

/**
 * Schwellen fuer die Strecken eines Profils. Im Kurzmodus (smoke) gilt nur
 * die Funktionspruefung (keine 5xx, Checks gruen): ein Laptop-Stack ist keine
 * Messumgebung. `THRESHOLDS=off` schaltet alle Schwellen ab, `THRESHOLDS=slo`
 * erzwingt die SLOs auch im Kurzmodus.
 */
export function sloThresholds(kinds, extra = {}) {
  const mode = __ENV.THRESHOLDS || (SMOKE ? 'functional' : 'slo')
  if (mode === 'off') return {}
  const thresholds = { errors: [ERROR_BUDGET], checks: ['rate>0.99'] }
  if (mode === 'slo') {
    for (const kind of kinds) {
      if (SLO[kind] !== undefined) thresholds[`http_req_duration{kind:${kind}}`] = SLO[kind]
    }
  }
  return { ...thresholds, ...extra }
}

/** Waehlt das Profil oder bricht mit der Liste der bekannten Profile ab. */
export function selectProfile(profiles) {
  const profile = profiles[PROFILE]
  if (profile === undefined) {
    throw new Error(`Unbekanntes PROFILE=${PROFILE}. Bekannt: ${Object.keys(profiles).join(', ')}`)
  }
  return profile
}

/** Trend-Statistiken fuer die Zusammenfassung und den Bericht. */
export const SUMMARY_TREND_STATS = ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max']

// ---------------------------------------------------------------------------
// API-Strecken
// ---------------------------------------------------------------------------

/** Gleiches Vokabular wie seed.py: Suchbegriffe treffen synthetische Inhalte. */
export const VOCABULARY = [
  'ablauf', 'agent', 'analyse', 'angebot', 'antwort', 'archiv', 'aufgabe', 'bericht',
  'checkliste', 'daten', 'dokument', 'entwurf', 'freigabe', 'gespraech', 'hinweis', 'kunde',
  'leitfaden', 'meldung', 'notiz', 'pruefung', 'qualitaet', 'regel', 'schritt', 'termin',
  'uebergabe', 'version', 'vorlage', 'werkzeug', 'zusammenfassung', 'ziel',
]

function wsPath(ws, suffix) {
  return `/v1/workspaces/${ws.id}${suffix}`
}

/** Lese-JWT dieses VU (je VU ein eigenes Token, wie ein eigener Browser). */
function readerToken(ws) {
  return ws.editors[mySlot() % ws.editors.length].jwt
}

/**
 * T3: Lesemix der Web-Oberflaeche (Listen, Detail, Verlauf) mit JWT.
 * Entspricht dem Seitenwechsel eines Redakteurs.
 */
export function readMix() {
  const ws = myWorkspace()
  const token = readerToken(ws)
  api('GET', '/v1/me', { token, kind: 'read', name: 'GET /v1/me' })
  api('GET', wsPath(ws, '/dashboard'), { token, kind: 'read', name: 'GET dashboard' })
  think()
  api('GET', wsPath(ws, '/playbooks?limit=50'), { token, kind: 'read', name: 'GET playbooks' })
  const playbookId = pick(ws.playbook_ids)
  api('GET', wsPath(ws, `/playbooks/${playbookId}`), {
    token,
    kind: 'read',
    name: 'GET playbooks/{id}',
  })
  api('GET', wsPath(ws, `/playbooks/${playbookId}/versions`), {
    token,
    kind: 'read',
    name: 'GET playbooks/{id}/versions',
  })
  think()
  api('GET', wsPath(ws, '/resources?limit=50'), { token, kind: 'read', name: 'GET resources' })
  api('GET', wsPath(ws, `/resources/${pick(ws.resource_ids)}`), {
    token,
    kind: 'read',
    name: 'GET resources/{id}',
  })
  api('GET', wsPath(ws, '/personas'), { token, kind: 'read', name: 'GET personas' })
  api('GET', wsPath(ws, `/personas/${ws.persona_id}`), {
    token,
    kind: 'read',
    name: 'GET personas/{id}',
  })
  api('GET', wsPath(ws, '/agents'), { token, kind: 'read', name: 'GET agents' })
  think()
}

function paragraph(id, text) {
  return { id, type: 'paragraph', props: {}, content: [{ type: 'text', text, styles: {} }], children: [] }
}

/**
 * T4: Schreibstrecke eines Redakteurs: Element oeffnen → Entwurf speichern →
 * einreichen → aktivieren. Jeder VU hat ein eigenes JWT und ein eigenes
 * Playbook (seed.py), damit sich Redakteure nicht gegenseitig blockieren und
 * das Schreiblimit (30/min je Token) je Redakteur gilt.
 */
export function writeFlow() {
  const ws = myWorkspace()
  const editor = ws.editors[mySlot() % ws.editors.length]
  const token = editor.jwt
  const base = wsPath(ws, `/playbooks/${editor.playbook_id}`)
  const opened = api('GET', base, { token, kind: 'read', name: 'GET playbooks/{id}' })
  const current = json(opened)
  if (current === null || opened.status !== 200) return
  think()
  const stamp = `${exec.vu.idInTest}-${exec.scenario.iterationInTest}`
  const blocks = [
    paragraph(`lt-${stamp}-1`, `Schritt ${stamp}: ${pick(VOCABULARY)} ${pick(VOCABULARY)} pruefen.`),
    paragraph(`lt-${stamp}-2`, `Uebergabe an ${pick(VOCABULARY)} mit ${pick(VOCABULARY)}.`),
  ]
  const saved = api('PATCH', `${base}/draft`, {
    token,
    kind: 'write',
    name: 'PATCH playbooks/{id}/draft',
    body: {
      name: current.name,
      content: { ...current.content, body: JSON.stringify(blocks) },
    },
  })
  const draft = json(saved)
  if (saved.status !== 200 || draft === null) return
  think()
  const version = draft.current_version
  const review = api('POST', `${base}/versions/${version}/transition`, {
    token,
    kind: 'write',
    name: 'POST transition review',
    body: { to: 'review' },
  })
  if (review.status !== 200) return
  api('POST', `${base}/versions/${version}/transition`, {
    token,
    kind: 'activate',
    name: 'POST transition active',
    body: { to: 'active' },
  })
  think()
}

/** T5: Volltextsuche und Passagensuche, wie Web-Suche bzw. `search_content`. */
export function searchFlow() {
  const ws = myWorkspace()
  const token = readerToken(ws)
  const q = `${pick(VOCABULARY)} ${pick(VOCABULARY)}`
  api('GET', wsPath(ws, `/search?q=${encodeURIComponent(q)}&limit=20`), {
    token,
    kind: 'search',
    name: 'GET search',
  })
  api('GET', wsPath(ws, `/search/content?q=${encodeURIComponent(pick(VOCABULARY))}&limit=5`), {
    token,
    kind: 'search',
    name: 'GET search/content',
  })
}

let ingestPayload = null
let ingestUnavailable = false

/**
 * T6: grosse Datei in die private Area des Agenten ingestieren (ADR-0048).
 * Der Inhalt ist synthetischer Text; ein eindeutiger Kopf je Aufruf verhindert
 * die Deduplizierung. Ohne konfigurierten Blob-Store (lokaler Stack ohne
 * WHO2BE_BLOBSTORE_*) antwortet die API 503 `blobstore_unconfigured`: das
 * zaehlt als `skipped`, nicht als Fehler, und die Strecke ruht danach.
 */
export function ingestFlow() {
  if (ingestUnavailable) {
    skipped.add(1, { kind: 'ingest', name: 'POST ingest' })
    sleep(1)
    return
  }
  const sizeMiB = envNumber('INGEST_MB', SMOKE ? 1 : 20)
  if (ingestPayload === null) {
    const line = `${VOCABULARY.join(' ')}\n`
    ingestPayload = line.repeat(Math.ceil((sizeMiB * 1024 * 1024) / line.length))
  }
  const ws = myWorkspace()
  const stamp = `loadtest ${exec.vu.idInTest}-${exec.scenario.iterationInTest}-${Date.now()}\n`
  const res = api('POST', wsPath(ws, '/ingest'), {
    token: ws.agent_tokens[mySlot() % ws.agent_tokens.length],
    kind: 'ingest',
    name: 'POST ingest',
    body: { file_b64: encoding.b64encode(stamp + ingestPayload), filename: 'loadtest.txt' },
    tolerate: (r) => r.status === 503 && reasonOf(r) === 'blobstore_unconfigured',
  })
  if (res.status === 503 && reasonOf(res) === 'blobstore_unconfigured') {
    ingestUnavailable = true
    console.warn('Ingest uebersprungen: Blob-Store der Testumgebung nicht konfiguriert.')
  }
  check(res, { 'ingest: kein OOM-Abbruch (Status != 0)': (r) => r.status !== 0 })
  think()
}

/** T10/T11: API-Gesundheit, je Aufruf ein Datenpunkt fuer die Verfuegbarkeit. */
export const healthOk = new Rate('health_ok')

export function healthProbe() {
  const res = http.get(`${BASE_URL}/v1/health`, {
    tags: { kind: 'health', name: 'GET /v1/health' },
    timeout: '5s',
    responseCallback: http.expectedStatuses(200),
  })
  healthOk.add(res.status === 200)
  return res.status === 200
}

/**
 * T11: Schreib-Burst mit EINEM Token ueber das Limit (30/min) hinaus. Erwartet
 * werden 429 statt 5xx. Ziel ist ein Entwurf des eigenen Redakteur-Playbooks;
 * die aktive Version bleibt unberuehrt.
 */
export function writeBurst(count) {
  const ws = myWorkspace()
  const editor = ws.editors[mySlot() % ws.editors.length]
  const base = wsPath(ws, `/playbooks/${editor.playbook_id}`)
  const current = json(api('GET', base, { token: editor.jwt, kind: 'read', name: 'GET playbooks/{id}' }))
  if (current === null) return 0
  let limited = 0
  for (let i = 0; i < count; i += 1) {
    const res = api('PATCH', `${base}/draft`, {
      token: editor.jwt,
      kind: 'limit',
      name: 'PATCH playbooks/{id}/draft (burst)',
      body: { name: current.name, content: current.content },
    })
    if (res.status === 429) limited += 1
  }
  check(limited, { 'Schreib-Burst: Limit greift mit 429': (n) => count <= 30 || n > 0 })
  return limited
}
