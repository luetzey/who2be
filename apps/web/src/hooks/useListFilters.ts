import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import type { VersionStatus } from '@/api/types'
import {
  countByStatus,
  isStatusFilterValue,
  matchesStatusFilter,
  type StatusCounts,
  type StatusFilterValue,
} from '@/lib/listFilter'

// Wie ein Listen-Item auf die filterbaren Felder abgebildet wird. Pro Liste
// unterschiedlich (Persona.content.tags vs. Playbook.tags/type), daher als
// Accessors uebergeben statt fest verdrahtet.
export interface ListFilterAccessors<T> {
  name: (item: T) => string
  status: (item: T) => VersionStatus | undefined
  hasPendingDraft: (item: T) => boolean | undefined
  tags?: (item: T) => string[]
  type?: (item: T) => string | undefined
  // Zusaetzlicher Suchtext neben dem Namen (z. B. Playbook-Trigger) — die
  // Freitext-Suche trifft, wenn Name ODER einer dieser Strings passt.
  searchText?: (item: T) => string[]
}

export interface ListFilters<T> {
  filtered: T[]
  counts: StatusCounts
  status: StatusFilterValue
  query: string
  tag: string
  type: string
  // SERVERSEITIGE Facette (WP-B): Agent-ID aus `?agent=`. Anders als die
  // clientseitigen Facetten filtert der Hook damit NICHT — die Page reicht
  // den Wert an den Daten-Hook durch, der den Refetch ausloest.
  agent: string
  // SERVERSEITIGE Facette (ADR-0045 „Ein Element, eine Sprache"): Sprache aus
  // `?locale=` — wie `agent` kein clientseitiger Filter, sondern an den
  // Daten-Hook durchgereicht (Refetch mit `?locale=`).
  locale: string
  // ANZEIGE-Praeferenz (WP-D3): Group-by-Modus aus `?group=`. Kein Filter —
  // grenzt die Liste nicht ein und zaehlt deshalb weder fuer `active` noch
  // fuer `reset`. Die Page interpretiert/validiert den Wert selbst
  // (Playbooks: `none|type|composite`) und gruppiert clientseitig.
  group: string
  availableTags: string[]
  availableTypes: string[]
  active: boolean
  setStatus: (value: StatusFilterValue) => void
  setQuery: (value: string) => void
  setTag: (value: string) => void
  setType: (value: string) => void
  setAgent: (value: string) => void
  setLocale: (value: string) => void
  setGroup: (value: string) => void
  reset: () => void
}

// URL-Query-Keys — die Liste ist teilbar/bookmarkbar, und das Dashboard
// verlinkt via `?status=review` direkt auf die vorgefilterte Sicht.
const STATUS_KEY = 'status'
const QUERY_KEY = 'q'
const TAG_KEY = 'tag'
const TYPE_KEY = 'type'
const AGENT_KEY = 'agent'
const LOCALE_KEY = 'locale'
const GROUP_KEY = 'group'

/**
 * Aktueller `?agent=`-Wert (serverseitige Facette, WP-B) — fuer die Page,
 * die den Wert VOR `useListFilters` an ihren Daten-Hook durchreichen muss
 * (der Filter wirkt im Backend, die Liste kommt bereits gefiltert an).
 */
export function useAgentFilterParam(): string {
  const [params] = useSearchParams()
  return params.get(AGENT_KEY) ?? ''
}

/**
 * Aktueller `?locale=`-Wert (serverseitige Facette, ADR-0045) — analog zu
 * `useAgentFilterParam`: die Page liest ihn VOR `useListFilters` und reicht
 * ihn an ihren Daten-Hook durch.
 */
export function useLocaleFilterParam(): string {
  const [params] = useSearchParams()
  return params.get(LOCALE_KEY) ?? ''
}

/**
 * Kombinierbare, URL-synchronisierte Filter fuer eine Listen-Seite:
 * Status-Quick-Filter (inkl. „Braucht Aufmerksamkeit") UND Freitext UND Tag
 * UND Typ. Zaehler werden ueber die nach Text/Tag/Typ eingegrenzte Basismenge
 * gerechnet, damit die Chip-Zahlen dem tatsaechlichen Klick-Ergebnis entsprechen.
 *
 * Die Agent-Facette (`?agent=`) ist die Ausnahme: sie wirkt SERVERSEITIG.
 * Der Hook verwaltet nur URL-Wert/Setter/Reset; `items` muessen bereits
 * gefiltert ankommen (Page: `useAgentFilterParam()` → Daten-Hook → Refetch).
 */
export function useListFilters<T>(
  items: readonly T[],
  accessors: ListFilterAccessors<T>,
): ListFilters<T> {
  const [params, setParams] = useSearchParams()

  const rawStatus = params.get(STATUS_KEY) ?? 'all'
  const status: StatusFilterValue = isStatusFilterValue(rawStatus) ? rawStatus : 'all'
  const query = params.get(QUERY_KEY) ?? ''
  const tag = params.get(TAG_KEY) ?? ''
  const type = params.get(TYPE_KEY) ?? ''
  const agent = params.get(AGENT_KEY) ?? ''
  const locale = params.get(LOCALE_KEY) ?? ''
  const group = params.get(GROUP_KEY) ?? ''

  const setParam = useCallback(
    (key: string, value: string) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (value === '' || value === 'all') {
            next.delete(key)
          } else {
            next.set(key, value)
          }
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  const setStatus = useCallback((value: StatusFilterValue) => setParam(STATUS_KEY, value), [setParam])
  const setQuery = useCallback((value: string) => setParam(QUERY_KEY, value), [setParam])
  const setTag = useCallback((value: string) => setParam(TAG_KEY, value), [setParam])
  const setType = useCallback((value: string) => setParam(TYPE_KEY, value), [setParam])
  const setAgent = useCallback((value: string) => setParam(AGENT_KEY, value), [setParam])
  const setLocale = useCallback((value: string) => setParam(LOCALE_KEY, value), [setParam])
  const setGroup = useCallback((value: string) => setParam(GROUP_KEY, value), [setParam])

  const reset = useCallback(() => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete(STATUS_KEY)
        next.delete(QUERY_KEY)
        next.delete(TAG_KEY)
        next.delete(TYPE_KEY)
        next.delete(AGENT_KEY)
        next.delete(LOCALE_KEY)
        return next
      },
      { replace: true },
    )
  }, [setParams])

  const availableTags = useMemo(() => {
    if (!accessors.tags) return []
    const set = new Set<string>()
    for (const item of items) {
      for (const entry of accessors.tags(item)) set.add(entry)
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b))
  }, [items, accessors])

  const availableTypes = useMemo(() => {
    if (!accessors.type) return []
    const set = new Set<string>()
    for (const item of items) {
      const value = accessors.type(item)
      if (value) set.add(value)
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b))
  }, [items, accessors])

  // Basismenge: alles ausser dem Status-Filter angewandt — die Grundlage
  // sowohl fuer die Zaehler als auch fuer die finale (status-gefilterte) Liste.
  const base = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter((item) => {
      if (q !== '') {
        const haystacks = [accessors.name(item), ...(accessors.searchText?.(item) ?? [])]
        if (!haystacks.some((text) => text.toLowerCase().includes(q))) return false
      }
      if (tag !== '' && accessors.tags && !accessors.tags(item).includes(tag)) return false
      if (type !== '' && accessors.type && accessors.type(item) !== type) return false
      return true
    })
  }, [items, query, tag, type, accessors])

  const counts = useMemo(
    () =>
      countByStatus(
        base.map((item) => ({
          status: accessors.status(item),
          hasPendingDraft: accessors.hasPendingDraft(item),
        })),
      ),
    [base, accessors],
  )

  const filtered = useMemo(
    () =>
      base.filter((item) =>
        matchesStatusFilter(
          { status: accessors.status(item), hasPendingDraft: accessors.hasPendingDraft(item) },
          status,
        ),
      ),
    [base, status, accessors],
  )

  const active =
    status !== 'all' || query !== '' || tag !== '' || type !== '' || agent !== '' || locale !== ''

  return {
    filtered: filtered as T[],
    counts,
    status,
    query,
    tag,
    type,
    agent,
    locale,
    group,
    availableTags,
    availableTypes,
    active,
    setStatus,
    setQuery,
    setTag,
    setType,
    setAgent,
    setLocale,
    setGroup,
    reset,
  }
}
