import { screen, waitFor } from '@testing-library/react'
import type { Factor, Session } from '@supabase/supabase-js'
import { describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

const { listFactors } = vi.hoisted(() => ({ listFactors: vi.fn() }))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      updateUser: vi.fn(async () => ({ data: {}, error: null })),
      signOut: vi.fn(async () => ({ error: null })),
      mfa: {
        listFactors,
        enroll: vi.fn(),
        challengeAndVerify: vi.fn(),
        unenroll: vi.fn(),
      },
    },
  },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

import { AccountPage } from './AccountPage'

const verifiedFactor: Factor = {
  id: 'factor-1',
  friendly_name: 'iPhone',
  factor_type: 'totp',
  status: 'verified',
  created_at: '2026-05-01T10:00:00Z',
  updated_at: '2026-05-01T10:00:00Z',
}

const session = {
  access_token: 'tok',
  user: {
    id: 'u1',
    email: 'agent@who2be.dev',
    user_metadata: { display_name: 'Agent' },
  },
} as unknown as Session

const me: Me = {
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
  has_password: true,
}

describe('AccountPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    listFactors.mockResolvedValue({
      data: { all: [verifiedFactor], totp: [verifiedFactor], phone: [] },
      error: null,
    })

    const { container } = renderInRoutes(<AccountPage />, {
      path: '/w/:workspaceId/settings/account',
      initialEntries: ['/w/ws-1/settings/account'],
      session,
      me,
    })

    // Warten, bis auch die asynchron geladene MFA-Sektion steht.
    await waitFor(() => {
      expect(screen.getByText('iPhone')).toBeInTheDocument()
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
