import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { SettingsTokensPage } from './SettingsTokensPage'

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SettingsTokensPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const tokens = [
      {
        id: 't1',
        name: 'CLI-Agent',
        created_at: '2026-05-24T10:00:00Z',
        last_used_at: null,
        revoked_at: null,
      },
    ]
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(tokens), { status: 200 })),
    )

    const { container } = renderInRoutes(<SettingsTokensPage />, { path: '/settings/tokens' })

    await waitFor(() => {
      expect(screen.getByText('CLI-Agent')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
