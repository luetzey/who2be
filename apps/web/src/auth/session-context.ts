import type { Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

import type { Me } from '@/api/types'

export interface SessionValue {
  session: Session | null
  // `false`, solange der initiale Session-Bootstrap (getSession + me-Fetch)
  // noch laeuft. In dieser Phase bedeutet `session === null` nur "noch
  // unbekannt" — Auth-Gates duerfen dann NICHT auf /login redirecten, sonst
  // geht beim Reload die aktuelle URL verloren (Deep-Link → Dashboard-Bug).
  sessionLoaded: boolean
  // Identity-/Memberships-Snapshot des Tokens — wird nach erfolgreichem
  // Login einmal via `GET /v1/me` resolved und im State gehalten.
  me: Me | null
  // Passwort-Login. Liefert `{ mfaRequired: true }`, wenn ein verifizierter
  // zweiter Faktor eine Step-up-Challenge braucht (nextLevel 'aal2' > current).
  // In dem Fall wird die aal1-Session NICHT committed — die LoginPage fuehrt
  // die TOTP-Challenge durch, erst danach committet `apply()` die aal2-Session.
  // `remember` (Issue #430, ADR-0052): mit `true` ueberlebt die Session neuen
  // Tab + Browser-Neustart (localStorage) bis zur absoluten Obergrenze
  // (`config.sessionMaxAgeHours`); mit `false` das heutige Tab-Lifetime-
  // Verhalten (sessionStorage).
  // `captchaToken` (Issue #539 / Folgebefund): GoTrue prueft das Captcha auch
  // am Passwort-Login (`/token` mit `grant_type=password`, middleware.go:190-196
  // nimmt nur die anderen Grant-Types aus). Weggelassen bleibt der Aufruf
  // unveraendert — der Parameter ist optional, nicht `undefined`-gesetzt.
  signIn: (
    email: string,
    password: string,
    remember: boolean,
    captchaToken?: string,
  ) => Promise<{ mfaRequired: boolean }>
  signOut: () => Promise<void>
  // Expliziter Re-Fetch von `/v1/me` — wird von `DefaultWorkspaceRedirect`
  // genutzt, wenn der Lazy-Seed noch nicht abgeschlossen war (Fallback).
  refreshMe: () => Promise<void>
}

export const SessionContext = createContext<SessionValue | null>(null)

export function useSession(): SessionValue {
  const value = useContext(SessionContext)
  if (value === null) {
    throw new Error('useSession muss innerhalb von SessionProvider verwendet werden.')
  }
  return value
}
