import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { config } from '@/config'

import { AgentConnectorSection } from './AgentConnectorSection'

const notifySuccess = vi.fn()
const notifyError = vi.fn()
const writeText = vi.fn()
const DEFAULT_MCP_URL = 'https://mcp.example.com/mcp'

vi.mock('@/config', () => ({
  config: { mcpUrl: 'https://mcp.example.com/mcp' },
}))

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

beforeEach(() => {
  notifySuccess.mockReset()
  notifyError.mockReset()
  writeText.mockReset()
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
})

afterEach(() => {
  vi.restoreAllMocks()
  config.mcpUrl = DEFAULT_MCP_URL
})

describe('AgentConnectorSection', () => {
  it('baut eine pro Agent eindeutige Connector-URL mit /a/<id> im Pfad', () => {
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)
    expect(screen.getByDisplayValue('https://mcp.example.com/mcp/a/abc-123')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Who2Be – Coder')).toBeInTheDocument()
  })

  it('vermeidet einen doppelten Slash, wenn mcpUrl bereits mit / endet', () => {
    config.mcpUrl = 'https://mcp.example.com/mcp/'
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)
    expect(screen.getByDisplayValue('https://mcp.example.com/mcp/a/abc-123')).toBeInTheDocument()
  })

  it('kopiert die URL in die Zwischenablage und meldet Erfolg', async () => {
    writeText.mockResolvedValue(undefined)
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)

    fireEvent.click(screen.getByRole('button', { name: 'URL kopieren' }))

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith('https://mcp.example.com/mcp/a/abc-123'),
    )
    expect(notifySuccess).toHaveBeenCalledWith('In Zwischenablage kopiert.')
  })
})

// Responsive-Vertrag #570 (AK 2): Connector-Name und Server-URL sind lange,
// trennstellenfreie technische Bezeichner in einem Read-only-`Input` neben
// einem Kopieren-Button. Gemessen am gebauten Stylesheet in Chromium bei
// 320 px schrumpft das Eingabefeld in der einzeiligen `flex`-Zeile auf 95 px
// (Server-URL) bzw. 77 px (Connector-Name) — von 521 bzw. 412 px Inhalt ist
// damit praktisch nichts lesbar, obwohl kein Body-Scroll entsteht (§4.4
// Punkt 5: abgeschnittener Text ist ein Defekt, auch ohne Ueberlauf).
//
// `flex-col` unterhalb `md` stellt den Button unter das Feld; das Feld
// erreicht damit die volle Spaltenbreite von 238 px. Ab `md` stellt
// `md:flex-row md:items-center` die Desktop-Zeile wieder her (Feld 527 px).
// Kein `min-w-0` am Input: gemessen bringt es hier nichts, weil `Input`
// bereits `w-full` traegt und die Zeile ihn ohnehin staucht.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1600_570-w3-agents-haelfte-b-responsive-audit.md
// gerendert belegt.
describe('AgentConnectorSection — Responsive (#570)', () => {
  it('stapelt Feld und Kopieren-Button unterhalb md und stellt ab md die Zeile wieder her', () => {
    render(<AgentConnectorSection agentId="abc-123" agentName="Coder" />)

    for (const id of ['connector-name', 'connector-url']) {
      const row = document.getElementById(id)?.parentElement
      expect(row).not.toBeNull()
      expect(row).toHaveClass('flex-col')
      expect(row).toHaveClass('md:flex-row')
      expect(row).toHaveClass('md:items-center')
    }
  })
})
