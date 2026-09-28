import type { APIRequestContext } from '@playwright/test'

/**
 * Minimaler MCP-Client fuer E2E: spricht den ECHTEN MCP-Dienst des
 * Compose-Stacks (`mcp`, Streamable-HTTP auf :8765, ADR-0034) — kein Mock.
 *
 * Auth: ein normaler `w2b_`-Token als Bearer. Der Server introspectiert ihn
 * per `GET /v1/me` gegen die API (`apps/mcp/src/who2be_mcp/auth.py`) — kein
 * OAuth-Consent-Flow noetig (siehe Kommentar am `mcp`-Dienst in
 * docker-compose.yml).
 *
 * Ablauf je Aufruf wie ein echter Client: `initialize` → Session-Id aus dem
 * Header `mcp-session-id` → `notifications/initialized` → `tools/call`. Die
 * Antwort kommt je nach Server-Einstellung als JSON oder als SSE-Stream
 * (`text/event-stream`); beides wird gelesen.
 */
const MCP_URL = process.env.E2E_MCP_URL ?? 'http://localhost:8765/mcp'
const PROTOCOL_VERSION = '2025-06-18'

interface JsonRpcResponse {
  jsonrpc: '2.0'
  id?: number
  result?: unknown
  error?: { code: number; message: string }
}

export interface McpToolResult {
  isError: boolean
  /** Text des ersten Content-Blocks (bei Tool-Erfolg: JSON der Tool-Antwort). */
  text: string
}

/** Liest die JSON-RPC-Antwort aus einem JSON- oder SSE-Body. */
function parseRpcBody(body: string, contentType: string): JsonRpcResponse {
  if (!contentType.includes('text/event-stream')) {
    return JSON.parse(body) as JsonRpcResponse
  }
  // SSE: die Antwort steht in den `data:`-Zeilen eines Events. Die letzte
  // `data:`-Zeile mit JSON-RPC-Antwort (id gesetzt) gewinnt.
  const messages = body
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => JSON.parse(line.slice('data:'.length).trim()) as JsonRpcResponse)
  const response = messages.reverse().find((message) => message.id !== undefined)
  if (response === undefined) {
    throw new Error(`MCP-SSE ohne JSON-RPC-Antwort: ${body}`)
  }
  return response
}

async function rpc(
  request: APIRequestContext,
  token: string,
  sessionId: string | undefined,
  payload: Record<string, unknown>,
): Promise<{ response: JsonRpcResponse | undefined; sessionId: string | undefined }> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/json, text/event-stream',
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': PROTOCOL_VERSION,
  }
  if (sessionId !== undefined) headers['mcp-session-id'] = sessionId
  const res = await request.post(MCP_URL, { headers, data: payload })
  const body = await res.text()
  if (!res.ok()) {
    throw new Error(`MCP ${String(payload.method)} → ${res.status()}: ${body}`)
  }
  const nextSession = res.headers()['mcp-session-id'] ?? sessionId
  // Notifications antworten mit 202 und leerem Body.
  if (body.trim() === '') return { response: undefined, sessionId: nextSession }
  return {
    response: parseRpcBody(body, res.headers()['content-type'] ?? ''),
    sessionId: nextSession,
  }
}

/**
 * Ruft ein MCP-Tool ueber eine frische Session auf. Frische Session pro
 * Aufruf: jeder Abruf im Test soll den Stand sehen, den ein neu verbundener
 * Agent sieht — kein Zustand aus einem frueheren Abruf.
 */
export async function callMcpTool(
  request: APIRequestContext,
  token: string,
  name: string,
  args: Record<string, unknown>,
): Promise<McpToolResult> {
  const init = await rpc(request, token, undefined, {
    jsonrpc: '2.0',
    id: 1,
    method: 'initialize',
    params: {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: 'who2be-e2e', version: '1' },
    },
  })
  if (init.response?.error !== undefined) {
    throw new Error(`MCP initialize: ${init.response.error.message}`)
  }
  const sessionId = init.sessionId
  await rpc(request, token, sessionId, { jsonrpc: '2.0', method: 'notifications/initialized' })
  const call = await rpc(request, token, sessionId, {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: { name, arguments: args },
  })
  if (call.response === undefined) throw new Error('MCP tools/call ohne Antwort')
  if (call.response.error !== undefined) {
    throw new Error(`MCP tools/call ${name}: ${call.response.error.message}`)
  }
  const result = call.response.result as {
    isError?: boolean
    content?: { type: string; text?: string }[]
  }
  return {
    isError: result.isError === true,
    text: result.content?.find((block) => block.type === 'text')?.text ?? '',
  }
}
