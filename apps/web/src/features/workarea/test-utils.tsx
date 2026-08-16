import type { Session } from '@supabase/supabase-js'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import type { Agent, KbNode, Me, WaArtifact, WorkArea, WorkAreaGrant } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

// Geteiltes Test-Setup des Arbeitsbereich-Features: Fixtures + ein
// Render-Wrapper, der eine Page unter ihrer echten Route mountet (ohne
// AppLayout — das uebernimmt der a11y-Helfer `renderInRoutes`).

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

export function area(overrides: Partial<WorkArea> = {}): WorkArea {
  return {
    id: 'area-1',
    workspace_id: 'ws-1',
    scope: 'shared',
    owner_agent_id: null,
    name: 'Marktrecherche',
    retention_days: null,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

export function artifact(overrides: Partial<WaArtifact> = {}): WaArtifact {
  return {
    id: 'art-1',
    area_id: 'area-1',
    workspace_id: 'ws-1',
    type: 'doc',
    title: 'Preisliste 2026',
    rev: 2,
    occurred_at: '2026-08-05T09:30:00Z',
    occurred_precision: 'day',
    sensitivity: 'general',
    source_system: null,
    source_url: null,
    fetched_at: null,
    blob_sha256: null,
    content_ref: null,
    created_at: '2026-08-05T09:30:00Z',
    updated_at: '2026-08-05T09:30:00Z',
    updated_by: 'agent:a1',
    ...overrides,
  }
}

export function grant(overrides: Partial<WorkAreaGrant> = {}): WorkAreaGrant {
  return {
    area_id: 'area-1',
    agent_id: 'agent-1',
    level: 'read',
    created_at: '2026-08-05T09:30:00Z',
    ...overrides,
  }
}

export function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'agent-1',
    workspace_id: 'ws-1',
    owner_id: 'u1',
    name: 'Recherche-Agent',
    description: '',
    persona_id: null,
    system_prompt_template_id: null,
    status: 'enabled',
    tool_policy: {
      playbook_read: 'assigned',
      resource_read: 'assigned',
      agent_read: 'assigned',
      external_tool_read: 'all',
      persona_read: true,
      persona_write: false,
      playbook_write: false,
      resource_write: false,
      agent_write: false,
      system_prompt_write: false,
      external_tool_write: false,
      feedback_write: true,
      feedback_resolve: false,
      promote_retire: false,
      workarea_write: false,
      kb_write: false,
      kb_edge_write: false,
    },
    persona_active: false,
    activatable: false,
    missing: [],
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    ...overrides,
  }
}

export function kbNode(overrides: Partial<KbNode> = {}): KbNode {
  return {
    id: 'node-1',
    workspace_id: 'ws-1',
    tier: 'derived',
    content: 'Der Listenpreis stieg 2026 um 8 Prozent.',
    content_ref: null,
    source_ref: 'artifact:art-1#aaaaaaaa',
    source_ref_kind: 'artifact',
    ttl_expires_at: null,
    status: 'live',
    derivation_depth: 1,
    sensitivity: 'general',
    occurred_at: '2026-08-05T00:00:00Z',
    occurred_precision: 'day',
    created_by: 'agent:a1',
    created_at: '2026-08-05T09:30:00Z',
    updated_at: '2026-08-05T09:30:00Z',
    ...overrides,
  }
}

/**
 * Mockt `fetch` mit einer Pfad→Antwort-Zuordnung.
 *
 * Der Schluessel ist ein Teilstring des Pfads; die erste passende Regel
 * gewinnt, deshalb spezifischere Pfade zuerst eintragen. Ohne Treffer kommt
 * ein leeres Array — das haelt Nebenrouten (z. B. die Agenten-Liste fuer die
 * Namensaufloesung) aus dem Weg, ohne dass jeder Test sie kennen muss.
 */
export function stubFetch(routes: Array<[string, unknown]>, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const match = routes.find(([fragment]) => url.includes(fragment))
      return new Response(JSON.stringify(match !== undefined ? match[1] : []), {
        status: match !== undefined ? status : 200,
        headers: { 'content-type': 'application/json' },
      })
    }),
  )
}

export function renderAt(
  element: ReactElement,
  path: string,
  initialEntries: string[],
): RenderResult {
  return render(
    <SessionContext.Provider
      value={{
        session,
        me,
        sessionLoaded: true,
        signIn: vi.fn(),
        signOut: vi.fn(),
        refreshMe: vi.fn(),
      }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route path={path} element={element} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}
