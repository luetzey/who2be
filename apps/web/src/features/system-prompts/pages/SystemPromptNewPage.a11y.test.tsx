import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { SystemPromptNewPage } from './SystemPromptNewPage'

// BlockNote-Insel mocken — ProseMirror kann in jsdom nicht mounten.
vi.mock('@/components/editor/system-prompt/SystemPromptEditor', () => ({
  SystemPromptEditor: () => <div data-testid="system-prompt-editor" />,
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SystemPromptNewPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    // Die New-Page laedt beim Mount nichts — Blanket-Stub reicht.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })),
    )

    const { container } = renderInRoutes(<SystemPromptNewPage />, {
      path: '/w/:workspaceId/system-prompts/new',
      initialEntries: ['/w/ws-1/system-prompts/new'],
    })

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Neues Template' })).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
