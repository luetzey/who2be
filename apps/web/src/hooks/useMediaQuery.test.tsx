import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useIsMobile, useMediaQuery } from './useMediaQuery'

interface MediaState {
  matches: boolean
  listeners: Array<(event: MediaQueryListEvent) => void>
}

function installMatchMedia(initial: boolean): MediaState {
  const state: MediaState = { matches: initial, listeners: [] }
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      get matches() {
        return state.matches
      },
      media: '',
      onchange: null,
      addEventListener: (_event: string, cb: (event: MediaQueryListEvent) => void) => {
        state.listeners.push(cb)
      },
      removeEventListener: (_event: string, cb: (event: MediaQueryListEvent) => void) => {
        state.listeners = state.listeners.filter((listener) => listener !== cb)
      },
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
  return state
}

function uninstallMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: undefined,
  })
}

describe('useMediaQuery', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('liefert den initialen Match-Zustand', () => {
    installMatchMedia(true)
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(true)
  })

  it('reagiert auf change-Events der MediaQueryList', () => {
    const media = installMatchMedia(false)
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(false)

    act(() => {
      media.matches = true
      media.listeners.forEach((listener) => listener({ matches: true } as MediaQueryListEvent))
    })

    expect(result.current).toBe(true)
  })

  it('meldet sich beim Unmount von der MediaQueryList ab', () => {
    const media = installMatchMedia(false)
    const { unmount } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(media.listeners).toHaveLength(1)

    unmount()

    expect(media.listeners).toHaveLength(0)
  })

  it('liefert false, wenn window.matchMedia fehlt (SSR-/Test-Guard)', () => {
    uninstallMatchMedia()
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(false)
  })

  describe('useIsMobile', () => {
    it('ist true unterhalb der md-Schwelle (max-width: 767px)', () => {
      installMatchMedia(true)
      const { result } = renderHook(() => useIsMobile())
      expect(result.current).toBe(true)
    })

    it('ist false ohne matchMedia', () => {
      uninstallMatchMedia()
      const { result } = renderHook(() => useIsMobile())
      expect(result.current).toBe(false)
    })
  })
})
