import { describe, expect, it } from 'vitest'

import { buildMcpConfig } from './mcpConfig'

const input = { mcpUrl: 'https://mcp.example.com/mcp', token: 'w2b_secret' }

describe('buildMcpConfig', () => {
  it('JSON: mcp-remote-stdio-Bruecke mit URL + Bearer-Header', () => {
    const parsed = JSON.parse(buildMcpConfig('json', input))
    expect(parsed.mcpServers.who2be).toEqual({
      command: 'npx',
      args: [
        '-y',
        'mcp-remote',
        'https://mcp.example.com/mcp',
        '--header',
        'Authorization: Bearer w2b_secret',
      ],
    })
  })

  it('CLI: claude-mcp-add-Befehl mit Transport + Header', () => {
    const cli = buildMcpConfig('cli', input)
    expect(cli).toBe(
      'claude mcp add --transport http who2be https://mcp.example.com/mcp ' +
        '--header "Authorization: Bearer w2b_secret"',
    )
  })

  it('Manual: URL + Authorization-Header als Klartext', () => {
    expect(buildMcpConfig('manual', input)).toBe(
      'URL: https://mcp.example.com/mcp\nHeader: Authorization: Bearer w2b_secret',
    )
  })
})
