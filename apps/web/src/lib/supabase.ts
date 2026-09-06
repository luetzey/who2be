import { createClient } from '@supabase/supabase-js'

import { config } from '../config'

import { hasRememberMarker, SESSION_STORAGE_KEY } from './remember-session'

// Delegierender Storage-Adapter (Issue #430/#471, ADR-0052 — loest ADR-0035 ab).
//
// Frueher fest auf `sessionStorage` (Tab-Lifetime, ADR-0035). Seit Issue #430
// opt-in: die Login-Checkbox "Angemeldet bleiben" setzt vor dem eigentlichen
// Login einen Marker (`lib/remember-session.ts`, geschrieben von
// `auth/SessionProvider.tsx::signIn`).
//
// Issue #471 — der Marker liegt im `localStorage` und ist damit
// tab-uebergreifend, `sessionStorage` dagegen ist strikt pro Tab. Ein
// Adapter, der den Marker bei JEDEM Zugriff live neu liest, lenkte damit
// auch schon laufende Tabs um, sobald EIN ANDERER Tab den Marker aenderte:
// Login in Tab B (mit Haken) hat den naechsten Storage-Zugriff in Tab A
// (ohne Haken) auf Session B umgeleitet — und umgekehrt loggte ein aus einem
// fremden Tab geloeschter Marker eine laufende "angemeldet bleiben"-Session
// still aus (leeres `sessionStorage`).
//
// Fix (Weg B, Owner-Entscheidung 2026-09-06, ADR-0052-Nachtrag): der Adapter
// entscheidet EINMAL PRO TAB, welches Backend er nutzt — das Ergebnis liegt
// im Modul-Zustand (`useLocalStorage` unten), nicht mehr live im Marker. Neu
// gesetzt wird dieser Wert ausschliesslich:
//   - beim Modul-Laden (Bootstrap dieses Tabs), und
//   - bei jedem Login IN DIESEM TAB (`syncStorageBackendForThisTab()`,
//     aufgerufen aus `SessionProvider::signIn` direkt nachdem dort der
//     Marker geschrieben/geloescht wurde — noch VOR `signInWithPassword`,
//     damit die gleich folgende Session direkt ins richtige Backend
//     geschrieben wird).
// Ein Marker-Wechsel aus einem FREMDEN Tab wirkt sich auf einen laufenden
// Tab damit nicht mehr aus; erst ein Reload uebernimmt den neuen Modus —
// gewolltes Verhalten, kein Mangel. Der Wert selbst entscheidet weiterhin
// zwischen genau zwei Backends:
//   - `true`  → `localStorage` (ueberlebt neuen Tab + Browser-Neustart, bis
//     zur absoluten Obergrenze `config.sessionMaxAgeHours` — die
//     Ablaufpruefung dafuer sitzt in `SessionProvider`, nicht hier).
//   - `false` (Default) → `sessionStorage`, exakt das ADR-0035-Verhalten
//     (Tab-Lifetime).
//
// Grund fuer EINEN Adapter statt zwei `createClient`-Instanzen:
// `createClient` bindet den Storage einmalig auf Modulebene (siehe unten) —
// ein zweiter Client waere eine zweite Quelle fuer denselben Zustand.
//
// Cross-Tab-Logout (AC 3, Issue #430) ist NICHT hier gebaut: `persistSession:
// true` + `storageKey` (unten) sind genau die zwei Vorbedingungen, unter
// denen `@supabase/auth-js` selbststaendig einen `BroadcastChannel` auf dem
// `storageKey` eroeffnet und `SIGNED_OUT` an alle gleichzeitig offenen Tabs
// meldet (`GoTrueClient.js`, `_notifyAllSubscribers` ueber `broadcastChannel`).
// Belegt in `supabase.test.ts`. Einschraenkung: ein `BroadcastChannel`
// erreicht nur GLEICHZEITIG offene Tabs — ein waehrend des Logouts
// geschlossener Tab merkt beim naechsten Oeffnen nichts davon; dort greift
// stattdessen die Ablaufpruefung in `SessionProvider`.
let useLocalStorage = hasRememberMarker()

/**
 * Aktualisiert den fuer DIESEN Tab eingefrorenen Storage-Modus (Issue #471).
 * Nur fuer einen Moduswechsel IN DIESEM TAB gedacht — `SessionProvider::signIn`
 * ruft das direkt nach dem Schreiben/Loeschen des Markers auf, damit ein
 * Login ohne Haken nach einem Login mit Haken (und umgekehrt) weiterhin
 * sofort wirkt. NIEMALS aus einem Storage-/`BroadcastChannel`-Event heraus
 * aufrufen, das aus einem FREMDEN Tab stammt — genau das war der Bug.
 */
export function syncStorageBackendForThisTab(): void {
  useLocalStorage = hasRememberMarker()
}

function backingStorage(): Storage {
  return useLocalStorage ? window.localStorage : window.sessionStorage
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
