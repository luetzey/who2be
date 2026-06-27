
import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PersonaDetailPage } from './PersonaDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Siehe PersonaDetailPage.test.tsx — BlockNote-Insel ist in jsdom nicht
// mountfaehig. `@/app/theme-context` wird hier NICHT gemockt, weil
// `renderInRoutes` den echten `ThemeProvider` mountet (AppLayout).
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
// Track F: pill-faehiger Profil-Editor — im a11y-Page-Test gestubt (das volle
// BlockNote-Custom-Schema mountet nicht in jsdom).
vi.mock('@/features/personas/components/PersonaProfileEditor', () => ({
  PersonaProfileEditor: () => <div data-testid="blocknote-view" />,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

describe('PersonaDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const persona = {
      id: 'p1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coach',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      created_at: '2026-05-24T11:00:00Z',
      updated_at: '2026-05-24T11:00:00Z',
    }
    const playbook = {
      id: 'pb1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coaching',
      current_version: 1,
      type: 'workflow',
      tags: [],
      triggers: null,
      content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
      created_at: 't',
      updated_at: 't',
    }
    const version = {
      version: 1,
      content: persona.content,
      created_by: 'o1',
      created_at: '2026-05-24T11:00:00Z',
    }

    const handlers: Record<string, () => Response> = {
      'GET /v1/workspaces/ws-1/personas/p1': () => jsonResponse(persona),
      'GET /v1/workspaces/ws-1/personas/p1/versions': () => jsonResponse([version]),
      'GET /v1/workspaces/ws-1/personas/p1/playbooks': () => jsonResponse([playbook]),
      'GET /v1/workspaces/ws-1/playbooks': () => jsonResponse([playbook]),
      // ADR-0038: Feedback-Panel laedt das Aggregat; leeres Summary → EmptyState
      // (kein ErrorAlert-Heading, das die heading-order brechen wuerde).
      'GET /v1/workspaces/ws-1/feedback/persona/p1': () =>
        jsonResponse({
          entity_type: 'persona',
          entity_id: 'p1',
          usage_count: 0,
          by_outcome: {},
          by_signal: {},
          recent_notes: [],
        }),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const method = init?.method ?? 'GET'
        const key = `${method} ${new URL(String(input)).pathname}`
        const handler = handlers[key]
        if (!handler) {
          throw new Error(`Unmocked ${key}`)
        }
        return handler()
      }),
    )

    const { container } = renderInRoutes(<PersonaDetailPage />, {
      path: '/w/:workspaceId/personas/:id',
      initialEntries: ['/w/ws-1/personas/p1'],
    })

    // Phase-3-Round-3: Header zeigt jetzt das Versions-Status-Format.
    await waitFor(() => {
      expect(screen.getByText(/Aktuelle Version: v1/)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByLabelText('Coaching')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
