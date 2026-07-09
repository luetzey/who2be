import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SystemPromptTemplate, SystemPromptTemplateVersion } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { SystemPromptDetailPage } from './SystemPromptDetailPage'

// BlockNote-Insel mocken — ProseMirror kann in jsdom nicht mounten.
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

const WS_PREFIX = '/v1/workspaces/ws-1'

const templateFixture: SystemPromptTemplate = {
  id: 'sp1',
  workspace_id: 'ws-1',
  owner_id: 'o1',
  name: 'Support-Template',
  slug: 'support-template',
  current_version: 1,
  current_status: 'draft',
  has_pending_draft: false,
  content: { description: 'Beschreibung', body: '[]' },
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

const versionFixture: SystemPromptTemplateVersion = {
  version: 1,
  status: 'draft',
  content: templateFixture.content,
  created_by: 'o1',
  created_at: '2026-07-01T00:00:00Z',
}

describe('SystemPromptDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const handlers: Record<string, () => Response> = {
      [`GET ${WS_PREFIX}/system-prompts/sp1`]: () =>
        new Response(JSON.stringify(templateFixture), { status: 200 }),
      [`GET ${WS_PREFIX}/system-prompts/sp1/versions`]: () =>
        new Response(JSON.stringify([versionFixture]), { status: 200 }),
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

    const { container } = renderInRoutes(<SystemPromptDetailPage />, {
      path: '/w/:workspaceId/system-prompts/:id',
      initialEntries: ['/w/ws-1/system-prompts/sp1'],
    })

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Support-Template' }),
      ).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
