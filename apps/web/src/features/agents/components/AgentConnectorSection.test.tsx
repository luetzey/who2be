import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Agent, AgentUsageStats, Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { config } from '@/config'
import {
  agentConnectorUrl,
  claudeCodeCommand,
  claudeInstallLink,
  cursorInstallLink,
  hermesCommand,
  serverSlug,
  vscodeInstallLink,
} from '@/lib/installLinks'
import { axe } from '@/test/a11y'

import {
  AgentConnectorSection,
  CONFIRM_AFTER_MS,
  POLL_INTERVAL_MS,
  POLL_LIMIT_MS,
} from './AgentConnectorSection'

const notifySuccess = vi.fn()
const notifyError = vi.fn()
const writeText = vi.fn()
const ORIGINAL_MCP_URL = config.mcpUrl
const URL_ = 'https://mcp.example.com/mcp/a/abc-123'
const USAGE_PATH = '/v1/workspaces/ws-1/agents/abc-123/usage'

vi.mock('@/lib/feedback', () => ({
  notify: {
    success: (...args: unknown[]) => notifySuccess(...args),
    error: (...args: unknown[]) => notifyError(...args),
    info: vi.fn(),
  },
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'abc-123',
    name: 'Coder',
    status: 'enabled',
    activatable: true,
    missing: [],
    is_managed: false,
    ...overrides,
  } as Agent
}

function usage(lastUsedAt: string | null): AgentUsageStats {
  return {
    agent_id: 'abc-123',
    uses_7d: 0,
    uses_30d: 0,
    uses_by_type_30d: { persona: 0, playbook: 0, resource: 0 },
    active_days_30d: 0,
    last_used_at: lastUsedAt,
    last_active_at: null,
    daily: [],
    work_areas: [],
    counting_since: '2026-10-01',
  }
}

/** Antworten fuer die Nutzung der Reihe nach; die letzte gilt danach weiter. */
function stubUsage(...answers: Array<string | null | 'error'>) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname
    if (path !== USAGE_PATH) throw new Error(`Unmocked ${path}`)
    calls.push(path)
    const answer = answers[Math.min(calls.length - 1, answers.length - 1)]
    if (answer === 'error') return new Response('{}', { status: 500 })
    return new Response(JSON.stringify(usage(answer ?? null)), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

function renderSection(overrides: Partial<Agent> = {}) {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/abc-123']}>
          <AgentConnectorSection agent={agent(overrides)} />
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

beforeEach(() => {
  config.mcpUrl = 'https://mcp.example.com/mcp'
  notifySuccess.mockReset()
  notifyError.mockReset()
  writeText.mockReset()
  writeText.mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  config.mcpUrl = ORIGINAL_MCP_URL
})

async function notConnected() {
  return screen.findByText('Noch nicht verbunden')
}

function claudeCta() {
  return screen.getByRole('link', { name: /Mit Claude verbinden/ })
}

describe('AgentConnectorSection — Claude', () => {
  it('zeigt den Install-Link mit Name und Agent-URL als Hauptaktion', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()

    const cta = claudeCta()
    expect(cta).toHaveAttribute('target', '_blank')
    expect(cta).toHaveAttribute('rel', 'noopener noreferrer')
    expect(cta.className).toContain('bg-brand')
    // Der ganze Link wird verglichen: kein Token, kein weiterer Parameter, kein Fragment.
    const expected = new URLSearchParams({
      modal: 'add-custom-connector',
      connectorName: 'Who2Be – Coder',
      connectorUrl: URL_,
    })
    expect(cta.getAttribute('href')).toBe(
      `https://claude.ai/customize/connectors?${expected.toString()}`,
    )
    const href = new URL(cta.getAttribute('href') ?? '')
    expect([...href.searchParams.keys()].sort()).toEqual(['connectorName', 'connectorUrl', 'modal'])
    expect(href.hash).toBe('')
    expect(href.searchParams.get('connectorName')).toBe('Who2Be – Coder')
    expect(href.searchParams.get('connectorUrl')).toBe(URL_)
    expect(screen.getByRole('button', { name: 'Claude (Web, App, Handy)' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('haelt Name und URL im Aufklapper als Rueckfall bereit und kopiert sie', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()

    const manual = screen.getByTestId('connect-manual')
    expect(within(manual).getByLabelText('Server-URL')).toHaveTextContent(URL_)
    expect(within(manual).getByLabelText('Name')).toHaveTextContent('Who2Be – Coder')

    fireEvent.click(within(manual).getByRole('button', { name: 'URL kopieren' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(URL_))
    expect(notifySuccess).toHaveBeenCalledWith('In Zwischenablage kopiert.')
  })

  it('kopiert den Test-Satz', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()

    fireEvent.click(screen.getByRole('button', { name: 'Satz kopieren' }))
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith('Wer bist du? Lade deine Persona aus Who2Be.'),
    )
  })

  it('meldet einen Kopierfehler', async () => {
    stubUsage(null)
    writeText.mockRejectedValue(new Error('denied'))
    Object.defineProperty(document, 'execCommand', { value: () => false, configurable: true })
    renderSection()
    await notConnected()

    fireEvent.click(screen.getByRole('button', { name: 'Satz kopieren' }))
    await waitFor(() => expect(notifyError).toHaveBeenCalled())
    expect(notifySuccess).not.toHaveBeenCalled()
  })

  it('vermeidet einen doppelten Slash, wenn mcpUrl mit / endet', async () => {
    config.mcpUrl = 'https://mcp.example.com/mcp/'
    stubUsage(null)
    renderSection()
    await notConnected()
    const href = new URL(claudeCta().getAttribute('href') ?? '')
    expect(href.searchParams.get('connectorUrl')).toBe(URL_)
  })
})

describe('AgentConnectorSection — Warten und Erfolg (O6 a)', () => {
  it('erkennt den ersten Abruf beim Nachfragen alle 5 s und meldet ihn', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = stubUsage(null, null, '2026-10-22T10:00:00Z')
    renderSection()
    await notConnected()

    fireEvent.click(claudeCta())
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('Warte auf „Coder“')
    // Waehrend des Wartens ist der Knopf nicht mehr die Brand-Aktion.
    expect(screen.getByRole('link', { name: /Claude erneut öffnen/ }).className).not.toContain(
      'bg-brand',
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(screen.getByTestId('connect-waiting')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    await waitFor(() => expect(screen.queryByTestId('connect-waiting')).not.toBeInTheDocument())
    expect(screen.getByTestId('connect-live')).toHaveTextContent(
      'Verbunden. „Coder“ hat seine Persona geladen.',
    )
    expect(screen.getByTestId('connect-status')).toHaveTextContent('Verbunden')
    expect(screen.getByTestId('connect-compact')).toHaveTextContent('Zuletzt abgerufen am')
    expect(calls.length).toBe(3)
  })

  it('fragt bei Rueckkehr in den Tab sofort nach', async () => {
    const calls = stubUsage(null, '2026-10-22T10:00:00Z')
    renderSection()
    await notConnected()

    fireEvent.click(claudeCta())
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await waitFor(() => expect(screen.getByTestId('connect-compact')).toBeInTheDocument())
    expect(calls.length).toBe(2)
  })

  it('zaehlt einen alten Abruf nicht als Erfolg', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubUsage('2026-10-01T08:00:00Z')
    renderSection()
    // Schon einmal abgerufen: kurze Fassung, ueber „Verbindung hinzufuegen“ auf.
    fireEvent.click(await screen.findByRole('button', { name: 'Verbindung hinzufügen' }))
    fireEvent.click(claudeCta())

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2)
    })
    expect(screen.getByTestId('connect-waiting')).toBeInTheDocument()
    expect(screen.getByTestId('connect-live')).toHaveTextContent('')
  })

  it('bietet nach 2 Minuten „Ja, weiter“ und hoert nach 10 Minuten auf', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(claudeCta())

    expect(screen.queryByRole('button', { name: 'Ja, weiter' })).not.toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CONFIRM_AFTER_MS)
    })
    expect(screen.getByRole('button', { name: 'Ja, weiter' })).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_LIMIT_MS - CONFIRM_AFTER_MS)
    })
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('fragt nicht mehr')
    const after = calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3)
    })
    expect(calls.length).toBe(after)

    fireEvent.click(screen.getByRole('button', { name: 'Ja, weiter' }))
    expect(screen.queryByTestId('connect-waiting')).not.toBeInTheDocument()
    expect(screen.getByTestId('connect-status')).toHaveTextContent('Verbunden')
    expect(screen.getByTestId('connect-compact')).toHaveTextContent('bestätigt')
  })

  it('startet bei einem Ladefehler ohne Stand und nimmt den ersten Abruf als Basis', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    stubUsage('error', '2026-10-01T08:00:00Z', '2026-10-01T08:00:00Z', '2026-10-22T10:00:00Z')
    renderSection()
    const cta = await screen.findByRole('link', { name: /Mit Claude verbinden/ })
    // Ohne bekannten Stand keine Kapsel (sie wuerde raten).
    expect(screen.queryByTestId('connect-status')).not.toBeInTheDocument()
    fireEvent.click(cta)

    // Erster Takt setzt die Basis, zweiter Takt liefert denselben alten Stand:
    // beides ist noch kein Erfolg.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(screen.getByTestId('connect-waiting')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    expect(screen.getByTestId('connect-waiting')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS)
    })
    await waitFor(() => expect(screen.queryByTestId('connect-waiting')).not.toBeInTheDocument())
  })
})

describe('AgentConnectorSection — andere Programme', () => {
  it('Claude Code: Befehl kopieren startet das Warten', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: 'Claude Code' }))

    expect(screen.getByRole('button', { name: 'Claude Code' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Befehl')).toHaveTextContent(
      `claude mcp add --transport http who2be-coder ${URL_}`,
    )
    // Befehl mit URL: darf mitten im Wort brechen (keine Trennstelle).
    expect(screen.getByLabelText('Befehl')).toHaveClass('break-all')
    fireEvent.click(screen.getByRole('button', { name: 'Befehl kopieren' }))
    await waitFor(() => expect(screen.getByTestId('connect-waiting')).toBeInTheDocument())
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('in Claude Code')
  })

  it('Cursor oder VS Code: zwei Deeplinks, nur einer als Brand', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: 'Cursor oder VS Code' }))

    const cursor = screen.getByRole('link', { name: /Zu Cursor hinzufügen/ })
    const vscode = screen.getByRole('link', { name: /In VS Code installieren/ })
    expect(cursor.getAttribute('href')).toMatch(/^cursor:\/\/anysphere\.cursor-deeplink\/mcp\/install\?/)
    expect(vscode.getAttribute('href')).toMatch(/^vscode:mcp\/install\?/)
    expect(cursor.className).toContain('bg-brand')
    expect(vscode.className).not.toContain('bg-brand')
    fireEvent.click(vscode)
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('in deinem Editor')
  })

  it('Etwas anderes: URL, Test-Satz und „Ich habe die Adresse eingetragen“', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: 'Etwas anderes' }))

    expect(screen.getByLabelText('Server-URL')).toHaveTextContent(URL_)
    expect(screen.queryByRole('link', { name: /Mit Claude verbinden/ })).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'So geht es in Gemini, Le Chat, Windsurf, Zed und Copilot' }),
    ).toHaveAttribute('href', '/w/ws-1/help/connect-other-clients#steckbriefe')
    fireEvent.click(screen.getByRole('button', { name: 'Ich habe die Adresse eingetragen' }))
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('in deinem Programm')
    expect(
      screen.queryByRole('button', { name: 'Ich habe die Adresse eingetragen' }),
    ).not.toBeInTheDocument()
  })

  it('Hermes Agent: OAuth-Befehl als einzige Brand-Aktion, Kopieren startet das Warten', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: 'Hermes Agent' }))

    expect(screen.getByRole('button', { name: 'Hermes Agent' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('connect-lead')).toHaveTextContent(
      'Im Terminal des Rechners, auf dem Hermes läuft.',
    )
    const command = screen.getByLabelText('Befehl')
    expect(command).toHaveTextContent(`hermes mcp add who2be-coder --url ${URL_} --auth oauth`)
    expect(command).toHaveClass('break-all')
    // Schritt 3 nennt /reload-mcp als Code, ohne Kopierknopf.
    expect(screen.getByText('/reload-mcp').tagName).toBe('CODE')
    expect(screen.getByTestId('connect-hints')).toHaveTextContent('hermes -p <profil> mcp add …')
    expect(screen.getByTestId('connect-hints')).toHaveTextContent('Server ohne Browser')

    const guide = screen.getByTestId('connect-guide')
    const brand = within(guide)
      .getAllByRole('button')
      .filter((el) => el.className.includes('bg-brand'))
    expect(brand.map((el) => el.textContent)).toEqual(['Befehl kopieren'])

    fireEvent.click(screen.getByRole('button', { name: 'Befehl kopieren' }))
    await waitFor(() => expect(screen.getByTestId('connect-waiting')).toBeInTheDocument())
    expect(writeText).toHaveBeenCalledWith(`hermes mcp add who2be-coder --url ${URL_} --auth oauth`)
    expect(screen.getByTestId('connect-waiting')).toHaveTextContent('in Hermes')
    // Waehrend des Wartens ist der Befehl keine Brand-Aktion mehr.
    expect(screen.getByRole('button', { name: 'Befehl kopieren' }).className).not.toContain('bg-brand')
    expect(screen.getByRole('link', { name: 'Klappt es nicht? Häufige Ursachen' })).toHaveAttribute(
      'href',
      '/w/ws-1/help/connect-other-clients#hermes',
    )
  })
})

describe('AgentConnectorSection — Auswahl (Client-Auswahl P-A)', () => {
  it('zeigt fuenf Kacheln in fester Reihenfolge im Raster 2 × 3 / 3 × 2', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()

    const group = screen.getByRole('group', { name: 'Wo nutzt du deine Agenten?' })
    expect(within(group).getAllByRole('button').map((el) => el.textContent)).toEqual([
      'Claude (Web, App, Handy)',
      'Claude Code',
      'Cursor oder VS Code',
      'Hermes Agent',
      'Etwas anderes',
    ])
    expect(group).toHaveClass('grid', 'grid-cols-2', 'md:grid-cols-3')
    expect(group).not.toHaveClass('sm:flex')
  })

  it('Untertitel wechselt mit der Auswahl und beschreibt die Schritte', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()

    const lead = screen.getByTestId('connect-lead')
    expect(lead).toHaveTextContent('Web, App am Computer und am Handy.')
    const steps = screen.getByRole('list')
    expect(steps).toHaveAttribute('aria-describedby', lead.id)

    fireEvent.click(screen.getByRole('button', { name: 'Claude Code' }))
    expect(screen.getByTestId('connect-lead')).toHaveTextContent('Im Terminal, mit einem Befehl.')
  })

  it.each([
    ['Claude (Web, App, Handy)', /Mit Claude verbinden/, '/w/ws-1/help/connect-claude#troubleshooting'],
    ['Claude Code', 'Befehl kopieren', '/w/ws-1/help/connect-other-clients#claude-code'],
    ['Cursor oder VS Code', /Zu Cursor hinzufügen/, '/w/ws-1/help/connect-other-clients#cursor-vscode'],
    ['Etwas anderes', 'Ich habe die Adresse eingetragen', '/w/ws-1/help/connect-other-clients#andere'],
  ] as const)('Hilfe-Link beim Warten fuer %s', async (tile, action, href) => {
    stubUsage(null)
    renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: tile }))
    const target =
      screen.queryByRole('link', { name: action }) ?? screen.getByRole('button', { name: action })
    fireEvent.click(target)
    const link = await screen.findByRole('link', { name: 'Klappt es nicht? Häufige Ursachen' })
    expect(link).toHaveAttribute('href', href)
  })

  it('a11y: keine axe-Befunde bei Hermes', async () => {
    stubUsage(null)
    const { container } = renderSection()
    await notConnected()
    fireEvent.click(screen.getByRole('button', { name: 'Hermes Agent' }))
    expect(await axe(container)).toHaveNoViolations()
  })
})

describe('AgentConnectorSection — Zustaende', () => {
  it('nicht bereit: Fehlt-Meldung mit Link statt Hauptaktion', async () => {
    stubUsage(null)
    renderSection({ status: 'disabled', activatable: false, missing: ['persona_active'] })

    const notice = await screen.findByTestId('connect-not-ready')
    expect(notice).toHaveTextContent('Noch nicht aktivierbar')
    expect(within(notice).getByRole('link', { name: 'Zu den Einstellungen' })).toHaveAttribute(
      'href',
      '/w/ws-1/agents/abc-123?tab=settings',
    )
    expect(screen.queryByRole('link', { name: /Mit Claude verbinden/ })).not.toBeInTheDocument()
  })

  it('deaktiviert, aber aktivierbar: eigener Hinweis', async () => {
    stubUsage(null)
    renderSection({ status: 'disabled' })
    expect(await screen.findByTestId('connect-not-ready')).toHaveTextContent(
      'Der Agent ist nicht aktiv.',
    )
  })

  it('verbunden: eine Zeile mit letztem Abruf, aufklappbar und wieder einklappbar', async () => {
    stubUsage('2026-10-22T10:00:00Z')
    renderSection()

    expect(await screen.findByTestId('connect-compact')).toHaveTextContent('Zuletzt abgerufen am')
    expect(screen.queryByRole('link', { name: /Mit Claude verbinden/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Verbindung hinzufügen' }))
    expect(claudeCta()).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Einklappen' }))
    expect(screen.getByTestId('connect-compact')).toBeInTheDocument()
  })

  it('Claude-Free-Hinweis nur bei eigenen Agenten, nicht beim Builder', async () => {
    stubUsage(null)
    const { unmount } = renderSection({ is_managed: true })
    await notConnected()
    expect(screen.queryByText(/Claude Free/)).not.toBeInTheDocument()
    unmount()

    renderSection()
    await notConnected()
    expect(screen.getByText(/Claude Free/)).toBeInTheDocument()
  })

  it('a11y: keine axe-Befunde im offenen und im wartenden Zustand', async () => {
    stubUsage(null)
    const { container } = renderSection()
    await notConnected()
    expect(await axe(container)).toHaveNoViolations()
    fireEvent.click(claudeCta())
    expect(await axe(container)).toHaveNoViolations()
  })
})

// Responsive-Vertrag #570: lange Werte (URL, Befehl) stehen unter `md` ueber
// dem Knopf und brechen um, statt abgeschnitten zu werden. jsdom hat kein
// Layout, deshalb ein Klassen-Vertrag; gemessen in den Abgabe-Fotos.
describe('AgentConnectorSection — Responsive (#570)', () => {
  it('stapelt Wert und Kopierknopf unterhalb md, Werte brechen um', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    const value = within(screen.getByTestId('connect-manual')).getByLabelText('Server-URL')
    expect(value).toHaveClass('break-all')
    const row = value.parentElement
    expect(row).toHaveClass('flex-col')
    expect(row).toHaveClass('md:flex-row')
  })

  it('Text bricht an Wortgrenzen, nur URLs und Befehle mitten im Wort', async () => {
    stubUsage(null)
    renderSection()
    await notConnected()
    // Test-Satz und Name sind Text: kein Zerreissen mitten im Wort bei 320 px.
    const sentence = screen.getByLabelText('Test-Satz')
    expect(sentence).toHaveClass('break-words')
    expect(sentence).not.toHaveClass('break-all')
    const name = within(screen.getByTestId('connect-manual')).getByLabelText('Name')
    expect(name).toHaveClass('break-words')
    expect(name).not.toHaveClass('break-all')
  })
})

// Reine Link-Bausteine aus `@/lib/installLinks` (hier statt in eigener Datei:
// Paketgrenze ≤ 8 Dateien, Karte t_e8e35e97).
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
    expect(link.hash).toBe('')
    // Genau diese drei Parameter — ein zusaetzlicher (etwa ein Token) waere ein Leck.
    expect([...link.searchParams.keys()].sort()).toEqual(['connectorName', 'connectorUrl', 'modal'])
    expect(link.searchParams.get('modal')).toBe('add-custom-connector')
    expect(link.searchParams.get('connectorName')).toBe('Who2Be – Carla')
    expect(link.searchParams.get('connectorUrl')).toBe(URL_)
  })

  it('Claude-Code-Befehl nutzt den HTTP-Transport ohne Token', () => {
    expect(claudeCodeCommand('who2be-carla', URL_)).toBe(
      `claude mcp add --transport http who2be-carla ${URL_}`,
    )
  })

  it('Hermes-Befehl traegt Name, URL und die OAuth-Anmeldung, kein Token', () => {
    // Ganzer Befehl verglichen: ohne `--auth oauth` meldet sich Hermes nicht an.
    expect(hermesCommand('who2be-carla', URL_)).toBe(
      `hermes mcp add who2be-carla --url ${URL_} --auth oauth`,
    )
  })

  it('Cursor-Deeplink traegt die URL als base64-JSON', () => {
    const link = cursorInstallLink('who2be-carla', URL_)
    expect(link.startsWith('cursor://anysphere.cursor-deeplink/mcp/install?')).toBe(true)
    const query = new URLSearchParams(link.split('?')[1])
    expect([...query.keys()].sort()).toEqual(['config', 'name'])
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
