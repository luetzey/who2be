// MCP-Client fuer k6: Streamable HTTP (ADR-0034) mit Token-Auth.
//
// Ablauf wie ein echter Agent: `initialize` → Session-Id aus dem Header
// `Mcp-Session-Id` → `notifications/initialized` → `tools/list` /
// `tools/call` → `DELETE` beendet die Session. Auth ist ein normaler
// agent-gebundener `w2b_`-Token als Bearer; der Server introspektiert ihn per
// `GET /v1/me` gegen die API (apps/mcp/src/who2be_mcp/auth.py). Die Antwort
// kommt als JSON oder als SSE-Stream; beides wird gelesen. Muster:
// apps/web/e2e/helpers/mcp.ts.
//
// Metrik-Tags: `kind=mcp_session` fuer initialize + tools/list (SLO p95 < 500 ms),
// `kind=mcp_call` fuer tools/call (SLO p95 < 500 ms, p99 < 1,5 s); `name` traegt
// die Methode bzw. den Werkzeugnamen, nie IDs.

import http from 'k6/http'
import { check } from 'k6'
import { Counter, Rate } from 'k6/metrics'

import {
  MCP_URL,
  VOCABULARY,
  errors,
  isServerError,
  mySlot,
  myWorkspace,
  pick,
  rateLimited,
  think,
} from './common.js'

export const PROTOCOL_VERSION = '2025-06-18'
const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '30s'

/** Werkzeug-Aufrufe, die mit `isError: true` zurueckkommen (fachlicher Fehler). */
export const toolErrors = new Rate('mcp_tool_errors')
/** Werkzeug-Fehler, deren Text auf ein Limit (429) hinweist. */
export const toolRateLimited = new Counter('mcp_tool_rate_limited')
/** Sessions, die nicht aufgebaut werden konnten (initialize ohne Session-Id). */
export const sessionFailures = new Rate('mcp_session_failures')

let rpcId = 0

function header(res, name) {
  const wanted = name.toLowerCase()
  for (const [key, value] of Object.entries(res.headers)) {
    if (key.toLowerCase() === wanted) return value
  }
  return undefined
}

/** Liest die JSON-RPC-Antwort aus einem JSON- oder SSE-Body. */
export function parseRpcBody(body, contentType) {
  if (body === null || body === undefined || String(body).trim() === '') return null
  const text = String(body)
  if (!String(contentType ?? '').includes('text/event-stream')) {
    try {
      return JSON.parse(text)
    } catch (_err) {
      return null
    }
  }
  // SSE: die Antwort steht in `data:`-Zeilen; die letzte mit gesetzter id gewinnt.
  let response = null
  for (const line of text.split('\n')) {
    if (!line.startsWith('data:')) continue
    try {
      const message = JSON.parse(line.slice('data:'.length).trim())
      if (message !== null && message.id !== undefined) response = message
    } catch (_err) {
      // Keep-Alive- oder Teilzeilen ignorieren.
    }
  }
  return response
}

/**
 * Eine MCP-Session. Je Iteration eine neue Session ist der realistische Fall
 * (ein Agent verbindet sich, arbeitet, trennt sich). `sessionLimitMs` und
 * Wiederverwendung ueber Iterationen sind bewusst nicht eingebaut: offene
 * Sessions im Prozess sind Gegenstand von T7 (Leaks) und sollen sichtbar sein.
 */
export class McpSession {
  constructor(token) {
    this.token = token
    this.sessionId = undefined
  }

  _post(payload, { kind, name }) {
    const headers = {
      Authorization: `Bearer ${this.token}`,
      Accept: 'application/json, text/event-stream',
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': PROTOCOL_VERSION,
    }
    if (this.sessionId !== undefined) headers['Mcp-Session-Id'] = this.sessionId
    const tags = { kind, name }
    const res = http.post(MCP_URL, JSON.stringify(payload), {
      headers,
      tags,
      timeout: REQUEST_TIMEOUT,
      responseCallback: http.expectedStatuses(200, 202, 429),
    })
    errors.add(isServerError(res.status), tags)
    if (res.status === 429) rateLimited.add(1, tags)
    check(res, { [`mcp ${name}: kein 5xx`]: (r) => !isServerError(r.status) }, tags)
    return res
  }

  _rpc(method, params, tagging) {
    rpcId += 1
    const res = this._post({ jsonrpc: '2.0', id: rpcId, method, params }, tagging)
    const message = res.status === 200 ? parseRpcBody(res.body, header(res, 'Content-Type')) : null
    return { res, message }
  }

  /** initialize + notifications/initialized. Liefert true bei Erfolg. */
  open() {
    const { res, message } = this._rpc(
      'initialize',
      {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: 'who2be-loadtest', version: '1' },
      },
      { kind: 'mcp_session', name: 'initialize' },
    )
    this.sessionId = header(res, 'Mcp-Session-Id')
    const ok =
      res.status === 200 &&
      this.sessionId !== undefined &&
      message !== null &&
      message.error === undefined
    sessionFailures.add(!ok)
    check(res, { 'mcp initialize: Session aufgebaut': () => ok })
    if (!ok) return false
    this._post(
      { jsonrpc: '2.0', method: 'notifications/initialized' },
      { kind: 'mcp_notify', name: 'notifications/initialized' },
    )
    return true
  }

  /** tools/list. Liefert die Zahl der Werkzeuge (0 bei Fehler). */
  listTools() {
    const { message } = this._rpc('tools/list', {}, { kind: 'mcp_session', name: 'tools/list' })
    const tools = message?.result?.tools
    const count = Array.isArray(tools) ? tools.length : 0
    check(null, { 'mcp tools/list: Werkzeuge vorhanden': () => count > 0 })
    return count
  }

  /**
   * tools/call. Liefert `{ ok, isError, text, status }`. Ein Werkzeug-Fehler
   * (`isError: true`) ist kein HTTP-Fehler und zaehlt in `mcp_tool_errors`;
   * Limit-Meldungen zusaetzlich in `mcp_tool_rate_limited`.
   */
  callTool(name, args) {
    const { res, message } = this._rpc(
      'tools/call',
      { name, arguments: args },
      { kind: 'mcp_call', name },
    )
    if (message === null || message.error !== undefined) {
      toolErrors.add(true, { name })
      return { ok: false, isError: true, text: message?.error?.message ?? '', status: res.status }
    }
    const result = message.result ?? {}
    const text = (result.content ?? []).find((block) => block.type === 'text')?.text ?? ''
    const isError = result.isError === true
    toolErrors.add(isError, { name })
    if (isError && /\b429\b|rate.?limit|limit erreicht|zu viele/i.test(text)) {
      toolRateLimited.add(1, { name })
    }
    return { ok: !isError, isError, text, status: res.status }
  }

  /** Beendet die Session serverseitig (DELETE), damit keine Sessions liegen bleiben. */
  close() {
    if (this.sessionId === undefined) return
    http.del(MCP_URL, null, {
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Mcp-Session-Id': this.sessionId,
        'MCP-Protocol-Version': PROTOCOL_VERSION,
      },
      tags: { kind: 'mcp_notify', name: 'session/delete' },
      timeout: REQUEST_TIMEOUT,
      responseCallback: http.expectedStatuses(200, 202, 204, 404, 405),
    })
    this.sessionId = undefined
  }
}

/**
 * T2: Agenten-Strecke wie ein echter Agent beim Start einer Aufgabe:
 * `initialize` → `tools/list` → `get_persona` → 3× `fetch_playbook` →
 * `search` → Session schliessen. Je Iteration eine neue Session; der Token
 * kommt reihum aus den agent-gebundenen Tokens des eigenen Workspaces.
 * `thinkBetween=false` laesst die Denkzeit weg (Spitze T8, Bruchpunkt T9).
 */
export function agentFlow({ thinkBetween = true } = {}) {
  const ws = myWorkspace()
  const session = new McpSession(ws.agent_tokens[mySlot() % ws.agent_tokens.length])
  if (!session.open()) return
  try {
    session.listTools()
    session.callTool('get_persona', { identifier: ws.persona_id })
    for (let i = 0; i < 3; i += 1) {
      if (thinkBetween) think()
      session.callTool('fetch_playbook', { playbook_id: pick(ws.playbook_ids) })
    }
    session.callTool('search', { query: `${pick(VOCABULARY)} ${pick(VOCABULARY)}`, limit: 10 })
  } finally {
    session.close()
  }
  if (thinkBetween) think()
}
