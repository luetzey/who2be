import type { Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

import type { Me } from '@/api/types'

export interface SessionValue {
  session: Session | null
  // Identity-/Memberships-Snapshot des Tokens — wird nach erfolgreichem
  // Login einmal via `GET /v1/me` resolved und im State gehalten.
  me: Me | null
  signIn: (email: string, password: string) => Promise<void>
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
