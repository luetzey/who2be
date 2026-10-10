import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PlaybooksPage } from './PlaybooksPage'

// jsdom kennt keine Breakpoints: ohne Mock (false) sieht der Test das
// Facetten-Raster der ListFilterBar, mit `viewport.mobile = true` das Sheet.
const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => viewport.mobile }))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function playbook(
  id: string,
  name: string,
  tags: string[],
  triggers: string | null,
  status: VersionStatus = 'active',
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name,
    current_version: 1,
    current_status: status,
    type: 'workflow',
    tags,
    triggers,
    content: { description: '', body: '', type: 'workflow', tags, triggers },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
    ...overrides,
  }
}

function renderWith(list: unknown[]) {
  // `/agents` (Agent-Facette) bekommt eine leere Liste, alles andere die
  // Playbooks — sonst landen Playbook-Objekte als Agent-Optionen im Select.
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      const body = /\/agents(\?|$)/.test(url) ? [] : list
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    }),
  )
  render(
    <SessionContext.Provider value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
      <AuthTokenProvider>
        <BrowserRouter>
          <PlaybooksPage />
        </BrowserRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  viewport.mobile = false
  // Filter-Zustand lebt in der URL (useSearchParams) — zwischen Tests
  // zuruecksetzen, sonst leakt ?tag/?status in den naechsten Render.
  window.history.pushState({}, '', '/')
})

describe('PlaybooksPage', () => {
  it('filtert client-seitig ueber das Tag-Select der Filterleiste und zeigt den Chip', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach', 'session'], 'how do i'),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
      expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    })

    // Kein Popover mehr: ab `md` stehen die Facetten direkt im Raster.
    fireEvent.change(screen.getByLabelText('Tag'), { target: { value: 'brain' } })

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    expect(window.location.search).toContain('tag=brain')

    // Aktive Facette als Chip „Tag: brain“; Entfernen hebt den Filter auf.
    const chips = screen.getByRole('list', { name: 'Aktive Filter' })
    fireEvent.click(within(chips).getByRole('button', { name: /Tag: brain/ }))
    expect(screen.getByText('Coaching')).toBeInTheDocument()
  })

  it('filtert ueber den Status-Chip „Braucht Aufmerksamkeit“', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null, 'active'),
      playbook('pb2', 'Brainstorming', ['brain'], null, 'review'),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Chip traegt Zaehler 1 (nur die Review-Version braucht Aufmerksamkeit).
    fireEvent.click(screen.getByRole('button', { name: /Braucht Aufmerksamkeit 1/ }))

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('zeigt Status-Chips nach der 0er-Regel: „Alle“ immer, 0er-Status nicht', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], null, 'active'),
      playbook('pb2', 'Brainstorming', [], null, 'active'),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    const group = screen.getByRole('group', { name: 'Nach Status filtern' })
    expect(within(group).getByRole('button', { name: 'Alle 2' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(within(group).getByRole('button', { name: 'Aktiv 2' })).toBeInTheDocument()
    expect(within(group).queryByRole('button', { name: /Entwurf/ })).not.toBeInTheDocument()
    expect(
      within(group).queryByRole('button', { name: /Braucht Aufmerksamkeit/ }),
    ).not.toBeInTheDocument()
  })

  it('filtert per Freitext nach Name und setzt per „Filter zurücksetzen“ zurueck', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    const search = screen.getByLabelText('Suche')
    expect(search).toHaveAttribute('placeholder', 'Nach Name oder Trigger suchen…')
    fireEvent.change(search, { target: { value: 'coach' } })

    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.queryByText('Brainstorming')).not.toBeInTheDocument()

    // Suche bekommt keinen Chip; „Filter zurücksetzen“ steht in der Leiste.
    expect(screen.queryByRole('list', { name: 'Aktive Filter' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Filter zurücksetzen' }))
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert per Freitext auch ueber Trigger', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], 'eskalation starten'),
      playbook('pb2', 'Brainstorming', [], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'eskal' } })

    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.queryByText('Brainstorming')).not.toBeInTheDocument()
  })

  it('zeigt Trigger als einzelne Pills, kappt bei 3 sichtbaren + „+N"', async () => {
    renderWith([playbook('pb1', 'Coaching', [], 'alpha, beta; gamma, delta, epsilon')])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Split an ',' UND ';' (WP-D1) — die ersten drei als Pills sichtbar.
    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
    expect(screen.getByText('gamma')).toBeInTheDocument()
    expect(screen.queryByText('delta')).not.toBeInTheDocument()
    expect(screen.queryByText('epsilon')).not.toBeInTheDocument()
    expect(screen.getByLabelText('2 weitere Trigger')).toHaveTextContent('+2')
  })

  it('zeigt sanften Status samt Version und „Entwurf offen"-Marker', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], null, 'active', {
        current_version: 3,
        has_pending_draft: true,
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    expect(screen.getByText(/Aktiv · v3/)).toBeInTheDocument()
    expect(screen.getByText('Entwurf offen')).toBeInTheDocument()
  })

  it('zeigt den Composite-Footer und klappt Sub-Playbooks als Links auf', async () => {
    renderWith([
      playbook('pb1', 'Composite-Flow', [], null, 'active', {
        is_composite: true,
        compose_children: [
          { id: 'c1', name: 'Schritt Eins' },
          { id: 'c2', name: 'Schritt Zwei' },
        ],
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Composite-Flow')).toBeInTheDocument()
    })

    // Zugeklappt: Zusammenfassung mit Zaehler + Kind-Namen, keine Links.
    const toggle = screen.getByRole('button', { name: /2 Sub-Playbooks/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: /Schritt Zwei/ })).not.toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const childLink = screen.getByRole('link', { name: /Schritt Zwei/ })
    expect(childLink).toHaveAttribute('href', expect.stringContaining('/playbooks/c2'))
    expect(screen.getByRole('link', { name: /Schritt Eins/ })).toBeInTheDocument()
  })

  it('zeigt den „Teil von"-Marker auf Kind-Zeilen (Rueckrichtung aus compose_children)', async () => {
    renderWith([
      playbook('pb1', 'Eskalation Level 2', [], null, 'active', {
        is_composite: true,
        compose_children: [{ id: 'pb2', name: 'Kunde begruessen' }],
      }),
      playbook('pb2', 'Kunde begruessen', [], null),
    ])

    // Der Kind-Name erscheint doppelt (eigene Zeile + Footer-Vorschau des
    // Composites) — direkt auf den Marker-Link warten.
    const marker = await screen.findByRole('link', {
      name: /Teil von Eskalation Level 2/,
    })
    expect(marker).toHaveAttribute('href', expect.stringContaining('/playbooks/pb1'))
  })

  it('gruppiert via ?group=composite mit Sektions-Headern und Zaehlern', async () => {
    window.history.pushState({}, '', '/?group=composite')
    renderWith([
      playbook('pb1', 'Composite-Flow', [], null, 'active', { is_composite: true }),
      playbook('pb2', 'Atomar A', [], null),
      playbook('pb3', 'Atomar B', [], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Composite-Flow')).toBeInTheDocument()
    })

    expect(screen.getByRole('heading', { name: /Composite\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Standalone\s?\(2\)/ })).toBeInTheDocument()
  })

  it('Gruppieren-Select der Filterleiste schaltet auf Typ-Gruppen um, ohne Chip', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], null),
      playbook('pb2', 'Brainstorming', [], null, 'active', {
        type: 'prompt',
        content: { description: '', body: '', type: 'prompt', tags: [], triggers: null },
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: /workflow/ })).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Gruppieren'), { target: { value: 'type' } })

    expect(screen.getByRole('heading', { name: /prompt\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /workflow\s?\(1\)/ })).toBeInTheDocument()
    // Beide Items bleiben sichtbar — Gruppierung filtert nicht und ist
    // Anzeige: kein Chip, kein „Filter zurücksetzen“.
    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Aktive Filter' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Filter zurücksetzen' })).not.toBeInTheDocument()
  })

  it('gruppiert via ?group=tag mit Sektions-Headern je Tag, Mehrfach-Tags in jeder Gruppe', async () => {
    window.history.pushState({}, '', '/?group=tag')
    renderWith([
      playbook('pb1', 'Coaching', ['coach', 'brain'], null),
      playbook('pb2', 'Brainstorming', ['brain'], null),
      playbook('pb3', 'Ohne Tag', [], null),
    ])

    await waitFor(() => {
      expect(screen.getAllByText('Coaching').length).toBeGreaterThan(0)
    })

    const brainHeading = screen.getByRole('heading', { name: /brain\s?\(2\)/ })
    expect(brainHeading).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /coach\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Ohne Tag\s?\(1\)/ })).toBeInTheDocument()
    // pb1 ('Coaching') traegt beide Tags und erscheint dadurch in beiden
    // Tag-Gruppen — beide Vorkommen bleiben sichtbar.
    expect(screen.getAllByText('Coaching')).toHaveLength(2)
  })

  it('zeigt Header-Count-Pill und Onboarding-Hero bei leerem Workspace', async () => {
    renderWith([])

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lege dein erstes Playbook an' }),
      ).toBeInTheDocument()
    })
    // Kein Count-Pill, keine Filterleiste im Onboarding-Zustand — dafuer
    // spiegelt der Hero den Header-CTA (zwei „Neues Playbook"-Links).
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Neues Playbook/ })).toHaveLength(2)
  })

  it('zeigt den gefilterten Leerzustand mit Suchbegriff und Reset', async () => {
    renderWith([playbook('pb1', 'Coaching', [], null)])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })
    expect(screen.getByLabelText('1 Playbook')).toHaveTextContent('1')

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'nix' } })

    expect(
      screen.getByRole('heading', { name: /Keine Treffer für „nix“/ }),
    ).toBeInTheDocument()
    // Zwei Wege zurueck: Leiste (ghost) und Leerzustand — beide setzen zurueck.
    const resets = screen.getAllByRole('button', { name: /Filter zurücksetzen/ })
    expect(resets).toHaveLength(2)
    fireEvent.click(resets[resets.length - 1])
    expect(screen.getByText('Coaching')).toBeInTheDocument()
  })

  it('legt unter md Tag, Typ, Sprache und Gruppieren ins Filter-Sheet', async () => {
    viewport.mobile = true
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Kein Raster unter md: die Selects stehen erst im Sheet.
    expect(screen.queryByLabelText('Tag')).not.toBeInTheDocument()
    const toggle = screen.getByRole('button', { name: 'Filter' })
    fireEvent.click(toggle)

    const sheet = await screen.findByRole('dialog', { name: 'Filter' })
    for (const label of ['Typ', 'Tag', 'Sprache', 'Gruppieren']) {
      expect(within(sheet).getByLabelText(label)).toBeInTheDocument()
    }
    fireEvent.change(within(sheet).getByLabelText('Tag'), { target: { value: 'brain' } })
    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(within(sheet).getByRole('button', { name: '1 Treffer zeigen' })).toBeInTheDocument()
  })
})
