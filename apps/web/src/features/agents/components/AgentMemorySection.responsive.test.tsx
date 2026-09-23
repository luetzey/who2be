import type { Session } from '@supabase/supabase-js'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, MemoryRead } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { AgentMemorySection } from './AgentMemorySection'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'editor',
}))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

const WS_PREFIX = '/v1/workspaces/ws-1'

// Domaenentypische, pessimistische Fixtures: ein snake_case-Bezeichner ohne
// Trennstelle im Fakt und eine Artefakt-URL im `context`-Freitext (der aus dem
// Ingest stammt — eine URL darin ist der Regelfall, nicht der Ausreisser).
const LONG_FACT = 'Der Nutzer verweist regelmaessig auf kundenservice_eskalation_stufe_zwei_playbook'
const CONTEXT_WITH_URL =
  'Gesagt in der Sitzung zu https://who2be.example.com/w/ws-1/workarea/artifacts/7f3c1a2e-9b44-4f0e-8c21-5d6ab7e19f30#block-12'

function memory(overrides: Partial<MemoryRead> = {}): MemoryRead {
  return {
    id: 'm1',
    agent_id: 'a1',
    status: 'pending',
    fact: LONG_FACT,
    context: CONTEXT_WITH_URL,
    category: 'preference',
    importance: 8,
    source: 'agent',
    triage_note: null,
    retrieval_count: 12,
    last_retrieved_at: '2026-09-22T14:31:07.482913Z',
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    ...overrides,
  }
}

function stubMemories(memories: MemoryRead[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const { pathname } = new URL(String(input))
      if (pathname === `${WS_PREFIX}/agents/a1/memories`) {
        return new Response(JSON.stringify(memories), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error(`Unmocked GET ${pathname}`)
    }),
  )
}

function renderSection() {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1/agents/a1']}>
          <Routes>
            <Route path="/w/:workspaceId/agents/:id" element={<AgentMemorySection agentId="a1" />} />
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
// jsdom hat kein Layout, deshalb sind das hier Klassen-Vertraege. Die
// Layout-Aussagen sind in
// .claude/plan/2026-09-23-1420_570-w3-agents-haelfte-a-responsive-audit.md
// gegen das gebaute CSS in Chromium bei 320 px gerendert belegt.
describe('AgentMemorySection — Responsive (#570)', () => {
  it('gibt der Text-Spalte der Aktiv-Zeile min-w-0 und laesst den Fakt umbrechen', async () => {
    stubMemories([memory({ status: 'active' })])
    renderSection()

    const fact = await screen.findByText(LONG_FACT)
    // Gemessen bei 320 px: der `Stack` zog auf 298,9 px in einer 254 px breiten
    // Zeile (+45 px Ueberlauf, Inhalt zusaetzlich abgeschnitten). Muster aus
    // `AgentHierarchyView.tsx:59`/`:98` (Vorentscheidung 1 des Issues).
    expect(fact.parentElement).toHaveClass('min-w-0')
    // `min-w-0` allein loeste in der Nachmessung nur den Ueberlauf — der Fakt
    // blieb mit 299 px Inhalt in 204 px sichtbar abgeschnitten (§4.4 Punkt 5).
    // Erst `break-words` am Absatz behebt beides. `break-words` und nicht
    // `break-all`, weil der Fakt Fliesstext ist: gemessen bricht es den
    // trennstellenfreien Bezeichner am Ende trotzdem um und zerhackt
    // gewoehnliche Saetze nicht.
    expect(fact).toHaveClass('break-words')
  })

  it('gibt der Text-Spalte der Abgelehnt-Zeile min-w-0 und laesst Fakt und Notiz umbrechen', async () => {
    stubMemories([memory({ status: 'rejected', triage_note: 'unbelegt' })])
    renderSection()

    const toggle = await screen.findByRole('button', { name: /abgelehnt/i })
    toggle.click()

    const fact = await screen.findByText(LONG_FACT)
    // Gemessen 340,9 px in 254 px (+87 px) — der schwerere der beiden Stacks.
    expect(fact.parentElement).toHaveClass('min-w-0')
    expect(fact).toHaveClass('break-words')
    // Die Notiz kann eine URL tragen (Freitext des Triage-Menschen).
    expect(screen.getByText(/^Notiz:/)).toHaveClass('break-words')
  })

  it('laesst den Kontext-Absatz der Triage-Zeile umbrechen', async () => {
    stubMemories([memory()])
    renderSection()

    const context = await screen.findByText(/Gesagt in der Sitzung zu/)
    // Gemessen bei 320 px: 218 px Inhalt in 204 px sichtbar — die Artefakt-URL
    // wurde abgeschnitten. `break-words` und nicht `break-all`, weil der
    // Absatz Fliesstext ist: es bricht nur, wenn ein einzelnes Wort allein
    // nicht passt, und zerhackt gewoehnliche Saetze nicht.
    expect(context).toHaveClass('break-words')
  })

  it('haelt das 40-px-Hit-Target aus AK 4 an den Triage-Aktionen und gibt es ab md frei', async () => {
    stubMemories([memory()])
    renderSection()

    for (const name of ['Freigeben', 'Ablehnen']) {
      const button = await screen.findByRole('button', { name })
      expect(button).toHaveClass('min-h-10')
      expect(button).toHaveClass('md:min-h-0')
    }
  })

  it('haelt das AK-4-Hit-Target am Loeschen-Trigger, der alle drei Aufrufstellen deckt', async () => {
    stubMemories([memory({ status: 'active' })])
    renderSection()

    const del = await screen.findByRole('button', { name: 'Erinnerung löschen' })
    // Gemessen 32 px in der `ghost`-Variante (`size="sm"` + `h-8`, wobei `h-8`
    // in `tailwind-merge` gewinnt). Der Trigger ist geteilt: eine Aenderung
    // deckt Einzel-Loeschen, Abgelehnt-Loeschen und „Alle loeschen".
    expect(del).toHaveClass('min-h-10')
    expect(del).toHaveClass('md:min-h-0')
  })

  it('haelt das AK-4-Hit-Target an den Aktiv-Aktionen und der Abgelehnt-Disclosure', async () => {
    stubMemories([memory({ status: 'active' }), memory({ id: 'm2', status: 'rejected' })])
    renderSection()

    const edit = await screen.findByRole('button', { name: 'Bearbeiten' })
    expect(edit).toHaveClass('min-h-10')
    expect(edit).toHaveClass('md:min-h-0')

    const toggle = await screen.findByRole('button', { name: /abgelehnt/i })
    expect(toggle).toHaveClass('min-h-10')
    expect(toggle).toHaveClass('md:min-h-0')
  })

  it('haelt das AK-4-Hit-Target an den Aktionen des Inline-Edit', async () => {
    stubMemories([memory({ status: 'active' })])
    renderSection()

    const edit = await screen.findByRole('button', { name: 'Bearbeiten' })
    edit.click()

    await waitFor(() => expect(screen.getByLabelText('Wichtigkeit')).toBeInTheDocument())
    for (const name of ['Speichern', 'Abbrechen']) {
      expect(screen.getByRole('button', { name })).toHaveClass('min-h-10')
      expect(screen.getByRole('button', { name })).toHaveClass('md:min-h-0')
    }
  })

  it('laesst die feste Breite des Wichtigkeits-Selects unveraendert — gemessen kein Defekt', async () => {
    stubMemories([memory({ status: 'active' })])
    renderSection()

    const edit = await screen.findByRole('button', { name: 'Bearbeiten' })
    edit.click()

    const select = await screen.findByLabelText('Wichtigkeit')
    // Das Issue vermutet hier den harten Breiten-Defekt und AK 3 verlangt die
    // Pruefung; Vorentscheidung 2 bot `w-20 sm:w-24` bzw. `w-full sm:w-24` an.
    // Gemessen ist es KEIN Defekt: `tailwind-merge` loescht das `w-full` des
    // Primitives, das Feld misst 96 px in einer 204 px breiten Spalte und hat
    // 108 px Reserve bis zur Innenkante — bei 40 px Hoehe und einstelligem
    // Inhalt (Stufen 1–10). Weiche 1 aus #431 verbietet einen Prefix ohne
    // gemessenen Defekt, also bleibt `w-24` stehen. Dieser Test haelt den
    // Nicht-Fund fest, damit die Stelle nicht ohne Messung „mitgefixt" wird.
    expect(select).toHaveClass('w-24')
    expect(select.className).not.toMatch(/sm:w-|md:w-/)
  })
})
