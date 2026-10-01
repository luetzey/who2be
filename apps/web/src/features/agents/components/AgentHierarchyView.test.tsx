import type { Session } from '@supabase/supabase-js'
import { act, fireEvent, render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_TOOL_POLICY,
  type Agent,
  type Me,
  type Persona,
  type Playbook,
  type SystemPromptTemplate,
} from '@/api/types'
import { SessionContext } from '@/auth/session-context'

import { AgentHierarchyView } from './AgentHierarchyView'

// Breakpoint steuerbar: jsdom kennt kein `matchMedia`; der Default `false`
// ist der Desktop-Pfad (alle Playbooks), `true` der Pfad unter `md`.
const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({
  useIsMobile: () => viewport.mobile,
}))

afterEach(() => {
  viewport.mobile = false
})

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

// AgentHierarchyView nutzt `useWorkspacePath` (Router-Param + Session) und
// `<Link>` — daher Session- und Router-Kontext bereitstellen.
function renderView(ui: ReactElement) {
  return render(
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <MemoryRouter initialEntries={['/w/ws-1/agents/agent-1']}>
        <Routes>
          <Route path="/w/:workspaceId/agents/:id" element={ui} />
        </Routes>
      </MemoryRouter>
    </SessionContext.Provider>,
  )
}

function mockAgent(): Agent {
  return {
    id: 'agent-1',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Coach Carla Bot',
    description: 'Coach Carla als Customer-Support-Agent',
    persona_id: 'p',
    system_prompt_template_id: 't',
    status: 'enabled',
    tool_policy: DEFAULT_TOOL_POLICY,
    persona_active: true,
    activatable: true,
    missing: [],
    created_at: '2026-05-30T10:00:00Z',
    updated_at: '2026-05-30T10:00:00Z',
  }
}

function mockPersona(): Persona {
  return {
    id: 'p',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Coach Carla',
    current_version: 3,
    content: {
      description: 'Senior-Coach',
      system_prompt: '',
      traits: [],
      tags: [],
    },
    created_at: 't',
    updated_at: 't',
  }
}

function mockTemplate(): SystemPromptTemplate {
  return {
    id: 't',
    workspace_id: 'ws',
    owner_id: 'u',
    name: 'Customer-Support-Agent',
    slug: 'customer-support-agent',
    current_version: 1,
    content: { description: '', body: 'Du bist {{ persona.name }}' },
    created_at: 't',
    updated_at: 't',
  }
}

function mockPlaybooks(): Playbook[] {
  return [
    {
      id: 'pb1',
      workspace_id: 'ws',
      owner_id: 'u',
      name: 'Reset-Mail',
      current_version: 2,
      type: 'prompt',
      tags: [],
      triggers: null,
      content: {
        description: '',
        body: '',
        type: 'prompt',
        tags: [],
        triggers: null,
      },
      created_at: 't',
      updated_at: 't',
    },
    {
      id: 'pb2',
      workspace_id: 'ws',
      owner_id: 'u',
      name: 'Eskalation',
      current_version: 1,
      type: 'prompt',
      tags: [],
      triggers: null,
      content: {
        description: '',
        body: '',
        type: 'prompt',
        tags: [],
        triggers: null,
      },
      created_at: 't',
      updated_at: 't',
    },
  ]
}

describe('AgentHierarchyView', () => {
  it('rendert Persona, System-Prompt und Playbook-Liste als Verweiszeilen', () => {
    renderView(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={mockPlaybooks()}
      />,
    )
    expect(screen.getByText('Zusammensetzung')).toBeInTheDocument()
    expect(screen.getByText('Coach Carla')).toBeInTheDocument()
    expect(screen.getByText('Customer-Support-Agent')).toBeInTheDocument()
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(2)
    expect(screen.getByText('Reset-Mail')).toBeInTheDocument()
    expect(screen.getByText('Eskalation')).toBeInTheDocument()
    // Persona-Verweis zeigt auf die Persona-Detailseite.
    expect(screen.getByRole('link', { name: 'Coach Carla' })).toHaveAttribute(
      'href',
      '/w/ws-1/personas/p',
    )
  })

  it('zeigt die Nicht-geladen-Zweige, wenn Persona und Template fehlen', () => {
    renderView(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={null}
        template={null}
        playbooks={[]}
      />,
    )
    expect(screen.getAllByText('— nicht geladen —')).toHaveLength(2)
  })

  it('zeigt "Keine Playbooks verknüpft." wenn die Liste leer ist', () => {
    renderView(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={[]}
      />,
    )
    expect(screen.getByText('Keine Playbooks verknüpft.')).toBeInTheDocument()
  })
})

// Responsive-Vertrag #570 (AK 4): die Playbook-Zeilen der Zusammensetzungs-
// Karte sind die primaeren Navigationsziele der Ansicht und halten unterhalb
// `md` 40 px Hit-Target. Die Zahl kommt aus AK 4 dieses Issues, nicht aus der
// Norm: `docs/frontend/design-language.md` §11 ist die einzige Quelle des
// Floors und setzt ihn auf >= 32 px — die gemessenen 32 px lagen also genau
// auf dem Floor, nicht darunter; 40 px ist dort die Praeferenz
// `size="default"`, die dieses Paket unterhalb `md` verbindlich macht.
//
// Gemessen am gebauten Stylesheet in Chromium bei 320 px: `px-2 py-1.5` bei
// `text-sm` ergibt 32 px Zeilenhoehe, `min-h-10` hebt sie auf 40 px, ab `md`
// faellt sie auf 32 px zurueck. Die Klassenfolge `min-h-10 md:min-h-0` ist
// woertlich die aus #568/#572 und der Schwesterkarte (Haelfte A) — eine
// zweite Variante desselben Musters waere Pattern Drift. `min-h-*` kollidiert
// in `tailwind-merge` nicht mit der Polsterung.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1600_570-w3-agents-haelfte-b-responsive-audit.md
// gerendert belegt.
describe('AgentHierarchyView — Responsive (#570)', () => {
  it('haelt an den Playbook-Zeilen den 40-px-Hit-Target aus AK 4 unterhalb md und gibt ihn ab md wieder frei', () => {
    renderView(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={mockPlaybooks()}
      />,
    )

    const rows = screen.getAllByTestId('agent-hierarchy-playbook')
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(row).toHaveClass('min-h-10')
      expect(row).toHaveClass('md:min-h-0')
    }
  })
})

function manyPlaybooks(count: number): Playbook[] {
  const [template] = mockPlaybooks()
  return Array.from({ length: count }, (_, index) => ({
    ...template,
    id: `pb-${index + 1}`,
    name: `Playbook ${index + 1}`,
  }))
}

function renderMany(count: number) {
  return renderView(
    <AgentHierarchyView
      agent={mockAgent()}
      persona={mockPersona()}
      template={mockTemplate()}
      playbooks={manyPlaybooks(count)}
    />,
  )
}

// Mobil-Spec P7, M6 (Namen): Vorher kuerzte `truncate` auch kurze Namen
// unnoetig. Die Namen sind Links zum Volltext, deshalb ist eine Begrenzung
// auf zwei Zeilen erlaubt (Spec M6.1) — mehr nicht. Klassen-Vertrag.
describe('AgentHierarchyView — Namen brechen um (Mobil-Spec M6)', () => {
  it('kuerzt Playbook-, Persona- und System-Prompt-Namen erst nach zwei Zeilen', () => {
    renderView(
      <AgentHierarchyView
        agent={mockAgent()}
        persona={mockPersona()}
        template={mockTemplate()}
        playbooks={mockPlaybooks()}
      />,
    )
    const names = [
      screen.getByText('Reset-Mail'),
      screen.getByRole('link', { name: 'Coach Carla' }),
      screen.getByRole('link', { name: 'Customer-Support-Agent' }),
    ]
    for (const name of names) {
      expect(name).toHaveClass('wrap-anywhere', 'line-clamp-2')
      expect(name).not.toHaveClass('truncate')
    }
  })
})

// PM-Zusatz zu P7 (Muster M9): Vor den Tabs stand die Karte mit allen
// 14 Playbooks (942 px bei 320). Unter `md` zuerst 4 im Seitenfluss plus
// „{{count}} weitere anzeigen“ (je 8); ab `md` unveraendert alle.
describe('AgentHierarchyView — Playbook-Liste unter md (Muster M9)', () => {
  it('zeigt unter md vier Playbooks und einen Knopf fuer die naechsten acht', () => {
    viewport.mobile = true
    renderMany(14)
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(4)
    expect(screen.getByRole('button', { name: '8 weitere anzeigen' })).toBeInTheDocument()
    // Die Liste nennt weiter die Gesamtzahl.
    expect(screen.getByRole('list', { name: '14 verknüpfte Playbooks' })).toBeInTheDocument()
  })

  it('laedt je acht nach, setzt den Fokus auf den ersten neuen Eintrag und meldet den Stand', () => {
    viewport.mobile = true
    renderMany(15)
    const live = document.querySelector('[aria-live="polite"]')
    expect(live).toHaveTextContent('')

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: '8 weitere anzeigen' }))
    })
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(12)
    expect(document.activeElement).toHaveTextContent('Playbook 5')
    expect(live).toHaveTextContent('12 von 15 angezeigt')

    act(() => {
      fireEvent.click(screen.getByRole('button', { name: '3 weitere anzeigen' }))
    })
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(15)
    expect(document.activeElement).toHaveTextContent('Playbook 13')
    expect(live).toHaveTextContent('15 von 15 angezeigt')
    expect(screen.queryByRole('button', { name: /weitere anzeigen/ })).not.toBeInTheDocument()
  })

  it('zeigt bei hoechstens vier Playbooks keinen Knopf', () => {
    viewport.mobile = true
    renderMany(4)
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(4)
    expect(screen.queryByRole('button', { name: /weitere anzeigen/ })).not.toBeInTheDocument()
  })

  it('zeigt ab md alle Playbooks ohne Knopf', () => {
    renderMany(14)
    expect(screen.getAllByTestId('agent-hierarchy-playbook')).toHaveLength(14)
    expect(screen.queryByRole('button', { name: /weitere anzeigen/ })).not.toBeInTheDocument()
  })
})
