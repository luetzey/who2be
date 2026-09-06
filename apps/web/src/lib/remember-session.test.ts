import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  clearRememberMarker,
  hasRememberMarker,
  markRememberedLogin,
  purgeStoredSessionFrom,
  readRememberMarker,
  rememberedSessionExpired,
  restoreRememberMarker,
  SESSION_STORAGE_KEY,
} from './remember-session'

const REMEMBER_KEY = 'who2be.auth.remember'
const HOUR_MS = 60 * 60 * 1000
const MAX_AGE_MS = 12 * HOUR_MS

beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

describe('Marker-Lebenszyklus', () => {
  it('schreibt Marker und Zeitstempel in EINEM Wert', () => {
    markRememberedLogin(1_700_000_000_000)

    expect(window.localStorage.getItem(REMEMBER_KEY)).toBe('{"signedInAt":1700000000000}')
    expect(hasRememberMarker()).toBe(true)
  })

  it('meldet ohne Marker Tab-Lifetime', () => {
    expect(hasRememberMarker()).toBe(false)
    expect(readRememberMarker()).toBeNull()
  })

  it('stellt den vorherigen Marker exakt wieder her (Login-Fehlerpfad)', () => {
    markRememberedLogin(1_700_000_000_000)
    const previous = readRememberMarker()

    clearRememberMarker()
    expect(hasRememberMarker()).toBe(false)

    restoreRememberMarker(previous)
    expect(window.localStorage.getItem(REMEMBER_KEY)).toBe(previous)
  })

  it('restoreRememberMarker(null) loescht — ein vorher nicht gesetzter Marker bleibt ungesetzt', () => {
    markRememberedLogin()
    restoreRememberMarker(null)

    expect(hasRememberMarker()).toBe(false)
  })
})

describe('rememberedSessionExpired — fail-closed', () => {
  it('kennt ohne Marker keine Obergrenze (normale Tab-Session, AC 2)', () => {
    expect(rememberedSessionExpired(MAX_AGE_MS)).toBe(false)
  })

  it('haelt eine Session innerhalb der Obergrenze', () => {
    markRememberedLogin(Date.now() - 1 * HOUR_MS)

    expect(rememberedSessionExpired(MAX_AGE_MS)).toBe(false)
  })

  it('erkennt eine Session jenseits der Obergrenze', () => {
    markRememberedLogin(Date.now() - 13 * HOUR_MS)

    expect(rememberedSessionExpired(MAX_AGE_MS)).toBe(true)
  })

  // Der Kern des Security-Review-Befunds: frueher standen Marker und
  // Zeitstempel in zwei Keys, und ein fehlender/kaputter Zeitstempel bedeutete
  // "keine Obergrenze". Ein einziges `setItem` aus den DevTools genuegte, um
  // die Kappung dauerhaft abzuschalten. Jetzt gilt jeder Marker, aus dem kein
  // gueltiger Zeitstempel zu lesen ist, als abgelaufen.
  it.each([
    ['kein JSON', 'kaputt'],
    ['JSON ohne Zeitstempel', '{}'],
    ['Zeitstempel als String', '{"signedInAt":"morgen"}'],
    ['Zeitstempel NaN', '{"signedInAt":null}'],
    ['leerer Wert', ''],
  ])('behandelt einen Marker mit %s als abgelaufen', (_label, raw) => {
    window.localStorage.setItem(REMEMBER_KEY, raw)

    expect(rememberedSessionExpired(MAX_AGE_MS)).toBe(true)
    // …und der Adapter routet trotzdem nach localStorage, sonst koennte der
    // erzwungene Logout den Token dort nicht loeschen.
    expect(hasRememberMarker()).toBe(true)
  })
})

describe('purgeStoredSessionFrom', () => {
  it('raeumt gezielt das nicht mehr zustaendige Backend ab', () => {
    window.localStorage.setItem(SESSION_STORAGE_KEY, 'alt-remembered')
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, 'aktuell-tab')

    purgeStoredSessionFrom('local')

    expect(window.localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull()
    expect(window.sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe('aktuell-tab')
  })

  it('ist ohne liegengebliebene Session ein No-op', () => {
    expect(() => purgeStoredSessionFrom('session')).not.toThrow()
  })
})
