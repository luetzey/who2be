import { afterEach, describe, expect, test, vi } from 'vitest'

import { resolveConfig, resolveLaunchMode, resolveSessionMaxAgeHours } from './config'

afterEach(() => {
  vi.unstubAllEnvs()
  delete window.__WHO2BE_CONFIG__
})

describe('resolveConfig — Aufloesungsreihenfolge', () => {
  test('Runtime-Config schlaegt die Build-Zeit-Env', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://gebacken.example.com')
    window.__WHO2BE_CONFIG__ = { apiBaseUrl: 'https://runtime.example.com' }

    expect(resolveConfig().apiBaseUrl).toBe('https://runtime.example.com')
  })

  test('leere Runtime-Werte gelten als „nicht gesetzt"', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://gebacken.example.com')
    window.__WHO2BE_CONFIG__ = { apiBaseUrl: '' }

    expect(resolveConfig().apiBaseUrl).toBe('https://gebacken.example.com')
  })

  test('ohne beides greift der Dev-Fallback (Vite-Dev-Server hat keinen Proxy)', () => {
    vi.stubEnv('VITE_API_BASE_URL', '')

    expect(resolveConfig().apiBaseUrl).toBe('http://localhost:8000')
  })

  test('im Production-Build ohne Env: Same-Origin', () => {
    vi.stubEnv('PROD', true)
    vi.stubEnv('VITE_API_BASE_URL', '')
    vi.stubEnv('VITE_SUPABASE_URL', '')

    const resolved = resolveConfig()

    expect(resolved.apiBaseUrl).toBe(window.location.origin)
    expect(resolved.supabaseUrl).toBe(window.location.origin)
  })
})

describe('resolveConfig — abgeleitete Werte', () => {
  test('MCP-URL wird aus der API-Basis abgeleitet (api. → mcp.)', () => {
    window.__WHO2BE_CONFIG__ = { apiBaseUrl: 'https://api.example.com' }

    expect(resolveConfig().mcpUrl).toBe('https://mcp.example.com/mcp')
  })

  test('expliziter Runtime-MCP-Endpoint gewinnt', () => {
    window.__WHO2BE_CONFIG__ = {
      apiBaseUrl: 'https://api.example.com',
      mcpUrl: 'http://127.0.0.1:8765/mcp',
    }

    expect(resolveConfig().mcpUrl).toBe('http://127.0.0.1:8765/mcp')
  })

  test('Same-Origin-API haengt /mcp an den Origin', () => {
    window.__WHO2BE_CONFIG__ = { apiBaseUrl: 'http://192.168.1.42:5173' }

    expect(resolveConfig().mcpUrl).toBe('http://192.168.1.42:5173/mcp')
  })

  test('Anon-Key faellt nie auf leer zurueck (supabase-js wuerde nicht initialisieren)', () => {
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '')

    expect(resolveConfig().supabaseAnonKey).not.toBe('')
  })

  test('signupDisabled kommt zur Laufzeit als Boolean', () => {
    window.__WHO2BE_CONFIG__ = { signupDisabled: true }

    expect(resolveConfig().signupDisabled).toBe(true)
  })
})

describe('resolveLaunchMode', () => {
  test('gueltige Werte werden 1:1 uebernommen', () => {
    expect(resolveLaunchMode('open')).toBe('open')
    expect(resolveLaunchMode('coming_soon')).toBe('coming_soon')
  })

  test('undefined/leer fallen ohne Warnung auf "open" zurueck', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(resolveLaunchMode(undefined)).toBe('open')
    expect(resolveLaunchMode('')).toBe('open')
    expect(warn).not.toHaveBeenCalled()

    warn.mockRestore()
  })

  test('unbekannte Werte fallen fail-open auf "open" zurueck und warnen', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(resolveLaunchMode('maintenance')).toBe('open')
    expect(warn).toHaveBeenCalledTimes(1)

    warn.mockRestore()
  })
})

describe('resolveConfig — launchMode/launchContact (Issue #429)', () => {
  test('Default ohne Runtime-Config: "open", kein Kontakt', () => {
    const resolved = resolveConfig()

    expect(resolved.launchMode).toBe('open')
    expect(resolved.launchContact).toBe('')
  })

  test('Runtime setzt launchMode und launchContact durch', () => {
    window.__WHO2BE_CONFIG__ = {
      launchMode: 'coming_soon',
      launchContact: 'hello@who2be.dev',
    }

    const resolved = resolveConfig()

    expect(resolved.launchMode).toBe('coming_soon')
    expect(resolved.launchContact).toBe('hello@who2be.dev')
  })

  test('coming_soon zieht signupDisabled nach, wenn die Runtime es nicht explizit setzt', () => {
    window.__WHO2BE_CONFIG__ = { launchMode: 'coming_soon' }

    expect(resolveConfig().signupDisabled).toBe(true)
  })

  test('ein explizites rt.signupDisabled gewinnt gegen einen abweichenden launchMode', () => {
    window.__WHO2BE_CONFIG__ = { launchMode: 'open', signupDisabled: true }

    expect(resolveConfig().signupDisabled).toBe(true)
  })

  test('Altschalter (VITE_WHO2BE_SIGNUP_DISABLED) wirkt weiterhin ohne Runtime-Config', () => {
    vi.stubEnv('VITE_WHO2BE_SIGNUP_DISABLED', 'true')

    const resolved = resolveConfig()

    expect(resolved.launchMode).toBe('open')
    expect(resolved.signupDisabled).toBe(true)
  })

  test('unbekannter Runtime-launchMode faellt auf "open" zurueck', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    window.__WHO2BE_CONFIG__ = { launchMode: 'wat' }

    expect(resolveConfig().launchMode).toBe('open')

    warn.mockRestore()
  })
})

describe('resolveSessionMaxAgeHours (Issue #430)', () => {
  test('gueltige Werte im Bereich 1-24 werden 1:1 uebernommen', () => {
    expect(resolveSessionMaxAgeHours(1)).toBe(1)
    expect(resolveSessionMaxAgeHours(2)).toBe(2)
    expect(resolveSessionMaxAgeHours(24)).toBe(24)
  })

  test('undefined faellt ohne Warnung auf den Default (12) zurueck', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(resolveSessionMaxAgeHours(undefined)).toBe(12)
    expect(warn).not.toHaveBeenCalled()

    warn.mockRestore()
  })

  test('Werte ausserhalb 1-24 fallen fail-closed auf den Default zurueck und warnen', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    expect(resolveSessionMaxAgeHours(0)).toBe(12)
    expect(resolveSessionMaxAgeHours(25)).toBe(12)
    expect(resolveSessionMaxAgeHours(-3)).toBe(12)
    expect(resolveSessionMaxAgeHours(Number.NaN)).toBe(12)
    expect(warn).toHaveBeenCalledTimes(4)

    warn.mockRestore()
  })

  test('resolveConfig liest sessionMaxAgeHours aus der Runtime-Config', () => {
    window.__WHO2BE_CONFIG__ = { sessionMaxAgeHours: 2 }

    expect(resolveConfig().sessionMaxAgeHours).toBe(2)
  })

  test('resolveConfig faellt ohne Runtime-Config auf den Default (12) zurueck', () => {
    expect(resolveConfig().sessionMaxAgeHours).toBe(12)
  })

  test('resolveConfig kappt einen zu hohen Runtime-Wert (z. B. > 24) auf den Default', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    window.__WHO2BE_CONFIG__ = { sessionMaxAgeHours: 999 }

    expect(resolveConfig().sessionMaxAgeHours).toBe(12)

    warn.mockRestore()
  })
})
