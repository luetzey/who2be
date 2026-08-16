import { useCallback, useEffect, useState } from 'react'

import type { KbSearchHit, WorkAreaSearchHit } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

// Beide Suchen teilen sich Zustand und Fehlerbehandlung, bleiben aber getrennte
// Hooks: WorkArea und Knowledge Base haben serverseitig EIGENE Indizes (die
// KB-Suche findet per Konstruktion nie Rohmaterial). Ein gemeinsamer Hook mit
// `scope`-Parameter wuerde diese Trennung verwischen.

interface SearchState<T> {
  hits: T[]
  loading: boolean
  error: string | null
}

const IDLE = { hits: [], loading: false, error: null }

function useSearch<T>(
  query: string,
  run: (q: string) => Promise<T[]>,
  errorKey: string,
): SearchState<T> {
  const [state, setState] = useState<SearchState<T>>(IDLE as SearchState<T>)

  useEffect(() => {
    // Leere Suche = kein Request. Der Server verlangt `q` ohnehin nicht-leer
    // (422), und eine „Alles"-Suche gibt es bewusst nicht — die Suche ist der
    // Einstieg, nicht der Katalog.
    if (query.trim() === '') {
      setState(IDLE as SearchState<T>)
      return
    }
    let cancelled = false
    setState({ hits: [], loading: true, error: null })
    run(query.trim())
      .then((hits) => {
        // Antworten ueberholter Anfragen verwerfen — beim Tippen ist die
        // Reihenfolge der Rueckkehr nicht garantiert.
        if (!cancelled) setState({ hits, loading: false, error: null })
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setState({
          hits: [],
          loading: false,
          error: cause instanceof Error ? cause.message : i18n.t(errorKey),
        })
      })
    return () => {
      cancelled = true
    }
  }, [query, run, errorKey])

  return state
}

export function useWorkAreaSearch(query: string, areaId?: string): SearchState<WorkAreaSearchHit> {
  const api = useApi()
  const run = useCallback(
    (q: string) =>
      api.searchWorkArea(areaId !== undefined && areaId !== '' ? { q, area_id: areaId } : { q }),
    [api, areaId],
  )
  return useSearch(query, run, 'workarea:search.loadError')
}

export function useKbSearch(query: string): SearchState<KbSearchHit> {
  const api = useApi()
  const run = useCallback((q: string) => api.searchKb({ q }), [api])
  return useSearch(query, run, 'workarea:kb.loadError')
}
