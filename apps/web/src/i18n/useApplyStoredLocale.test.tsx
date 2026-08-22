import type { Session } from '@supabase/supabase-js'
import { renderHook, waitFor } from '@testing-library/react'
import { act } from 'react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SessionContext } from '@/auth/session-context'
import i18n, { resetLocaleChoiceState } from '@/i18n'
import { useApplyStoredLocale } from '@/i18n/useApplyStoredLocale'
import { useLocale } from '@/i18n/useLocale'

const updateUser = vi.fn().mockResolvedValue({ data: {}, error: null })
vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { updateUser: (...args: unknown[]) => updateUser(...args) } },
}))

const sessionOf = (id: string, preferred: string | undefined): Session =>
  ({
    access_token: 'tok',
    user: { id, user_metadata: { preferred_locale: preferred } },
  }) as unknown as Session

function withSession(session: Session | null) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <SessionContext.Provider
        value={{
          session,
          me: null,
          sessionLoaded: true,
          signIn: vi.fn(),
          signOut: vi.fn(),
          refreshMe: vi.fn(),
        }}
      >
        {children}
      </SessionContext.Provider>
    )
  }
}

beforeEach(() => {
  resetLocaleChoiceState()
})

afterEach(async () => {
  resetLocaleChoiceState()
  await act(async () => {
    await i18n.changeLanguage('de')
  })
})

describe('useApplyStoredLocale', () => {
  it('wendet die gespeicherte Praeferenz an, wenn der Nutzer noch nichts gewaehlt hat', async () => {
    renderHook(() => useApplyStoredLocale(), { wrapper: withSession(sessionOf('u1', 'en')) })

    await waitFor(() => {
      expect(i18n.resolvedLanguage).toBe('en')
    })
  })

  it('laesst eine Wahl bestehen, die VOR der Session getroffen wurde', async () => {
    // Regression: der Session-Bootstrap ist asynchron. Wer den Umschalter im
    // Header bedient, bevor `session.user` eintrifft, darf nicht anschliessend
    // vom gespeicherten Altwert ueberfahren werden.
    const { result } = renderHook(() => useLocale(), { wrapper: withSession(null) })
    await act(async () => {
      result.current.setLocale('en')
    })
    expect(i18n.resolvedLanguage).toBe('en')

    renderHook(() => useApplyStoredLocale(), { wrapper: withSession(sessionOf('u1', 'de')) })
    await act(async () => {
      await Promise.resolve()
    })

    expect(i18n.resolvedLanguage).toBe('en')
  })

  it('laesst eine Wahl bestehen, die NACH der Session getroffen wurde', async () => {
    // Zweiter Pfad zum selben Symptom: `supabase.auth.updateUser` behaelt den
    // access_token, `SessionProvider.apply()` dedupliziert darauf und verwirft
    // USER_UPDATED — der Session-State traegt also weiter die alte Praeferenz.
    const stale = sessionOf('u1', 'de')
    const { rerender } = renderHook(
      () => {
        useApplyStoredLocale()
        return useLocale()
      },
      { wrapper: withSession(stale) },
    )
    await waitFor(() => {
      expect(i18n.resolvedLanguage).toBe('de')
    })

    const { result } = renderHook(() => useLocale(), { wrapper: withSession(stale) })
    await act(async () => {
      result.current.setLocale('en')
    })

    rerender()
    await act(async () => {
      await Promise.resolve()
    })

    expect(i18n.resolvedLanguage).toBe('en')
  })

  it('wendet nach einem User-Wechsel die Praeferenz der neuen Person an', async () => {
    // Die Wahl der vorigen Person gilt fuer die neue nicht. Der Zustand liegt
    // im Modul, nicht im Hook-Ref — sonst haette der Remount von `AppLayout`
    // nach Logout/Login die Regel geleert.
    const { result } = renderHook(() => useLocale(), { wrapper: withSession(null) })
    await act(async () => {
      result.current.setLocale('de')
    })

    const first = renderHook(() => useApplyStoredLocale(), {
      wrapper: withSession(sessionOf('u1', 'de')),
    })
    await act(async () => {
      await Promise.resolve()
    })
    expect(i18n.resolvedLanguage).toBe('de')
    // Logout → AppLayout unmountet, neuer Login mountet den Hook frisch.
    first.unmount()

    const second = renderHook(() => useApplyStoredLocale(), {
      wrapper: withSession(sessionOf('u2', 'en')),
    })
    await waitFor(() => {
      expect(i18n.resolvedLanguage).toBe('en')
    })
    second.unmount()
  })
})
