import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  ThemeContext,
  type ResolvedTheme,
  type ThemeContextValue,
  type ThemePreference,
} from './theme-context'

const STORAGE_KEY = 'who2be:theme'
const PREFERENCES: readonly ThemePreference[] = ['light', 'dark', 'system']

function readStoredPreference(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return PREFERENCES.includes(stored as ThemePreference)
    ? (stored as ThemePreference)
    : 'system'
}

function readSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light'
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

interface ThemeProviderProps {
  children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(() => readStoredPreference())
  const [systemTheme, setSystemTheme] = useState<ResolvedTheme>(() => readSystemTheme())

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (event: MediaQueryListEvent) => {
      setSystemTheme(event.matches ? 'dark' : 'light')
    }
    media.addEventListener('change', handler)
    return () => media.removeEventListener('change', handler)
  }, [])

  const resolved: ResolvedTheme = preference === 'system' ? systemTheme : preference

  useEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.dataset.theme = resolved
  }, [resolved])

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, next)
    }
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolved, setPreference }),
    [preference, resolved, setPreference],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
