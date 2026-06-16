// Baut fertige MCP-Client-Konfigurationen mit URL + Token (ADR-0034: der
// HTTP-MCP-Server authentifiziert pro Request mit dem Bearer-Token). Der Token
// ist nur im Reveal-Moment verfuegbar — diese Strings werden dort erzeugt.

export type McpConfigFormat = 'json' | 'cli' | 'manual' | 'prompt'

export interface McpConfigInput {
  mcpUrl: string
  token: string
}

// Reihenfolge = Anzeige-Reihenfolge im Format-Umschalter. Der `prompt`-Inhalt
// ist lokalisiert und wird in der Komponente erzeugt (nicht hier).
export const MCP_CONFIG_FORMATS: { id: McpConfigFormat; labelKey: string }[] = [
  { id: 'json', labelKey: 'mcp.format.json' },
  { id: 'cli', labelKey: 'mcp.format.cli' },
  { id: 'manual', labelKey: 'mcp.format.manual' },
  { id: 'prompt', labelKey: 'mcp.format.prompt' },
]

/**
 * Strukturierte Formate (JSON/CLI/Manual). Das `prompt`-Format ist lokalisierter
 * Fliesstext und wird separat in der Komponente gebaut.
 */
export function buildMcpConfig(
  format: Exclude<McpConfigFormat, 'prompt'>,
  { mcpUrl, token }: McpConfigInput,
): string {
  const bearer = `Bearer ${token}`
  switch (format) {
    case 'json':
      // mcpServers-Block fuer Claude Desktop / Cowork / Cursor. Deren Config-
      // Datei kennt nur stdio-Server (command/args), KEIN Inline-`type: http` —
      // daher die `mcp-remote`-Bruecke, die auf den HTTP-Server zeigt und den
      // Bearer-Header durchreicht. Funktioniert auch in Claude Code.
      return JSON.stringify(
        {
          mcpServers: {
            who2be: {
              command: 'npx',
              args: ['-y', 'mcp-remote', mcpUrl, '--header', `Authorization: ${bearer}`],
            },
          },
        },
        null,
        2,
      )
    case 'cli':
      // Claude-Code-CLI: nativer HTTP-Transport mit Auth-Header (kein mcp-remote noetig).
      return `claude mcp add --transport http who2be ${mcpUrl} --header "Authorization: ${bearer}"`
    case 'manual':
      return `URL: ${mcpUrl}\nHeader: Authorization: ${bearer}`
  }
}
