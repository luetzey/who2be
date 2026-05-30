import { createClient } from '@supabase/supabase-js'

import { config } from '../config'

// Tab-Lifetime-Session: GoTrue speichert Access-/Refresh-Token im
// `sessionStorage`, nicht im `localStorage`. Folgen:
//   - Token verschwindet, sobald der Tab geschlossen wird (keine
//     Disk-Persistierung, kein dauerhaftes Bearer-Token auf der Platte).
//   - Magic-Link/Hash-Detect funktioniert: `detectSessionInUrl` parsed den
//     Hash und legt die Session im Storage ab. Ohne Storage waere die
//     Session nach dem `getSession()`-Aufruf direkt wieder weg, der
//     Invitation-Flow wuerde auf `null` zurueckfallen.
const sessionStorageAdapter = {
  getItem: (key: string) => {
    if (typeof window === 'undefined') return null
    return window.sessionStorage.getItem(key)
  },
  setItem: (key: string, value: string) => {
    if (typeof window === 'undefined') return
    window.sessionStorage.setItem(key, value)
  },
  removeItem: (key: string) => {
    if (typeof window === 'undefined') return
    window.sessionStorage.removeItem(key)
  },
}

export const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: sessionStorageAdapter,
    storageKey: 'who2be.auth.session',
    // GoTrue-Invite-/Magic-Link liefert die Tokens im URL-Hash (implicit
    // flow). PKCE wuerde einen anderen Callback-Aufbau erwarten.
    flowType: 'implicit',
  },
})
