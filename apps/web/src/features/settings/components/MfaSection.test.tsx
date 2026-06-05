import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { Factor } from '@supabase/supabase-js'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { listFactors, enroll, challengeAndVerify, unenroll, success } = vi.hoisted(() => ({
  listFactors: vi.fn(),
  enroll: vi.fn(),
  challengeAndVerify: vi.fn(),
  unenroll: vi.fn(),
  success: vi.fn(),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { mfa: { listFactors, enroll, challengeAndVerify, unenroll } } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success, error: vi.fn(), info: vi.fn() },
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

function listResult(factors: Factor[]) {
  return { data: { all: factors, totp: factors, phone: [] }, error: null }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('MfaSection', () => {
  it('zeigt die leere Liste, wenn kein Faktor existiert', async () => {
    listFactors.mockResolvedValue(listResult([]))
    render(<MfaSection />)

    await waitFor(() =>
      expect(screen.getByText('Noch kein Authenticator eingerichtet.')).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Authenticator hinzufügen' })).toBeInTheDocument()
  })

  it('listet verifizierte Faktoren mit Aktiv-Badge', async () => {
    listFactors.mockResolvedValue(listResult([verifiedFactor]))
    render(<MfaSection />)

    await waitFor(() => expect(screen.getByText('iPhone')).toBeInTheDocument())
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
  })

  it('blendet unverifizierte Rest-Faktoren aus', async () => {
    listFactors.mockResolvedValue(
      listResult([{ ...verifiedFactor, id: 'f2', status: 'unverified', friendly_name: 'Halb' }]),
    )
    render(<MfaSection />)

    await waitFor(() =>
      expect(screen.getByText('Noch kein Authenticator eingerichtet.')).toBeInTheDocument(),
    )
    expect(screen.queryByText('Halb')).not.toBeInTheDocument()
  })

  it('fuehrt den Enroll-Verify-Flow ueber die GoTrue-/factors-API', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({
      data: { id: 'new-factor', totp: { qr_code: '<svg/>', secret: 'ABCDEF', uri: 'otpauth://x' } },
      error: null,
    })
    challengeAndVerify.mockResolvedValue({ data: {}, error: null })
    render(<MfaSection />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Authenticator hinzufügen' })).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Authenticator hinzufügen' }))

    // Enroll wurde mit TOTP angestossen; Secret + QR erscheinen.
    await waitFor(() => expect(enroll).toHaveBeenCalledWith({ factorType: 'totp' }))
    await waitFor(() => expect(screen.getByText('ABCDEF')).toBeInTheDocument())
    expect(screen.getByAltText('QR-Code zum Einrichten des Authenticators')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('6-stelliger Code'), { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen' }))

    await waitFor(() =>
      expect(challengeAndVerify).toHaveBeenCalledWith({ factorId: 'new-factor', code: '123456' }),
    )
    expect(success).toHaveBeenCalledWith('Zwei-Faktor aktiviert.')
  })

  it('validiert einen nicht 6-stelligen Code, ohne GoTrue aufzurufen', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({
      data: { id: 'new-factor', totp: { qr_code: '<svg/>', secret: 'ABCDEF', uri: 'otpauth://x' } },
      error: null,
    })
    render(<MfaSection />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Authenticator hinzufügen' })).toBeInTheDocument(),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Authenticator hinzufügen' }))
    await waitFor(() => expect(screen.getByText('ABCDEF')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('6-stelliger Code'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen' }))

    await waitFor(() =>
      expect(screen.getByText('Bitte einen 6-stelligen Code eingeben.')).toBeInTheDocument(),
    )
    expect(challengeAndVerify).not.toHaveBeenCalled()
  })
})
