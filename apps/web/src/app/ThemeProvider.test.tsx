import { act, render, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTheme } from './theme-context'
import { ThemeProvider } from './ThemeProvider'

const STORAGE_KEY = 'who2be:theme'

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
      media: '(prefers-color-scheme: dark)',
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

function wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('defaults to system preference and resolves via prefers-color-scheme', () => {
    installMatchMedia(true)
    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.preference).toBe('system')
    expect(result.current.resolved).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('persists a manual preference into localStorage and sets data-theme', () => {
    installMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper })

    act(() => result.current.setPreference('dark'))

    expect(result.current.preference).toBe('dark')
    expect(result.current.resolved).toBe('dark')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('restores a stored preference on mount', () => {
    installMatchMedia(false)
    window.localStorage.setItem(STORAGE_KEY, 'dark')

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.preference).toBe('dark')
    expect(result.current.resolved).toBe('dark')
  })

  it('reacts to prefers-color-scheme changes when preference is system', () => {
    const media = installMatchMedia(false)
    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.resolved).toBe('light')

    act(() => {
      media.matches = true
      media.listeners.forEach((listener) =>
        listener({ matches: true } as MediaQueryListEvent),
      )
    })

    expect(result.current.resolved).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('throws when useTheme is called outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    function Consumer() {
      useTheme()
      return null
    }
    expect(() => render(<Consumer />)).toThrow(/ThemeProvider/)
    spy.mockRestore()
  })
})
