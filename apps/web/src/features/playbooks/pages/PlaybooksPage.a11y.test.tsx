import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { PlaybooksPage } from './PlaybooksPage'

// jsdom kennt keine Breakpoints — fuer das Filter-Sheet (unter `md`) wird
// `useIsMobile` gezielt umgeschaltet.
const viewport = vi.hoisted(() => ({ mobile: false }))
vi.mock('@/hooks/useMediaQuery', () => ({ useIsMobile: () => viewport.mobile }))

afterEach(() => {
  vi.unstubAllGlobals()
  viewport.mobile = false
})

const playbooks = [
  {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Coaching',
    current_version: 1,
    type: 'workflow',
    tags: ['coach'],
    triggers: null,
    content: {
      description: '',
      body: '',
      type: 'workflow',
      tags: ['coach'],
      triggers: null,
    },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  },
]

function renderPage() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()
      const body = /\/agents(\?|$)/.test(url) ? [] : playbooks
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
    }),
  )
  return renderInRoutes(<PlaybooksPage />, {
    path: '/w/:workspaceId/playbooks',
    initialEntries: ['/w/ws-1/playbooks'],
  })
}

describe('PlaybooksPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    const { container } = renderPage()

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit offenem Filter-Sheet (unter md)', async () => {
    viewport.mobile = true
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    const sheet = await screen.findByRole('dialog', { name: 'Filter' })

    const results = await axe(sheet)
    expect(results).toHaveNoViolations()
  })
})
