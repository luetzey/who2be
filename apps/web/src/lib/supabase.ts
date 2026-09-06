import { createClient } from '@supabase/supabase-js'

import { config } from '../config'

import { hasRememberMarker, SESSION_STORAGE_KEY } from './remember-session'

// Delegierender Storage-Adapter (Issue #430, ADR-0052 — loest ADR-0035 ab).
//
// Frueher fest auf `sessionStorage` (Tab-Lifetime, ADR-0035). Jetzt opt-in:
// die Login-Checkbox "Angemeldet bleiben" setzt vor dem eigentlichen Login
// einen Marker (`lib/remember-session.ts`, geschrieben von
// `auth/SessionProvider.tsx::signIn`). Dieser Adapter liest den Marker bei
// JEDEM Storage-Zugriff neu und routet entsprechend:
//   - Marker gesetzt  → `localStorage` (ueberlebt neuen Tab + Browser-
//     Neustart, bis zur absoluten Obergrenze `config.sessionMaxAgeHours` —
//     die Ablaufpruefung dafuer sitzt in `SessionProvider`, nicht hier).
//   - Marker NICHT gesetzt (Default) → `sessionStorage`, exakt das bisherige
//     Tab-Lifetime-Verhalten.
// Grund fuer EINEN Adapter statt zwei `createClient`-Instanzen:
// `createClient` bindet den Storage einmalig auf Modulebene (siehe unten) —
// ein zweiter Client waere eine zweite Quelle fuer denselben Zustand.
//
// Cross-Tab-Logout (AC 3) ist NICHT hier gebaut: `persistSession: true` +
// `storageKey` (unten) sind genau die zwei Vorbedingungen, unter denen
// `@supabase/auth-js` selbststaendig einen `BroadcastChannel` auf dem
// `storageKey` eroeffnet und `SIGNED_OUT` an alle gleichzeitig offenen Tabs
// meldet (`GoTrueClient.js`, `_notifyAllSubscribers` ueber `broadcastChannel`).
// Belegt in `supabase.test.ts`. Einschraenkung: ein `BroadcastChannel`
// erreicht nur GLEICHZEITIG offene Tabs — ein waehrend des Logouts
// geschlossener Tab merkt beim naechsten Oeffnen nichts davon; dort greift
// stattdessen die Ablaufpruefung in `SessionProvider`.
function backingStorage(): Storage {
  return hasRememberMarker() ? window.localStorage : window.sessionStorage
}

const delegatingStorageAdapter = {
  getItem: (key: string) => {
    if (typeof window === 'undefined') return null
    return backingStorage().getItem(key)
  },
  setItem: (key: string, value: string) => {
    if (typeof window === 'undefined') return
    backingStorage().setItem(key, value)
  },
  removeItem: (key: string) => {
    if (typeof window === 'undefined') return
    backingStorage().removeItem(key)
  },
}

export const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: delegatingStorageAdapter,
    storageKey: SESSION_STORAGE_KEY,
    // GoTrue-Invite-/Magic-Link liefert die Tokens im URL-Hash (implicit
    // flow). PKCE wuerde einen anderen Callback-Aufbau erwarten.
    flowType: 'implicit',
  },
})
