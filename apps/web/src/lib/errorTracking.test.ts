// Fehler-Tracking (Stabilitaet A3): ohne DSN kein Laden und kein Aufruf, mit
// DSN die PII-Linie aus dem Backend (kein Nutzer, keine Header/Cookies/Bodies,
// keine Query-Strings, maskierte Tokens/E-Mails, kein Replay, kein Tracing).
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { runInNewContext } from 'node:vm'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { RuntimeConfig } from '@/config'

const { sentryInit, captureReactException, moduleLoaded } = vi.hoisted(() => ({
  sentryInit: vi.fn(),
  captureReactException: vi.fn(),
  moduleLoaded: vi.fn(),
}))

vi.mock('@sentry/react', () => {
  moduleLoaded()
  return { init: sentryInit, captureReactException }
})

import {
  beforeBreadcrumb,
  beforeSend,
  buildOptions,
  type ErrorTrackingConfig,
  initErrorTracking,
  reportBoundaryError,
  resetErrorTrackingForTests,
  scrubText,
} from './errorTracking'

type ErrorEvent = import('@sentry/react').ErrorEvent
type Breadcrumb = import('@sentry/react').Breadcrumb

const OFF: ErrorTrackingConfig = { sentryDsn: '', sentryEnvironment: 'production', sentryRelease: '' }
const ON: ErrorTrackingConfig = {
  sentryDsn: 'https://public@tracker.example/1',
  sentryEnvironment: 'staging',
  sentryRelease: 'web@1.2.3',
}
const INFO = { componentStack: '\n    at Page' }

describe('initErrorTracking ohne DSN', () => {
  let fetchSpy: ReturnType<typeof vi.fn>
  let beaconSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    resetErrorTrackingForTests()
    vi.clearAllMocks()
    fetchSpy = vi.fn()
    beaconSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    vi.stubGlobal('navigator', { ...navigator, sendBeacon: beaconSpy })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('laedt das SDK nicht, initialisiert nichts und ruft kein Netz auf', async () => {
    await expect(initErrorTracking(OFF)).resolves.toBe(false)

    expect(moduleLoaded).not.toHaveBeenCalled()
    expect(sentryInit).not.toHaveBeenCalled()
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(beaconSpy).not.toHaveBeenCalled()
  })

  it('meldet Boundary-Fehler nicht und laedt dabei auch nichts nach', async () => {
    await initErrorTracking(OFF)

    reportBoundaryError(new Error('Boom'), INFO)
    await Promise.resolve()

    expect(moduleLoaded).not.toHaveBeenCalled()
    expect(captureReactException).not.toHaveBeenCalled()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('behandelt den Default aus config.ts (kein /config.js-Wert) als aus', async () => {
    await expect(initErrorTracking()).resolves.toBe(false)

    expect(sentryInit).not.toHaveBeenCalled()
  })
})

describe('initErrorTracking mit DSN', () => {
  beforeEach(() => {
    resetErrorTrackingForTests()
    vi.clearAllMocks()
  })

  it('initialisiert das SDK genau einmal mit DSN, Environment und Release', async () => {
    await expect(initErrorTracking(ON)).resolves.toBe(true)
    await initErrorTracking(ON)

    expect(sentryInit).toHaveBeenCalledTimes(1)
    const options = sentryInit.mock.calls[0][0] as ReturnType<typeof buildOptions>
    expect(options.dsn).toBe(ON.sentryDsn)
    expect(options.environment).toBe('staging')
    expect(options.release).toBe('web@1.2.3')
  })

  it('meldet Boundary-Fehler mit Komponenten-Stack', async () => {
    await initErrorTracking(ON)
    const error = new Error('Boom')

    reportBoundaryError(error, INFO)
    await vi.waitFor(() => expect(captureReactException).toHaveBeenCalledTimes(1))

    expect(captureReactException).toHaveBeenCalledWith(error, INFO)
  })
})

describe('buildOptions (PII-Linie)', () => {
  it('schaltet Tracing, Nutzerdaten, Header, Cookies, Bodies und Query-Strings ab', () => {
    const options = buildOptions(ON)

    expect(options.tracesSampleRate).toBe(0)
    expect(options.dataCollection).toMatchObject({
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
      stackFrameVariables: false,
    })
    expect(options.beforeSend).toBe(beforeSend)
    expect(options.beforeBreadcrumb).toBe(beforeBreadcrumb)
  })

  it('setzt kein Release, wenn keins konfiguriert ist', () => {
    expect(buildOptions({ ...ON, sentryRelease: '' })).not.toHaveProperty('release')
  })

  it('nimmt Session-Pings heraus und laesst kein Replay zu', () => {
    const options = buildOptions(ON)
    const defaults = ['Breadcrumbs', 'BrowserSession', 'GlobalHandlers', 'Replay'].map((name) => ({
      name,
    }))

    const integrations = options.integrations as (d: { name: string }[]) => { name: string }[]
    const kept = integrations(defaults).map((i) => i.name)

    expect(kept).toContain('GlobalHandlers')
    expect(kept).not.toContain('BrowserSession')
    // Replay ist nie in den Defaults; das Modul importiert es nicht.
    expect(Object.keys(options)).not.toContain('replaysSessionSampleRate')
    expect(Object.keys(options)).not.toContain('replaysOnErrorSampleRate')
  })
})

describe('Scrubbing', () => {
  it('maskiert Who2Be-Tokens, JWTs, Bearer-Werte, E-Mails und Query-Strings', () => {
    const jwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl'
    const text = `w2b_abc123 ${jwt} Bearer xyz.789 max@example.org /callback?code=geheim`

    const out = scrubText(text)

    expect(out).not.toContain('w2b_abc123')
    expect(out).not.toContain(jwt)
    expect(out).not.toContain('xyz.789')
    expect(out).not.toContain('max@example.org')
    expect(out).not.toContain('geheim')
    expect(out).toContain('/callback')
  })

  it('maskiert Fragment-Parameter wie Query-Strings, reine Anker bleiben', () => {
    const text =
      'Callback fehlgeschlagen: https://who2be.de/cb?lang=de#access_token=opaque123' +
      '&expires_in=3600&refresh_token=rt-geheim-456&token_type=bearer&type=recovery' +
      ' siehe /docs#abschnitt'

    const out = scrubText(text)

    expect(out).not.toContain('rt-geheim-456')
    expect(out).not.toContain('opaque123')
    expect(out).not.toContain('refresh_token')
    expect(out).toContain('https://who2be.de/cb')
    expect(out).toContain('/docs#abschnitt')
    expect(out).toBe('Callback fehlgeschlagen: https://who2be.de/cb[Filtered][Filtered] siehe /docs#abschnitt')
  })

  it('beforeSend entfernt Nutzer, Request-Daten und URL-Anhang und maskiert verschachtelt', () => {
    const event = {
      user: { id: 'u1', email: 'max@example.org', ip_address: '{{auto}}' },
      request: {
        url: 'https://who2be.de/app/agents?token=w2b_x#access_token=eyJa.eyJb.c',
        headers: { Authorization: 'Bearer abc' },
        cookies: { sb: 'x' },
        data: { password: 'p' },
        query_string: 'token=x',
      },
      exception: { values: [{ type: 'Error', value: 'Fehler fuer max@example.org mit w2b_secret' }] },
      extra: { nested: [{ hint: 'Bearer abc.def' }] },
    } as unknown as ErrorEvent

    const out = beforeSend(event)

    expect(out.user).toBeUndefined()
    expect(out.request).toEqual({ url: 'https://who2be.de/app/agents' })
    const serialized = JSON.stringify(out)
    expect(serialized).not.toContain('max@example.org')
    expect(serialized).not.toContain('w2b_secret')
    expect(serialized).not.toContain('abc.def')
  })

  it('beforeBreadcrumb kuerzt URLs und maskiert Konsolen-Zeilen', () => {
    const crumb = {
      category: 'fetch',
      message: 'Login fuer max@example.org',
      data: {
        url: 'https://who2be.de/auth/v1/token?grant_type=password',
        from: '/login?next=/app',
        to: '/app#access_token=eyJa.eyJb.c',
        'http.query': 'grant_type=password',
      },
    } as Breadcrumb

    const out = beforeBreadcrumb(crumb)

    expect(out.data).toEqual({
      url: 'https://who2be.de/auth/v1/token',
      from: '/login',
      to: '/app',
    })
    expect(out.message).not.toContain('max@example.org')
  })

  it('haengt sich an Zyklen nicht auf', () => {
    const cyclic: Record<string, unknown> = { text: 'max@example.org' }
    cyclic.self = cyclic
    const event = { extra: cyclic } as unknown as ErrorEvent

    expect(() => beforeSend(event)).not.toThrow()
    expect(cyclic.text).toBe('[Filtered]')
  })
})

describe('Runtime-Weg WHO2BE_SENTRY_* → /config.js', () => {
  function generate(env: Record<string, string>): RuntimeConfig {
    const dir = mkdtempSync(join(tmpdir(), 'who2be-sentry-'))
    try {
      const target = join(dir, 'config.js')
      execFileSync('sh', [resolve(__dirname, '../../docker/40-who2be-runtime-config.sh')], {
        env: { PATH: process.env.PATH ?? '/usr/bin:/bin', WHO2BE_RUNTIME_CONFIG_PATH: target, ...env },
        stdio: 'pipe',
      })
      const sandbox: { window: { __WHO2BE_CONFIG__?: RuntimeConfig } } = { window: {} }
      runInNewContext(readFileSync(target, 'utf8'), sandbox)
      return sandbox.window.__WHO2BE_CONFIG__ ?? {}
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  }

  it('schreibt ohne Env einen leeren DSN (Tracking aus) und Environment production', () => {
    const cfg = generate({})

    expect(cfg.sentryDsn).toBe('')
    expect(cfg.sentryEnvironment).toBe('production')
    expect(cfg.sentryRelease).toBe('')
  })

  it('uebernimmt DSN, Environment und Release aus der Env', () => {
    const cfg = generate({
      WHO2BE_SENTRY_DSN: 'https://public@tracker.example/1',
      WHO2BE_SENTRY_ENVIRONMENT: 'staging',
      WHO2BE_SENTRY_RELEASE: 'web@1.2.3',
    })

    expect(cfg).toMatchObject({
      sentryDsn: 'https://public@tracker.example/1',
      sentryEnvironment: 'staging',
      sentryRelease: 'web@1.2.3',
    })
  })
})
