import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { isStaleChunkError, reloadOnStaleChunk } from './stale-chunk'

describe('isStaleChunkError', () => {
  it('matcht die Safari-Meldung (Error-Instanz)', () => {
    expect(isStaleChunkError(new Error('Importing a module script failed'))).toBe(true)
  })

  it('matcht die Chrome-Meldung case-insensitiv', () => {
    expect(
      isStaleChunkError(new Error('FAILED TO FETCH DYNAMICALLY IMPORTED MODULE')),
    ).toBe(true)
  })

  it('matcht die Firefox-Meldung', () => {
    expect(isStaleChunkError(new Error('Error loading dynamically imported module'))).toBe(true)
  })

  it('matcht Event-aehnliche Objekte mit message-Feld', () => {
    expect(isStaleChunkError({ message: 'importing a module script failed' })).toBe(true)
  })

  it('matcht Event-aehnliche Objekte mit reason-Error (unhandledrejection)', () => {
    expect(
      isStaleChunkError({ reason: new Error('Failed to fetch dynamically imported module') }),
    ).toBe(true)
  })

  it('matcht Event-aehnliche Objekte mit reason-String', () => {
    expect(
      isStaleChunkError({ reason: 'error loading dynamically imported module' }),
    ).toBe(true)
  })

  it('liefert false fuer generische Fehler', () => {
    expect(isStaleChunkError(new Error('Network request failed'))).toBe(false)
  })

  it('liefert false fuer Nicht-Error-Werte', () => {
    expect(isStaleChunkError('Importing a module script failed')).toBe(false)
    expect(isStaleChunkError(null)).toBe(false)
    expect(isStaleChunkError(undefined)).toBe(false)
    expect(isStaleChunkError(42)).toBe(false)
    expect(isStaleChunkError({})).toBe(false)
  })
})

describe('reloadOnStaleChunk', () => {
  const GUARD_KEY = 'who2be:stale-chunk-reload'
  let reloadSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    window.sessionStorage.clear()
    reloadSpy = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('reloadet beim ersten Aufruf und setzt den Guard', () => {
    const result = reloadOnStaleChunk()

    expect(result).toBe(true)
    expect(reloadSpy).toHaveBeenCalledTimes(1)
    expect(window.sessionStorage.getItem(GUARD_KEY)).not.toBeNull()
  })

  it('reloadet beim zweiten Aufruf direkt danach NICHT (One-Shot-Guard)', () => {
    reloadOnStaleChunk()
    reloadSpy.mockClear()

    const result = reloadOnStaleChunk()

    expect(result).toBe(false)
    expect(reloadSpy).not.toHaveBeenCalled()
  })

  it('reloadet wieder, sobald das Zeitfenster abgelaufen ist', () => {
    const now = Date.now()
    vi.spyOn(Date, 'now').mockReturnValue(now)
    reloadOnStaleChunk()
    reloadSpy.mockClear()

    vi.spyOn(Date, 'now').mockReturnValue(now + 60_001)
    const result = reloadOnStaleChunk()

    expect(result).toBe(true)
    expect(reloadSpy).toHaveBeenCalledTimes(1)
  })

  it('loest keinen Reload aus, wenn sessionStorage wirft (z. B. Private Mode)', () => {
    const getItemSpy = vi
      .spyOn(Object.getPrototypeOf(window.sessionStorage) as Storage, 'getItem')
      .mockImplementation(() => {
        throw new Error('SecurityError')
      })

    const result = reloadOnStaleChunk()

    expect(result).toBe(false)
    expect(reloadSpy).not.toHaveBeenCalled()

    getItemSpy.mockRestore()
  })
})
