import { render, screen, waitFor } from '@testing-library/react'
import type { Factor } from '@supabase/supabase-js'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'

const { listFactors } = vi.hoisted(() => ({ listFactors: vi.fn() }))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { mfa: { listFactors, enroll: vi.fn(), challengeAndVerify: vi.fn(), unenroll: vi.fn() } } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

import { MfaSection } from './MfaSection'

const verifiedFactor: Factor = {
  id: 'factor-1',
  friendly_name: 'iPhone',
  factor_type: 'totp',
  status: 'verified',
  created_at: '2026-05-01T10:00:00Z',
  updated_at: '2026-05-01T10:00:00Z',
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('MfaSection (a11y)', () => {
  it('hat keine axe-Violations mit eingerichtetem Faktor', async () => {
    listFactors.mockResolvedValue({
      data: { all: [verifiedFactor], totp: [verifiedFactor], phone: [] },
      error: null,
    })

    const { container } = render(<MfaSection />)
    await waitFor(() => expect(screen.getByText('iPhone')).toBeInTheDocument())

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
