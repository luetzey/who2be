import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { updateUser, signOut, exportMyData, deleteAccount, notifySuccess, notifyError } =
  vi.hoisted(() => ({
    updateUser: vi.fn(),
    signOut: vi.fn(),
    exportMyData: vi.fn(),
    deleteAccount: vi.fn(),
    notifySuccess: vi.fn(),
    notifyError: vi.fn(),
  }))

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser, signOut } },
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: notifySuccess, error: notifyError, info: vi.fn() },
}))

// Track O: Export-/Konto-Löschen-Sektionen nutzen useApi — hier gestubbt, damit
// der Test ohne AuthTokenProvider auskommt.
vi.mock('@/api/useApi', () => ({
  useApi: () => ({ exportMyData, deleteAccount }),
}))

// ThemeToggle braucht den ThemeProvider-Context; fuer den AccountPage-Test
// irrelevant — durch einen Platzhalter ersetzt.
vi.mock('@/components/ui/theme-toggle', () => ({
  ThemeToggle: () => <div>theme</div>,
}))

// MfaSection spricht die GoTrue-`/factors`-API (supabase.auth.mfa) beim Mount
// an — hier irrelevant und durch einen Platzhalter ersetzt. Eigene Tests in
// MfaSection.test.tsx / MfaSection.a11y.test.tsx.
vi.mock('../components/MfaSection', () => ({
  MfaSection: () => <div>mfa</div>,
}))

// `hasPassword` ist mutabel, damit die Passwort-Setzen-Zweige (Magic-Link-User
// ohne Passwort) ohne zweite Mock-Factory testbar sind. Default: true.
const sessionState = vi.hoisted(() => ({ hasPassword: true }))

vi.mock('@/auth/session-context', () => ({
  useSession: () => ({
    session: {
      access_token: 't',
      user: { id: 'user-1', email: 'agent@who2be.dev', user_metadata: { display_name: 'Agent' } },
    },
    me: { user_id: 'user-1', has_password: sessionState.hasPassword },
  }),
}))

import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import i18n from '@/i18n'

import { AccountPage } from './AccountPage'

function renderPage() {
  return render(
    <AuthTokenProvider>
      <MemoryRouter initialEntries={['/w/abc/settings/account']}>
        <Routes>
          <Route path="/w/abc/settings/account" element={<AccountPage />} />
          <Route path="/login" element={<div>LOGIN</div>} />
        </Routes>
      </MemoryRouter>
    </AuthTokenProvider>,
  )
}

afterEach(() => {
  updateUser.mockReset()
  signOut.mockReset()
  exportMyData.mockReset()
  deleteAccount.mockReset()
  notifySuccess.mockReset()
  notifyError.mockReset()
  sessionState.hasPassword = true
})

describe('AccountPage', () => {
  it('aendert das Passwort ueber updateUser', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort aendern' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ password: 'neues-passwort-1' })
    })
  })

  it('aendert die E-Mail und loest eine Re-Confirm-Mail aus', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    fireEvent.change(screen.getByLabelText('E-Mail aendern'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'E-Mail aendern' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ email: 'neu@who2be.dev' })
    })
  })

  it('meldet ueberall ab und navigiert zum Login', async () => {
    signOut.mockResolvedValue({ error: null })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Überall abmelden' }))

    await waitFor(() => {
      expect(signOut).toHaveBeenCalledWith({ scope: 'global' })
    })
    await waitFor(() => {
      expect(screen.getByText('LOGIN')).toBeInTheDocument()
    })
  })

  it('exportiert die Daten ueber die API', async () => {
    exportMyData.mockResolvedValue({ user_id: 'user-1', organizations: [] })
    // jsdom kennt createObjectURL nicht — stubben.
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Daten exportieren' }))

    await waitFor(() => {
      expect(exportMyData).toHaveBeenCalledTimes(1)
    })
  })

  it('loescht das Konto erst nach E-Mail-Bestaetigung und meldet ab', async () => {
    deleteAccount.mockResolvedValue({ purge_after: '2026-07-03T00:00:00Z' })
    signOut.mockResolvedValue({ error: null })
    renderPage()

    // Dialog oeffnen.
    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))

    // Ohne passende E-Mail bleibt der Bestaetigen-Button deaktiviert.
    const confirmButton = screen.getByRole('button', { name: 'Konto endgültig löschen' })
    expect(confirmButton).toBeDisabled()

    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    expect(confirmButton).toBeEnabled()
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(signOut).toHaveBeenCalledWith({ scope: 'global' })
    })
  })
})

// ---------------------------------------------------------------------------
// Branch-Abdeckung (WP-1/TST-1): Validierungszweige, GoTrue-Fehlerpfade,
// Erfolgs-/Fehler-Toasts, Override-Token-Sektion und Sprachumschaltung.
// ---------------------------------------------------------------------------

describe('AccountPage — Profil-Formular', () => {
  it('validiert einen leeren Anzeigenamen, ohne GoTrue aufzurufen', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText('Anzeigename'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    expect(await screen.findByText('Bitte einen Namen eingeben.')).toBeInTheDocument()
    expect(updateUser).not.toHaveBeenCalled()
  })

  it('zeigt den GoTrue-Fehler beim Speichern des Anzeigenamens', async () => {
    updateUser.mockResolvedValue({ data: null, error: { message: 'metadata locked' } })
    renderPage()

    fireEvent.change(screen.getByLabelText('Anzeigename'), { target: { value: 'Neuer Name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    expect(await screen.findByText('metadata locked')).toBeInTheDocument()
    expect(notifySuccess).not.toHaveBeenCalled()
  })

  it('speichert den Anzeigenamen und zeigt den Erfolgs-Toast', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    fireEvent.change(screen.getByLabelText('Anzeigename'), { target: { value: 'Neuer Name' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ data: { display_name: 'Neuer Name' } })
    })
    expect(notifySuccess).toHaveBeenCalledWith('Anzeigename gespeichert.')
  })
})

describe('AccountPage — E-Mail-Formular', () => {
  it('lehnt die aktuelle E-Mail als neue Adresse ab', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText('E-Mail aendern'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'E-Mail aendern' }))

    expect(
      await screen.findByText('Das ist bereits deine aktuelle E-Mail-Adresse.'),
    ).toBeInTheDocument()
    expect(updateUser).not.toHaveBeenCalled()
  })

  it('validiert eine ungueltige E-Mail, ohne GoTrue aufzurufen', async () => {
    renderPage()

    const emailInput = screen.getByLabelText('E-Mail aendern')
    fireEvent.change(emailInput, { target: { value: 'nicht-gueltig' } })
    // Direktes submit-Event statt Button-Klick: jsdom blockiert den Klick
    // sonst per nativer Constraint-Validation (type="email"), bevor die
    // zod-Zweige von react-hook-form ueberhaupt laufen.
    const formEl = emailInput.closest('form')
    if (formEl === null) {
      throw new Error('E-Mail-Formular nicht gefunden')
    }
    fireEvent.submit(formEl)

    expect(await screen.findByText('Bitte gueltige E-Mail eingeben.')).toBeInTheDocument()
    expect(updateUser).not.toHaveBeenCalled()
  })

  it('zeigt den GoTrue-Fehler beim E-Mail-Wechsel', async () => {
    updateUser.mockResolvedValue({ data: null, error: { message: 'email taken' } })
    renderPage()

    fireEvent.change(screen.getByLabelText('E-Mail aendern'), {
      target: { value: 'neu@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'E-Mail aendern' }))

    expect(await screen.findByText('email taken')).toBeInTheDocument()
    expect(notifySuccess).not.toHaveBeenCalled()
  })
})

describe('AccountPage — Passwort-Formular', () => {
  it('validiert Mindestlaenge und fehlende Wiederholung', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText('Neues Passwort'), { target: { value: 'kurz' } })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort aendern' }))

    expect(await screen.findByText('Mindestens 8 Zeichen.')).toBeInTheDocument()
    expect(screen.getByText('Bitte wiederholen.')).toBeInTheDocument()
    expect(updateUser).not.toHaveBeenCalled()
  })

  it('validiert nicht uebereinstimmende Passwoerter', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'langgenug-eins' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'langgenug-zwei' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort aendern' }))

    expect(await screen.findByText('Passwoerter stimmen nicht ueberein.')).toBeInTheDocument()
    expect(updateUser).not.toHaveBeenCalled()
  })

  it('zeigt den GoTrue-Fehler beim Passwort-Wechsel', async () => {
    updateUser.mockResolvedValue({ data: null, error: { message: 'weak password' } })
    renderPage()

    fireEvent.change(screen.getByLabelText('Neues Passwort'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort aendern' }))

    expect(await screen.findByText('weak password')).toBeInTheDocument()
    expect(notifySuccess).not.toHaveBeenCalled()
  })

  it('zeigt den Setzen-Modus fuer Magic-Link-User ohne Passwort', async () => {
    sessionState.hasPassword = false
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    // Ohne bestehendes Passwort: andere Labels + Magic-Link-Hinweis.
    expect(screen.getByText(/per Magic-Link oder Social-Login angemeldet/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Passwort setzen'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
      target: { value: 'neues-passwort-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ password: 'neues-passwort-1' })
    })
    expect(notifySuccess).toHaveBeenCalledWith('Passwort gesetzt.')
  })
})

describe('AccountPage — Überall abmelden (Fehlerpfad)', () => {
  it('zeigt den Fehler und bleibt auf der Seite, wenn das globale Abmelden scheitert', async () => {
    signOut.mockResolvedValue({ error: { message: 'signout kaputt' } })
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Überall abmelden' }))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('signout kaputt')
    })
    expect(screen.queryByText('LOGIN')).not.toBeInTheDocument()
    // pending wird zurueckgesetzt — der Button ist wieder klickbar.
    expect(screen.getByRole('button', { name: 'Überall abmelden' })).toBeEnabled()
  })
})

describe('AccountPage — Datenexport (Fehlerpfade)', () => {
  it('meldet den Fehler mit Message, wenn der Export scheitert', async () => {
    exportMyData.mockRejectedValue(new Error('export kaputt'))
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Daten exportieren' }))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('export kaputt')
    })
    expect(notifySuccess).not.toHaveBeenCalled()
  })

  it('faellt bei Nicht-Error-Ursachen auf die generische Meldung zurueck', async () => {
    exportMyData.mockRejectedValue('kaputt')
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Daten exportieren' }))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Export fehlgeschlagen.')
    })
  })
})

describe('AccountPage — Konto löschen (Fehlerpfade)', () => {
  it('zeigt den Fehler und bleibt eingeloggt, wenn das Loeschen scheitert', async () => {
    deleteAccount.mockRejectedValue(new Error('loeschen verboten'))
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))
    // Case-insensitiver Vergleich inkl. Trim: abweichende Schreibweise genuegt.
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: '  AGENT@WHO2BE.DEV ' },
    })
    const confirmButton = screen.getByRole('button', { name: 'Konto endgültig löschen' })
    expect(confirmButton).toBeEnabled()
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('loeschen verboten')
    })
    expect(signOut).not.toHaveBeenCalled()
    expect(screen.queryByText('LOGIN')).not.toBeInTheDocument()
  })

  it('faellt bei Nicht-Error-Ursachen auf die generische Meldung zurueck', async () => {
    deleteAccount.mockRejectedValue('kaputt')
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Konto endgültig löschen' }))

    await waitFor(() => {
      expect(notifyError).toHaveBeenCalledWith('Löschen fehlgeschlagen.')
    })
  })

  it('setzt die E-Mail-Bestaetigung beim Schliessen des Dialogs zurueck', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))
    fireEvent.change(screen.getByLabelText('E-Mail'), {
      target: { value: 'agent@who2be.dev' },
    })
    expect(screen.getByRole('button', { name: 'Konto endgültig löschen' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'Konto endgültig löschen' }),
      ).not.toBeInTheDocument()
    })

    // Erneut oeffnen: das Feld ist leer, der Button wieder deaktiviert.
    fireEvent.click(screen.getByRole('button', { name: 'Konto löschen' }))
    expect(await screen.findByLabelText('E-Mail')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Konto endgültig löschen' })).toBeDisabled()
  })
})

describe('AccountPage — Override-Token', () => {
  it('aktiviert einen langen Token maskiert und entfernt ihn wieder', async () => {
    renderPage()

    expect(screen.getByText(/kein Override \(Supabase-JWT aktiv\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Override entfernen' })).toBeDisabled()

    fireEvent.change(screen.getByLabelText('w2b_-Token'), {
      target: { value: 'w2b_geheim_token' },
    })
    const activate = screen.getByRole('button', { name: 'Aktivieren' })
    expect(activate).toBeEnabled()
    fireEvent.click(activate)

    // Nur die letzten 6 Zeichen bleiben sichtbar; das Eingabefeld wird geleert.
    expect(await screen.findByText(/Override aktiv \(…_token\)/)).toBeInTheDocument()
    expect(screen.getByLabelText('w2b_-Token')).toHaveValue('')

    fireEvent.click(screen.getByRole('button', { name: 'Override entfernen' }))
    expect(await screen.findByText(/kein Override \(Supabase-JWT aktiv\)/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Override entfernen' })).toBeDisabled()
  })

  it('zeigt kurze Tokens ungekuerzt an', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText('w2b_-Token'), { target: { value: 'w2b_x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aktivieren' }))

    expect(await screen.findByText(/Override aktiv \(w2b_x\)/)).toBeInTheDocument()
  })

  it('ignoriert ein Submit mit leerem Input', () => {
    renderPage()

    const formEl = screen.getByLabelText('w2b_-Token').closest('form')
    if (formEl === null) {
      throw new Error('Override-Formular nicht gefunden')
    }
    fireEvent.submit(formEl)

    expect(screen.getByText(/kein Override \(Supabase-JWT aktiv\)/)).toBeInTheDocument()
  })
})

describe('AccountPage — Sprachumschaltung', () => {
  afterEach(async () => {
    // Zurueck auf Deutsch — nachfolgende Tests assertieren deutsche Strings.
    await i18n.changeLanguage('de')
  })

  it('schaltet die UI-Sprache um und persistiert die Praeferenz im Profil', async () => {
    updateUser.mockResolvedValue({ data: {}, error: null })
    renderPage()

    expect(screen.getByText('Sprache der Benutzeroberfläche.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Sprache'), { target: { value: 'en' } })

    expect(await screen.findByText('Interface language.')).toBeInTheDocument()
    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith({ data: { preferred_locale: 'en' } })
    })
  })

  it('schaltet auch um, wenn die Persistierung fehlschlaegt (best effort)', async () => {
    updateUser.mockRejectedValue(new Error('kein Login'))
    renderPage()

    fireEvent.change(screen.getByLabelText('Sprache'), { target: { value: 'en' } })

    expect(await screen.findByText('Interface language.')).toBeInTheDocument()
    expect(notifyError).not.toHaveBeenCalled()
  })
})
