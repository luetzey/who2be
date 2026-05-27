import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PersonaDetailPage } from './PersonaDetailPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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
      owner_id: 'o1',
      name: 'Coach',
      current_version: 1,
      content: { description: 'd', system_prompt: 's', traits: [] },
      created_at: '2026-05-24T11:00:00Z',
      updated_at: '2026-05-24T11:00:00Z',
    }
    const playbook = {
      id: 'pb1',
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
      'GET /v1/personas/p1': () => jsonResponse(persona),
      'GET /v1/personas/p1/versions': () => jsonResponse([version]),
      'GET /v1/personas/p1/playbooks': () => jsonResponse([playbook]),
      'GET /v1/playbooks': () => jsonResponse([playbook]),
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

    const { container } = renderInRoutes(<PersonaDetailPage />, { path: '/personas/:id', initialEntries: ['/personas/p1'] })

    await waitFor(() => {
      expect(screen.getByText('Aktuelle Version: 1')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByLabelText('Coaching')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
