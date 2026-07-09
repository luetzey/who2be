import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

// BlockNote-Insel mocken — sie ist in jsdom nicht mountfaehig (Muster aus
// PlaybookDetailPage.test.tsx). ThemeProvider kommt real ueber das AppLayout
// von renderInRoutes, daher kein theme-context-Mock noetig.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
  SuggestionMenuController: () => null,
  getDefaultReactSlashMenuItems: () => [],
  createReactInlineContentSpec: (_config: unknown, _impl: unknown) => ({
    config: _config,
    implementation: _impl,
  }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@blocknote/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@blocknote/core')>()
  return {
    ...actual,
    BlockNoteSchema: {
      create: vi.fn().mockReturnValue({
        blockSchema: {},
        inlineContentSchema: {
          placeholder: { type: 'placeholder', propSchema: {}, content: 'none' },
          text: { config: 'text' },
          link: { config: 'link' },
        },
        styleSchema: {},
      }),
    },
    defaultInlineContentSpecs: { text: {}, link: {} },
  }
})

import { PlaybookDetailPage } from './PlaybookDetailPage'

const WS_PREFIX = '/v1/workspaces/ws-1'

const adminMe: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'o1',
      name: 'Org',
      slug: 'org',
      kind: 'personal',
      workspaces: [{ id: 'ws-1', name: 'WS', slug: 'ws', role: 'admin' }],
    },
  ],
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybookDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout (voll bestueckte Detail-Sicht)', async () => {
    const content = {
      description: 'd',
      body: '',
      type: 'workflow',
      tags: ['coaching'],
      triggers: '"passwort vergessen", "reset link"',
    }
    const playbook = {
      id: 'pb1',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Coach',
      current_version: 2,
      current_status: 'draft',
      type: 'workflow',
      tags: ['coaching'],
      triggers: '"passwort vergessen", "reset link"',
      is_composite: true,
      content,
      created_at: '2026-05-24T12:00:00Z',
      updated_at: '2026-05-24T12:00:00Z',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname
        if (path === `${WS_PREFIX}/playbooks/pb1`) return jsonResponse(playbook)
        if (path === `${WS_PREFIX}/playbooks/pb1/versions`)
          return jsonResponse([
            { version: 1, status: 'active', content, created_by: 'o1', created_at: 't1' },
            { version: 2, status: 'draft', content, created_by: 'o1', created_at: 't2' },
          ])
        if (path === `${WS_PREFIX}/playbooks/pb1/resource_links`)
          return jsonResponse([
            {
              resource_id: 'r1',
              resource_name: 'Glossar',
              block_id: 'b1',
              position: 0,
              available: true,
              preview: 'Abschnitt A',
            },
          ])
        if (path === `${WS_PREFIX}/playbooks/pb1/usages`)
          return jsonResponse([{ persona_id: 'per1', persona_name: 'Coach Persona' }])
        if (path === `${WS_PREFIX}/playbooks/pb1/composes`)
          return jsonResponse([
            { id: 'c1', name: 'Schritt Eins', is_composite: false },
            { id: 'c2', name: 'Verschachtelt', is_composite: true },
          ])
        if (path === `${WS_PREFIX}/playbooks/pb1/composed_by`)
          return jsonResponse([{ id: 'p9', name: 'Eltern-Composite' }])
        if (path === `${WS_PREFIX}/feedback/playbook/pb1`)
          return jsonResponse({
            entity_type: 'playbook',
            entity_id: 'pb1',
            usage_count: 3,
            by_outcome: { applied: 2, error: 1 },
            by_signal: { helpful: 1, unclear: 1 },
            recent_notes: ['Schritt 2 unklar.'],
          })
        // AppShell-/Layout-Nebenfetches tolerant beantworten.
        return jsonResponse([])
      }),
    )

    const { container } = renderInRoutes(<PlaybookDetailPage />, {
      path: '/w/:workspaceId/playbooks/:id',
      initialEntries: ['/w/ws-1/playbooks/pb1'],
      me: adminMe,
    })

    await waitFor(() => {
      expect(screen.getByText('Coach')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('Coach Persona')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
