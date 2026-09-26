import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

// ---------------------------------------------------------------------------
// Branch-Abdeckung (WP-1/TST-1): Fehlerpfade des Enroll-/Verify-/Unenroll-
// Flows und der Abbruch-Cleanup. MfaSection ist die MFA-Enrollment-Sektion
// der AccountPage (dort als Platzhalter gemockt).
// ---------------------------------------------------------------------------

describe('MfaSection — Fehlerpfade', () => {
  it('zeigt den Ladefehler, wenn die Faktorenliste nicht geladen werden kann', async () => {
    listFactors.mockResolvedValue({ data: null, error: { message: 'factors down' } })
    render(<MfaSection />)

    expect(await screen.findByText('factors down')).toBeInTheDocument()
  })

  it('zeigt die GoTrue-Meldung, wenn das Enrollment nicht startet', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({ data: null, error: { message: 'enroll kaputt' } })
    render(<MfaSection />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Authenticator hinzufügen' }),
    )

    expect(await screen.findByText('enroll kaputt')).toBeInTheDocument()
    // Ohne Faktor-Daten erscheint kein QR-Code/Verify-Formular.
    expect(screen.queryByLabelText('6-stelliger Code')).not.toBeInTheDocument()
  })

  it('faellt auf die generische Enroll-Meldung zurueck, wenn Daten fehlen', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({ data: null, error: null })
    render(<MfaSection />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Authenticator hinzufügen' }),
    )

    expect(
      await screen.findByText('Einrichtung konnte nicht gestartet werden.'),
    ).toBeInTheDocument()
  })

  it('zeigt den Verify-Fehler im Dialog, ohne den Erfolgs-Toast auszuloesen', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({
      data: { id: 'new-factor', totp: { qr_code: '<svg/>', secret: 'ABCDEF', uri: 'otpauth://x' } },
      error: null,
    })
    challengeAndVerify.mockResolvedValue({ data: null, error: { message: 'falscher Code' } })
    render(<MfaSection />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Authenticator hinzufügen' }),
    )
    await waitFor(() => expect(screen.getByText('ABCDEF')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('6-stelliger Code'), { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen' }))

    expect(await screen.findByText('falscher Code')).toBeInTheDocument()
    expect(success).not.toHaveBeenCalled()
    // Dialog bleibt offen fuer einen erneuten Versuch.
    expect(screen.getByLabelText('6-stelliger Code')).toBeInTheDocument()
  })

  it('raeumt einen abgebrochenen Enroll per Unenroll wieder auf', async () => {
    listFactors.mockResolvedValue(listResult([]))
    enroll.mockResolvedValue({
      data: { id: 'new-factor', totp: { qr_code: '<svg/>', secret: 'ABCDEF', uri: 'otpauth://x' } },
      error: null,
    })
    unenroll.mockResolvedValue({ data: {}, error: null })
    render(<MfaSection />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Authenticator hinzufügen' }),
    )
    await waitFor(() => expect(screen.getByText('ABCDEF')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))

    await waitFor(() => {
      expect(unenroll).toHaveBeenCalledWith({ factorId: 'new-factor' })
    })
  })

  it('entfernt einen verifizierten Faktor und aktualisiert die Liste', async () => {
    listFactors
      .mockResolvedValueOnce(listResult([verifiedFactor]))
      .mockResolvedValue(listResult([]))
    unenroll.mockResolvedValue({ data: {}, error: null })
    render(<MfaSection />)

    await waitFor(() => expect(screen.getByText('iPhone')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Entfernen' }))

    // Bestaetigen-Button lebt im Dialog-Portal; der Listen-Button heisst gleich.
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

    await waitFor(() => {
      expect(unenroll).toHaveBeenCalledWith({ factorId: 'factor-1' })
    })
    expect(success).toHaveBeenCalledWith('Faktor entfernt.')
    await waitFor(() =>
      expect(screen.getByText('Noch kein Authenticator eingerichtet.')).toBeInTheDocument(),
    )
  })

  it('zeigt den Fehler im Entfernen-Dialog, wenn Unenroll scheitert', async () => {
    listFactors.mockResolvedValue(listResult([verifiedFactor]))
    unenroll.mockResolvedValue({ data: null, error: { message: 'nicht erlaubt' } })
    render(<MfaSection />)

    await waitFor(() => expect(screen.getByText('iPhone')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Entfernen' }))

    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Entfernen' }))

    expect(await within(dialog).findByText('nicht erlaubt')).toBeInTheDocument()
    expect(success).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Responsive-Vertrag #568 (§4.4 Punkt 5): die Faktor-Zeile traegt
// `justify-between` ohne `flex-wrap`. Gemessen drueckt der Entfernen-Button
// (87 px) den Faktornamen bei 320 px auf 30 px Breite bei 187 px Inhalt —
// `truncate` greift, rettet aber nichts, sichtbar bleiben zwei Zeichen.
// `flex-wrap` an der Zeile plus `basis-full md:basis-auto` an der Textspalte
// gibt ihr unterhalb `md` eine eigene Zeile (gemessen 30 -> 129 px), ab `md`
// bleibt die kompakte einzeilige Fassung. jsdom hat kein Layout — die
// Layout-Aussage steht gerendert in
// .claude/plan/2026-09-23-0830_568-w3-settings-responsive-audit.md.
// ---------------------------------------------------------------------------

describe('MfaSection — Responsive (#568)', () => {
  it('laesst die Faktor-Zeile unterhalb md umbrechen, statt den Namen zu zerquetschen', async () => {
    listFactors.mockResolvedValue(listResult([verifiedFactor]))
    render(<MfaSection />)

    const name = await screen.findByText('iPhone')
    const textColumn = name.parentElement
    const row = textColumn?.parentElement

    expect(row?.tagName).toBe('LI')
    expect(row?.className.split(/\s+/)).toContain('flex-wrap')
    expect(textColumn?.className.split(/\s+/)).toContain('basis-full')
    expect(textColumn?.className.split(/\s+/)).toContain('md:basis-auto')
    // min-w-0 bleibt — ohne es greift `truncate` am Namen nicht.
    expect(textColumn?.className.split(/\s+/)).toContain('min-w-0')
  })

  it('haelt das Status-Badge von der Schrumpfung frei', async () => {
    listFactors.mockResolvedValue(listResult([verifiedFactor]))
    render(<MfaSection />)

    const badge = await screen.findByText('Aktiv')
    expect(badge.className.split(/\s+/)).toContain('shrink-0')
  })
})
