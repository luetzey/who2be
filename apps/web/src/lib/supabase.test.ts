import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// `createClient` gemockt, um die tatsaechlich uebergebenen `auth`-Optionen
// (inkl. des delegierenden Storage-Adapters) abzugreifen — ohne echten
// GoTrue-Netzwerkaufruf.
const { createClient } = vi.hoisted(() => ({
  createClient: vi.fn(() => ({ auth: {} })),
}))

vi.mock('@supabase/supabase-js', () => ({ createClient }))

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

interface SupabaseModule {
  syncStorageBackendForThisTab: () => void
}

function capturedAuthOptions(): CapturedAuthOptions {
  const call = createClient.mock.calls.at(-1) as unknown as [
    string,
    string,
    { auth: CapturedAuthOptions },
  ]
  return call[2].auth
}

/**
 * Importiert `./supabase` frisch (Modul-Cache geleert, Issue #471). Der
 * fuer den Tab eingefrorene Storage-Modus (`useLocalStorage` in
 * `lib/supabase.ts`) wird dabei genau einmal aus dem *aktuellen*
 * `localStorage`-Inhalt bestimmt — exakt wie beim echten Laden eines neuen
 * Tabs. Danach im selben Test gesetzte/geloeschte Marker aendern das
 * Ergebnis NICHT mehr automatisch, nur noch ein Aufruf von
 * `syncStorageBackendForThisTab()` (simuliert einen Login IN DIESEM Tab).
 */
async function importFreshSupabase(): Promise<{
  options: CapturedAuthOptions
  sync: () => void
}> {
  vi.resetModules()
  createClient.mockClear()
  const mod = (await import('./supabase')) as unknown as SupabaseModule
  return { options: capturedAuthOptions(), sync: mod.syncStorageBackendForThisTab }
}

beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
  vi.resetModules()
})

describe('supabase-Client — Cross-Tab-Logout-Vorbedingung (Weiche 6, Issue #430 AC 3)', () => {
  it('setzt persistSession + storageKey — genau die Bedingung, unter der auth-js selbststaendig einen BroadcastChannel eroeffnet', async () => {
    // @supabase/auth-js/dist/main/GoTrueClient.js:
    //   if (isBrowser() && globalThis.BroadcastChannel && this.persistSession && this.storageKey) {
    //     this.broadcastChannel = new globalThis.BroadcastChannel(this.storageKey)
    //   }
    // Cross-Tab-Logout haengt komplett an dieser Bedingung — kein eigener
    // `storage`-Listener oder `BroadcastChannel` im who2be-Code noetig.
    const { options } = await importFreshSupabase()

    expect(options.persistSession).toBe(true)
    expect(typeof options.storageKey).toBe('string')
    expect(options.storageKey.length).toBeGreaterThan(0)
  })
})

describe('delegierender Storage-Adapter (Issue #430) — Backend-Wahl beim Modul-Laden', () => {
  it('routet ohne Remember-Marker beim Laden nach sessionStorage — heutiges Tab-Lifetime-Verhalten', async () => {
    const { options } = await importFreshSupabase()
    const { storage } = options

    storage.setItem(SESSION_KEY, 'tab-session')

    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('tab-session')
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(storage.getItem(SESSION_KEY)).toBe('tab-session')

    storage.removeItem(SESSION_KEY)
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('routet mit beim Laden bereits gesetztem Remember-Marker nach localStorage', async () => {
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    const { options } = await importFreshSupabase()
    const { storage } = options

    storage.setItem(SESSION_KEY, 'remembered-session')

    expect(window.localStorage.getItem(SESSION_KEY)).toBe('remembered-session')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
    expect(storage.getItem(SESSION_KEY)).toBe('remembered-session')

    storage.removeItem(SESSION_KEY)
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('routet auch bei beim Laden bereits kaputtem Marker nach localStorage — sonst findet signOut() den Token nicht', async () => {
    // Ein Marker, der sich nicht parsen laesst, heisst NICHT "keine
    // Persistenz": die Session liegt trotzdem im localStorage. Der Adapter
    // muss sie dort finden, damit `signOut()` sie loeschen kann; dass so eine
    // Session als abgelaufen gilt, entscheidet `rememberedSessionExpired`.
    window.localStorage.setItem(REMEMBER_KEY, 'kaputt')
    const { options } = await importFreshSupabase()
    const { storage } = options

    storage.setItem(SESSION_KEY, 'broken-marker-session')

    expect(window.localStorage.getItem(SESSION_KEY)).toBe('broken-marker-session')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Issue #471: der Marker liegt im `localStorage` (tab-uebergreifend), aber
// `sessionStorage` ist strikt pro Tab. Ein Adapter, der den Marker bei JEDEM
// Zugriff live neu liest, lenkte damit auch schon laufende Tabs um, sobald
// EIN ANDERER Tab den Marker aenderte. Fix (Weg B): der Adapter entscheidet
// EINMAL PRO TAB, welches Backend er nutzt (Modul-Zustand statt Live-Read).
// ---------------------------------------------------------------------------
describe('Issue #471 — Storage-Backend wird EINMAL PRO TAB eingefroren, nicht live nachgelesen', () => {
  it('reproduziert den Bug: ein Marker-Wechsel in einem FREMDEN Tab lenkt einen bereits laufenden Tab nicht um (AC 1)', async () => {
    // Tab A boot: ohne Haken eingeloggt -> sessionStorage.
    const { options: tabA } = await importFreshSupabase()
    tabA.storage.setItem(SESSION_KEY, 'tab-a-session')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('tab-a-session')

    // Tab B (ein anderer, gleichzeitig offener Tab) loggt sich MIT Haken ein
    // und setzt dabei den globalen Marker — Tab A bekommt davon nur ueber den
    // gemeinsamen `localStorage` etwas mit, nie ueber einen eigenen Login.
    window.localStorage.setItem(REMEMBER_KEY, MARKER)

    // Naechster Storage-Zugriff in Tab A (z. B. Auto-Refresh-Tick,
    // `visibilitychange`) MUSS weiterhin Tab As eigenes Backend treffen.
    tabA.storage.setItem(SESSION_KEY, 'tab-a-session-2')

    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('tab-a-session-2')
    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(tabA.storage.getItem(SESSION_KEY)).toBe('tab-a-session-2')
  })

  it('Gegenfall: ein GELOESCHTER Marker loggt einen laufenden "angemeldet bleiben"-Tab nicht still aus (AC 2)', async () => {
    // Tab A boot: MIT Haken eingeloggt -> localStorage, Session liegt dort.
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    const { options: tabA } = await importFreshSupabase()
    tabA.storage.setItem(SESSION_KEY, 'remembered-session')
    expect(window.localStorage.getItem(SESSION_KEY)).toBe('remembered-session')

    // Marker verschwindet (z. B. "Ueberall abmelden" in einem anderen Tab).
    window.localStorage.removeItem(REMEMBER_KEY)

    // Tab A muss die Session weiterhin im localStorage finden — ein Read darf
    // nicht ploetzlich ins (leere) sessionStorage gehen und den Tab damit
    // still ausloggen.
    expect(tabA.storage.getItem(SESSION_KEY)).toBe('remembered-session')
    tabA.storage.setItem(SESSION_KEY, 'remembered-session-2')
    expect(window.localStorage.getItem(SESSION_KEY)).toBe('remembered-session-2')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })

  it('ein Moduswechsel IM SELBEN TAB wirkt weiterhin sofort, ueber die explizite Sync-Funktion (AC 3)', async () => {
    const { options, sync } = await importFreshSupabase()
    const { storage } = options

    // Start: kein Marker -> sessionStorage (heutiges Tab-Lifetime-Verhalten).
    storage.setItem(SESSION_KEY, 'v1')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('v1')

    // signIn(remember=true) IN DIESEM TAB: Marker setzen, dann synchronisieren
    // — exakt das, was `SessionProvider::signIn` jetzt tut.
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    sync()
    storage.setItem(SESSION_KEY, 'v2')
    expect(window.localStorage.getItem(SESSION_KEY)).toBe('v2')

    // Und zurueck: signIn(remember=false) IN DIESEM TAB.
    window.localStorage.removeItem(REMEMBER_KEY)
    sync()
    storage.setItem(SESSION_KEY, 'v3')
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe('v3')
  })

  it('signOut findet die Session weiterhin im richtigen Backend, auch wenn der Marker zwischenzeitlich schon geloescht ist (AC 4)', async () => {
    // Tab mit "angemeldet bleiben": Session liegt im localStorage.
    window.localStorage.setItem(REMEMBER_KEY, MARKER)
    const { options } = await importFreshSupabase()
    options.storage.setItem(SESSION_KEY, 'remembered-session')

    // `SessionProvider::signOut` loescht den Marker NACH `supabase.auth.signOut()`
    // (Reihenfolge bleibt bestehen) — der eingefrorene Wert macht den Adapter
    // aber unabhaengig davon robust: er hat die Session dort abgelegt und
    // findet + loescht sie dort, ganz gleich, was mit dem Marker
    // zwischenzeitlich passiert.
    window.localStorage.removeItem(REMEMBER_KEY)
    options.storage.removeItem(SESSION_KEY)

    expect(window.localStorage.getItem(SESSION_KEY)).toBeNull()
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull()
  })
})
