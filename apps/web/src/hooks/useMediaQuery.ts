import { useEffect, useState } from 'react'

// Mobile-Schwelle: alles unterhalb Tailwinds `md`-Breakpoint (768px) gilt als
// "mobile" (Designsprache §4 „Responsive & Breakpoints"). `max-width: 767px`
// bleibt exklusiv zu `md:` (min-width: 768px) — keine Ueberlappung am
// Breakpoint selbst.
const MOBILE_QUERY = '(max-width: 767px)'

function getMatch(query: string): boolean {
  // Gleicher Guard wie `app/ThemeProvider.tsx` (`readSystemTheme`): SSR/Test-
  // Umgebungen ohne `window` oder ohne `matchMedia`-Implementierung liefern
  // `false`, statt beim Mount zu crashen.
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(query).matches
}

/**
 * Liefert, ob `query` aktuell matched, und haelt den Wert ueber
 * `change`-Events der `MediaQueryList` aktuell.
 *
 * Ohne `window.matchMedia` (SSR, JSDOM ohne Polyfill) liefert der Hook
 * durchgehend `false` — kein Crash, kein Server/Client-Mismatch-Risiko.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState<boolean>(() => getMatch(query))

  useEffect(() => {
    // Kein `matchMedia` (SSR, JSDOM ohne Polyfill): Initialzustand ist bereits
    // `false` (siehe `getMatch` oben) — nichts zu subscriben, nichts zu tun.
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return
    }
    const media = window.matchMedia(query)
    setMatches(media.matches)
    const handler = (event: MediaQueryListEvent) => {
      setMatches(event.matches)
    }
    media.addEventListener('change', handler)
    return () => media.removeEventListener('change', handler)
  }, [query])

  return matches
}

/**
 * Kurzform fuer die Mobile-Schwelle der Designsprache (unterhalb `md`,
 * `max-width: 767px`). Gedacht als Basis fuer spaetere Mobile-Wellen
 * (Sheet-Navigation, Touch-Layouts) — heute ohne Konsumenten.
 */
export function useIsMobile(): boolean {
  return useMediaQuery(MOBILE_QUERY)
}
