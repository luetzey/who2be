import { describe, expect, it } from 'vitest'

import {
  agentConnectorUrl,
  claudeCodeCommand,
  claudeInstallLink,
  cursorInstallLink,
  serverSlug,
  vscodeInstallLink,
} from './installLinks'

const URL_ = 'https://mcp.example.com/mcp/a/abc-123'

describe('installLinks', () => {
  it('baut die Agent-URL mit /a/<id> und ohne doppelten Slash', () => {
    expect(agentConnectorUrl('https://mcp.example.com/mcp', 'abc-123')).toBe(URL_)
    expect(agentConnectorUrl('https://mcp.example.com/mcp//', 'abc-123')).toBe(URL_)
  })

  it('kodiert eine ID mit Sonderzeichen, statt den Pfad zu verlaengern', () => {
    expect(agentConnectorUrl('https://m.example/mcp', '../x?y')).toBe(
      'https://m.example/mcp/a/..%2Fx%3Fy',
    )
  })

  it('macht aus dem Agentennamen einen sicheren Servernamen', () => {
    expect(serverSlug('Carla Bot')).toBe('who2be-carla-bot')
    expect(serverSlug('Größen-Prüfer')).toBe('who2be-groessen-pruefer')
    expect(serverSlug('Café; rm -rf /')).toBe('who2be-cafe-rm-rf')
    expect(serverSlug('***')).toBe('who2be')
    expect(serverSlug('a'.repeat(80))).toBe(`who2be-${'a'.repeat(40)}`)
  })

  it('Claude-Install-Link traegt Name und URL als Query', () => {
    const link = new URL(claudeInstallLink('Who2Be – Carla', URL_))
    expect(link.origin).toBe('https://claude.ai')
    expect(link.pathname).toBe('/customize/connectors')
    expect(link.searchParams.get('modal')).toBe('add-custom-connector')
    expect(link.searchParams.get('connectorName')).toBe('Who2Be – Carla')
    expect(link.searchParams.get('connectorUrl')).toBe(URL_)
  })

  it('Claude-Code-Befehl nutzt den HTTP-Transport ohne Token', () => {
    expect(claudeCodeCommand('who2be-carla', URL_)).toBe(
      `claude mcp add --transport http who2be-carla ${URL_}`,
    )
  })

  it('Cursor-Deeplink traegt die URL als base64-JSON', () => {
    const link = cursorInstallLink('who2be-carla', URL_)
    expect(link.startsWith('cursor://anysphere.cursor-deeplink/mcp/install?')).toBe(true)
    const query = new URLSearchParams(link.split('?')[1])
    expect(query.get('name')).toBe('who2be-carla')
    expect(JSON.parse(atob(query.get('config') ?? ''))).toEqual({ url: URL_ })
  })

  it('Cursor-Deeplink lehnt eine Nicht-ASCII-Konfiguration ab', () => {
    expect(() => cursorInstallLink('x', 'https://ä.example')).toThrow('non-ascii')
  })

  it('VS-Code-Link traegt die Konfiguration URL-kodiert', () => {
    const link = vscodeInstallLink('who2be-carla', URL_)
    expect(link.startsWith('vscode:mcp/install?')).toBe(true)
    expect(JSON.parse(decodeURIComponent(link.slice('vscode:mcp/install?'.length)))).toEqual({
      name: 'who2be-carla',
      type: 'http',
      url: URL_,
    })
  })
})
