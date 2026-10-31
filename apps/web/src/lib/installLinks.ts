// Ein-Klick-Wege, einen Who2Be-Agenten als Remote-MCP-Server (OAuth) in einem
// Programm einzutragen (Onboarding-Spec §5.1). Alle Links tragen nur Name und
// URL — kein Token: angemeldet wird beim Verbinden per OAuth.
//
// Quellen (Stand 2026-10):
// - Claude: https://claude.com/docs/connectors/building/directory-vs-custom
//   (`/customize/connectors?modal=add-custom-connector&connectorName&connectorUrl`).
//   Gegen Who2Be-OAuth noch ungetestet (P0, Owner-Test vor dem Release).
// - Cursor: https://cursor.com/docs/mcp/install-links (`name` + base64-JSON `config`).
// - VS Code: https://code.visualstudio.com/api/extension-guides/ai/mcp
//   (`vscode:mcp/install?<urlencoded JSON>`).
// - Claude Code: `claude mcp add --transport http <name> <url>`.
// - Hermes Agent: `hermes mcp add <name> --url <url> --auth oauth`
//   (`hermes mcp add --help`; Hermes-Doku user-guide/features/mcp,
//   „OAuth-authenticated HTTP servers“).

export type ConnectClient = 'claude' | 'code' | 'editor' | 'hermes' | 'other'

/**
 * Reihenfolge der Auswahl (Client-Auswahl-Spec §1): erst das Chat-Programm,
 * dann die Entwickler-Werkzeuge, dann der Agent-Rahmen, der Rueckfall zuletzt.
 * Einzige Quelle — Baustein und Begruessung lesen beide von hier.
 */
export const CONNECT_CLIENTS: readonly ConnectClient[] = ['claude', 'code', 'editor', 'hermes', 'other']

/**
 * Ziel von „Klappt es nicht? Häufige Ursachen“ je Programm (Spec §2.5),
 * relativ zum Workspace.
 */
export const CONNECT_HELP_PATHS: Readonly<Record<ConnectClient, string>> = {
  claude: '/help/connect-claude#troubleshooting',
  code: '/help/connect-other-clients#claude-code',
  editor: '/help/connect-other-clients#cursor-vscode',
  hermes: '/help/connect-other-clients#hermes',
  other: '/help/connect-other-clients#andere',
}

/** Steckbriefe weiterer Programme (Gemini, Le Chat, …) in der Hilfe. */
export const OTHER_CLIENTS_HELP_PATH = '/help/connect-other-clients#steckbriefe'

/**
 * Anker der Karte „Verbindung“ auf der Agent-Seite (UX-Audit B1):
 * `/agents/<id>#connect` oeffnet den Ueberblick und springt die Karte an.
 * Ziel des Startlisten-Knopfs „Builder verbinden“.
 */
export const AGENT_CONNECT_HASH = '#connect'

/** Server-URL eines Agenten: der Agent steht im Pfad (`/a/<id>`, Issue #404). */
export function agentConnectorUrl(mcpUrl: string, agentId: string): string {
  return `${mcpUrl.replace(/\/+$/, '')}/a/${encodeURIComponent(agentId)}`
}

/**
 * Kurzer, shell- und konfigsicherer Servername (`who2be-<agent>`). Umlaute
 * werden umschrieben, alles andere ausser a-z/0-9 wird zu `-`. Bleibt vom
 * Agentennamen nichts uebrig, heisst der Server nur `who2be`.
 */
export function serverSlug(agentName: string): string {
  const base = agentName
    .toLowerCase()
    .replace(/ä/g, 'ae')
    .replace(/ö/g, 'oe')
    .replace(/ü/g, 'ue')
    .replace(/ß/g, 'ss')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/g, '')
  return base === '' ? 'who2be' : `who2be-${base}`
}

export function claudeInstallLink(connectorName: string, connectorUrl: string): string {
  const query = new URLSearchParams({
    modal: 'add-custom-connector',
    connectorName,
    connectorUrl,
  })
  return `https://claude.ai/customize/connectors?${query.toString()}`
}

export function claudeCodeCommand(serverName: string, connectorUrl: string): string {
  return `claude mcp add --transport http ${serverName} ${connectorUrl}`
}

/**
 * Hermes Agent traegt den Server per OAuth ein. `--auth oauth` ist Pflicht:
 * ohne meldet sich Hermes nicht per OAuth an, und einen anderen Weg (etwa ein
 * festes Token) bietet Who2Be nicht.
 */
export function hermesCommand(serverName: string, connectorUrl: string): string {
  return `hermes mcp add ${serverName} --url ${connectorUrl} --auth oauth`
}

/** base64 eines ASCII-Strings ohne `btoa`-Abhaengigkeit vom DOM-Zeichensatz. */
function base64Ascii(value: string): string {
  // Die Konfiguration enthaelt nur die URL; Nicht-ASCII waere ein Bug.
  if (!/^[\x20-\x7e]*$/.test(value)) throw new Error('non-ascii config')
  return btoa(value)
}

export function cursorInstallLink(serverName: string, connectorUrl: string): string {
  const config = base64Ascii(JSON.stringify({ url: connectorUrl }))
  const query = new URLSearchParams({ name: serverName, config })
  return `cursor://anysphere.cursor-deeplink/mcp/install?${query.toString()}`
}

export function vscodeInstallLink(serverName: string, connectorUrl: string): string {
  const config = JSON.stringify({ name: serverName, type: 'http', url: connectorUrl })
  return `vscode:mcp/install?${encodeURIComponent(config)}`
}
