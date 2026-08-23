import { afterEach, describe, expect, test, vi } from 'vitest'

import { resolveConfig } from './config'

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
