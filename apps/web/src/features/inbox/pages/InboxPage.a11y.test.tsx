import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { InboxCounts, Me, WorkspaceRole } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { InboxPage } from './InboxPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function meWithRole(role: WorkspaceRole): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Acme',
        slug: 'acme',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role }],
      },
    ],
  }
}

const now = new Date().toISOString()

function stub(counts: InboxCounts) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const json = (payload: unknown) => new Response(JSON.stringify(payload), { status: 200 })
      if (url.includes('/inbox/counts')) return json(counts)
      if (url.includes('/memories'))
        return json({
          items: [
            {
              id: 'm1',
              agent_id: 'a1',
              status: 'pending',
              fact: 'Rückgabefrist ist 30 Tage',
              context: null,
              category: 'fact',
              importance: 5,
              source: 'agent',
              triage_note: null,
              retrieval_count: 0,
              last_retrieved_at: null,
              created_at: now,
              updated_at: now,
            },
          ],
          next_cursor: null,
        })
      if (url.includes('/cases'))
        return json([
          {
            id: 'c1',
            workspace_id: 'ws-1',
            agent_id: 'a1',
            reporter_kind: 'human',
            reporter_user_id: 'u1',
            reporter_agent_id: null,
            situation: 's',
            behavior: 'Antwort auf Englisch statt Deutsch',
            impact: null,
            expected_behavior: 'e',
            severity: 'normal',
            signal: null,
            source_ref: null,
            source_feedback_id: null,
            source_memory_id: null,
            status: 'open',
            created_at: now,
          },
        ])
      if (url.includes('/agents')) return json([{ id: 'a1', name: 'Support-Assistent' }])
      if (url.includes('/personas'))
        return json([{ id: 'p1', name: 'Erstattung', current_version: 3, current_status: 'review' }])
      return json([])
    }),
  )
}

function renderPage(role: WorkspaceRole) {
  return renderInRoutes(<InboxPage />, {
    path: '/w/:workspaceId/inbox',
    initialEntries: ['/w/ws-1/inbox'],
    me: meWithRole(role),
  })
}

describe('InboxPage a11y', () => {
  it('a11y: befüllte Seite (admin) ohne axe-Verstöße, Abschnitte als section mit h2', async () => {
    stub({
      follow_ups_due: 1,
      memory_approval: 1,
      versions_review: 1,
      system_prompts_review: 0,
      cases_open: 1,
      patterns: 2,
      total: 4,
    })
    const { container } = renderPage('admin')
    await screen.findByRole('link', { name: 'Einordnen: Antwort auf Englisch statt Deutsch' })
    await screen.findByRole('link', { name: 'Erstattung Version 3 öffnen' })
    // Jeder Abschnitt ist eine benannte Region mit Zahl im Namen (Spec §8).
    expect(screen.getByRole('region', { name: 'Gedächtnis zur Freigabe, 1' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Zum Anschauen' })).toBeInTheDocument()
    expect(await axe(container)).toHaveNoViolations()
  })

  it('a11y: Leerzustand ohne axe-Verstöße', async () => {
    stub({
      follow_ups_due: 0,
      memory_approval: 0,
      versions_review: 0,
      system_prompts_review: 0,
      cases_open: 0,
      patterns: 0,
      total: 0,
    })
    const { container } = renderPage('editor')
    await screen.findByText('Alles erledigt')
    expect(await axe(container)).toHaveNoViolations()
  })
})
