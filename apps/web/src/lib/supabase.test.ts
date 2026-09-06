import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// `createClient` gemockt, um die tatsaechlich uebergebenen `auth`-Optionen
// (inkl. des delegierenden Storage-Adapters) abzugreifen — ohne echten
// GoTrue-Netzwerkaufruf.
const { createClient } = vi.hoisted(() => ({
  createClient: vi.fn(() => ({ auth: {} })),
}))

vi.mock('@supabase/supabase-js', () => ({ createClient }))

// Modul-Singleton: `createClient` laeuft genau einmal beim ersten Import
// (ES-Module-Caching) — der abgegriffene Adapter ist danach in allen Tests
// derselbe, was hier gewuenscht ist (er soll das Remember-Flag bei jedem
// Zugriff live neu lesen, nicht beim Client-Aufbau binden).
import './supabase'

const REMEMBER_KEY = 'who2be.auth.remember'
const SESSION_KEY = 'who2be.auth.session'
const MARKER = JSON.stringify({ signedInAt: Date.now() })

interface CapturedAuthOptions {
  persistSession: boolean
  storageKey: string
  storage: {
    getItem: (key: string) => string | null
    setItem: (key: string, value: string) => void
    removeItem: (key: string) => void
  }
}

function capturedAuthOptions(): CapturedAuthOptions {
  const call = createClient.mock.calls[0] as unknown as [
    string,
    string,
    { auth: CapturedAuthOptions },
  ]
  return call[2].auth
}

beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

describe('supabase-Client — Cross-Tab-Logout-Vorbedingung (Weiche 6, Issue #430 AC 3)', () => {
  it('setzt persistSession + storageKey — genau die Bedingung, unter der auth-js selbststaendig einen BroadcastChannel eroeffnet', () => {
    // @supabase/auth-js/dist/main/GoTrueClient.js:
    //   if (isBrowser() && globalThis.BroadcastChannel && this.persistSession && this.storageKey) {
    //     this.broadcastChannel = new globalThis.BroadcastChannel(this.storageKey)
    //   }
    // Cross-Tab-Logout haengt komplett an dieser Bedingung — kein eigener
    // `storage`-Listener oder `BroadcastChannel` im who2be-Code noetig.
    const options = capturedAuthOptions()

    expect(options.persistSession).toBe(true)
    expect(typeof options.storageKey).toBe('string')
    expect(options.storageKey.length).toBeGreaterThan(0)
  })
})

describe('delegierender Storage-Adapter (Issue #430)', () => {
  it('routet ohne Remember-Flag nach sessionStorage — heutiges Tab-Lifetime-Verhalten', () => {
    const { storage } = capturedAuthOptions()

    storage.setItem(SESSION_KEY, 'tab-session')

    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('tab-session')
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(storage.getItem(SESSION_KEY)).toBe('tab-session')

    storage.removeItem(SESSION_KEY)
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('routet mit gesetztem Remember-Flag nach localStorage', () => {
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    const { storage } = capturedAuthOptions()

    storage.setItem(SESSION_KEY, 'remembered-session')

    expect(window.localStorage.getItem(SESSION_KEY)).toBe('remembered-session')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
    expect(storage.getItem(SESSION_KEY)).toBe('remembered-session')

    storage.removeItem(SESSION_KEY)
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('routet auch bei kaputtem Marker nach localStorage — sonst findet signOut() den Token nicht', () => {
    // Ein Marker, der sich nicht parsen laesst, heisst NICHT "keine
    // Persistenz": die Session liegt trotzdem im localStorage. Der Adapter
    // muss sie dort finden, damit `signOut()` sie loeschen kann; dass so eine
    // Session als abgelaufen gilt, entscheidet `rememberedSessionExpired`.
    window.localStorage.setItem(REMEMBER_KEY, 'kaputt')
    const { storage } = capturedAuthOptions()

    storage.setItem(SESSION_KEY, 'broken-marker-session')

    expect(window.localStorage.getItem(SESSION_KEY)).toBe('broken-marker-session')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('liest den Marker bei jedem Zugriff neu (kein einmaliges Binden beim Client-Aufbau)', () => {
    const { storage } = capturedAuthOptions()

    // Ohne Flag: sessionStorage.
    storage.setItem(SESSION_KEY, 'v1')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('v1')

    // Flag wird NACH dem Client-Aufbau gesetzt (Login mit Haken) — der
    // naechste Zugriff muss sofort nach localStorage routen.
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    storage.setItem(SESSION_KEY, 'v2')
    expect(window.localStorage.getItem(SESSION_KEY)).toBe('v2')
  })
})
