import type { Session } from '@supabase/supabase-js'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_TOOL_POLICY, type Agent, type Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { AgentsPage } from './AgentsPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

const WS_PREFIX = '/v1/workspaces/ws-1'

// Domaenentypische, pessimistische Fixtures: snake_case-Bezeichner ohne
// Trennstelle, wie sie in Persona- und Template-Namen der Realfall sind.
const PERSONA_NAME = 'kundenservice-eskalation-zweite-stufe'
const TEMPLATE_NAME = 'systemprompt_kundenservice_eskalation'

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'a1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Carla Bot',
    description: '',
    persona_id: 'p1',
    persona_name: PERSONA_NAME,
    system_prompt_template_id: 'sp1',
    template_name: TEMPLATE_NAME,
    template_version: 14,
    status: 'enabled',
    tool_policy: DEFAULT_TOOL_POLICY,
    persona_active: true,
    activatable: true,
    missing: [],
    playbook_count: 3,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function stubAgents(agents: Agent[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const { pathname } = new URL(String(input))
      if (pathname === `${WS_PREFIX}/agents`) {
        return new Response(JSON.stringify(agents), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error(`Unmocked GET ${pathname}`)
    }),
  )
}

function renderPage() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents']}>
          <Routes>
            <Route path="/w/:workspaceId/agents" element={<AgentsPage />} />
            <Route path="/w/:workspaceId/agents/:id" element={<div>Detail</div>} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

// Responsive-Vertrag #570 (Haelfte A).
//
// Zur Zahl 40 px: sie kommt aus **AK 4 dieses Issues**, nicht aus der Norm.
// `docs/frontend/design-language.md` §11 ist die einzige Quelle des
// Hit-Target-Floors und setzt ihn auf >= 32 px; 40 px ist dort die Praeferenz
// `size="default"`, und `size="sm"` (36 px) ist ausdruecklich zulaessig. Die
// gemessenen 32 und 36 px dieser Datei sind nach der Norm also konform —
// dieses Paket hebt sie unterhalb `md` an, weil sein Akzeptanzkriterium es
// verlangt.
//
// `min-h-10 md:min-h-0` ist woertlich die Klassenfolge aus PR #604
// (`SettingsNav`) und #605 (`WorkAreaNav`, `AreaGrants`).
//
// Das Issue notiert fuer diese Datei „kein Klassen-Befund" — das stimmt fuer die
// Klassen und ist gerade der Grund, genauer zu messen: die Defekte sitzen im
// Inhalt (trennstellenfreie Bezeichner in Pillen), nicht in den Klassen.
//
// jsdom hat kein Layout, deshalb sind das hier Klassen-Vertraege. Die
// Layout-Aussagen sind in
// .claude/plan/2026-09-23-1420_570-w3-agents-haelfte-a-responsive-audit.md
// gegen das gebaute CSS in Chromium bei 320 px gerendert belegt.
describe('AgentsPage — Responsive (#570)', () => {
  it('kuerzt den Template-Bezeichner kontrolliert statt ihn aus der Spalte laufen zu lassen', async () => {
    stubAgents([agent()])
    renderPage()

    const pill = await screen.findByText(`${TEMPLATE_NAME} · v14`)
    // Gemessen bei 320 px: 256 px in einer 238 px breiten Spalte (+18 px
    // Ueberlauf), ohne Versionssuffix sogar 319,5 px (+81 px) — isoliert
    // gegengemessen, also nicht Folge eines anderen Fundes.
    //
    // Warum `min-w-0 truncate` und nicht `break-all`/`break-words`, alle drei
    // gegeneinander gemessen:
    //   - `break-words` reicht nicht: ein reiner snake_case-Bezeichner hat
    //     keine Trennstelle (Underscores sind keine), gemessen blieb er mit
    //     297 px in 238 px abgeschnitten.
    //   - `break-all` loest es in einer normalen Spalte (238 px), entartet aber
    //     sobald die Karte Zeilen-Aktionen traegt: dann kollabiert die
    //     Textspalte des `EntityCard`-Primitives auf 16 px und die Pille wird
    //     gemessen 612 px HOCH — ein Zeichen pro Zeile.
    //   - `min-w-0 truncate` haelt die Pille in beiden Lagen in der Spalte.
    // AK 2 laesst „kuerzen kontrolliert" ausdruecklich zu, und es ist woertlich
    // das Muster aus `AgentHierarchyView.tsx:64`/`:98` (Vorentscheidung 1 des
    // Issues: diese Datei ist das Vorbild, nicht die Baustelle).
    expect(pill).toHaveClass('min-w-0')
    expect(pill).toHaveClass('truncate')
  })

  it('kuerzt den Persona-Bezeichner kontrolliert', async () => {
    stubAgents([agent()])
    renderPage()

    const pill = await screen.findByText(PERSONA_NAME)
    // Gemessen genau 238 px — buendig an der Innenkante, ohne jede Reserve. Ein
    // Zeichen mehr im Personennamen laeuft ueber; gleicher Inhaltstyp und
    // gleiche Behandlung wie die Template-Pille.
    expect(pill).toHaveClass('min-w-0')
    expect(pill).toHaveClass('truncate')
  })

  it('haelt das 40-px-Hit-Target aus AK 4 an den Filter-Chips und gibt es ab md frei', async () => {
    stubAgents([agent()])
    renderPage()

    const chip = await screen.findByRole('button', { name: /Alle/ })
    // Gemessen 32 px: `size="sm"` (h-9) plus `className="h-8"`, und `h-8`
    // gewinnt in `tailwind-merge`. Nach §11 (>= 32 px) noch zulaessig, nach
    // AK 4 dieses Issues zu niedrig.
    expect(chip).toHaveClass('min-h-10')
    expect(chip).toHaveClass('md:min-h-0')
  })

  it('haelt das AK-4-Hit-Target am Filter-Reset', async () => {
    stubAgents([agent()])
    renderPage()

    const chip = await screen.findByRole('button', { name: /Aktiv/ })
    chip.click()

    const reset = await screen.findByRole('button', { name: 'Filter zurücksetzen' })
    // Gemessen 32 px (`h-8 px-2`).
    expect(reset).toHaveClass('min-h-10')
    expect(reset).toHaveClass('md:min-h-0')
  })

  it('haelt das AK-4-Hit-Target am Einrichten-Link unvollstaendiger Agents', async () => {
    stubAgents([agent({ activatable: false, missing: ['persona'], persona_name: null })])
    renderPage()

    const setup = await screen.findByRole('link', { name: /Einrichten/ })
    // Gemessen 36 px (`size="sm"`, ohne Hoehen-Override).
    expect(setup).toHaveClass('min-h-10')
    expect(setup).toHaveClass('md:min-h-0')
  })

  it('laesst Suchfeld und Favoriten-Toggle unveraendert — gemessen erfuellt', async () => {
    stubAgents([agent()])
    renderPage()

    const search = await screen.findByLabelText('Suche')
    const favorite = await screen.findByTestId('favorite-toggle')
    // Suchfeld 40 x 238 px ueber die volle Breite, `favorite-toggle` 40 x 40 px
    // (`size="icon"`) — beide erfuellen AK 4 ohne Eingriff. Dieser Test haelt
    // die Nicht-Funde fest, damit sie nicht ohne Messung „mitgefixt" werden.
    expect(search.className).not.toMatch(/min-h-/)
    expect(favorite.className).not.toMatch(/min-h-/)
  })
})
