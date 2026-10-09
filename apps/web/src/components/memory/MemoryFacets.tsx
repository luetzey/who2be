import { useTranslation } from 'react-i18next'

import type { Agent, MemoryCounts } from '@/api/types'
import type { FacetSpec, StatusChipOption } from '@/lib/listFilter'

import {
  ENTRY_FACET_VALUES,
  type EntryFacet,
  type EntryFilters,
} from '@/features/memory/hooks/useMemoryApi'

// Facetten des Gedaechtnisses (Gedaechtnisverwaltung §6.2/§6.3).
//
// Je Facette genau EIN Wert: `GET /memories` nimmt je Feld einen Wert
// (`MemoryFilter`, ADR-0053 6.4.1). Zaehler kommen aus `/memories/counts`
// (je Gruppe ohne den eigenen Filter); Werte mit 0 bleiben waehlbar.
//
// `useMemoryFilterBar` → Props der ListFilterBar (Filter-Standard §3.1): Tab
// „Eintraege“ (M1) und die Gedaechtnis-Karte am Agenten (M2, ohne Agent-Facette).

// Status-Chips in Lebenszyklus-Reihenfolge, Punkt-Token wie `StatusLine`.
const STATUS_TOKENS: Record<string, string> = {
  active: 'active',
  pending: 'review',
  expired: 'draft',
  rejected: 'draft',
}

// Facetten der Leiste (ohne Status — der steht in den Chips), feste Reihenfolge.
const BAR_FACETS = ['agent', 'kind', 'health', 'origin', 'source'] as const

interface FacetsProps {
  filters: EntryFilters
  counts: MemoryCounts | null
  countsError: boolean
  agents: Agent[]
  // Agent fest vorgegeben (Gedaechtnis-Karte am Agenten): keine Agent-Facette.
  hideAgent?: boolean
  onChange: (facet: EntryFacet, value: string) => void
}

/**
 * Adapter Gedaechtnis → ListFilterBar (Filter-Standard §3.1): Status als
 * Chips, die uebrigen Facetten als Selects mit Serverzahl „(n)“, Agenten
 * alphabetisch, Hinweis zum gewaehlten Zustand unter dem Select.
 */
export function useMemoryFilterBar({
  filters,
  counts,
  countsError,
  agents,
  hideAgent = false,
  onChange,
}: FacetsProps): {
  statusOptions: StatusChipOption[]
  status: string
  onStatusChange: (value: string) => void
  facets: FacetSpec[]
} {
  const { t } = useTranslation(['learning', 'data'])
  const label = useFacetLabel(agents)
  const known = !countsError && counts !== null
  const countOf = (facet: EntryFacet, value: string): number | undefined =>
    known ? (counts?.groups?.[facet]?.[value] ?? 0) : undefined

  // „Alle“: ohne Status-Filter ist `total` genau diese Menge; mit Filter die
  // Summe der Status-Gruppe (die Gruppe zaehlt ohne den eigenen Filter).
  const statusGroup = counts?.groups?.status ?? {}
  const allCount = !known
    ? null
    : filters.status === ''
      ? (counts?.total ?? 0)
      : Object.values(statusGroup).reduce((sum, value) => sum + value, 0)
  const statusOptions: StatusChipOption[] = [
    { value: 'all', label: t('data:filter.all'), count: allCount, keepWhenZero: true },
    ...ENTRY_FACET_VALUES.status.map((value) => ({
      value,
      label: label('status', value),
      count: known ? (statusGroup[value] ?? 0) : null,
      token: STATUS_TOKENS[value],
    })),
  ]

  const shown = BAR_FACETS.filter((facet) => !(hideAgent && facet === 'agent'))
  const facets = shown.map((facet): FacetSpec => {
    let values: string[]
    if (facet === 'agent') {
      // Server meldet nur vorhandene Agenten; ohne Zahlen alle bekannten. Ein
      // gesetzter Agent bleibt waehlbar, auch ohne Eintraege.
      values = known ? Object.keys(counts?.groups?.agent ?? {}) : agents.map((agent) => agent.id)
      if (filters.agent !== '' && !values.includes(filters.agent)) values.push(filters.agent)
      values.sort((a, b) => label('agent', a).localeCompare(label('agent', b)))
    } else {
      values = [...ENTRY_FACET_VALUES[facet]]
    }
    return {
      key: facet,
      label: t(`learning:entries.facet.${facet}`),
      allLabel: facet === 'agent' ? t('data:filter.allAgents') : t('learning:entries.facet.all'),
      options: values.map((value) => ({
        value,
        label: label(facet, value),
        count: countOf(facet, value),
        hint: facet === 'health' ? t(`learning:health.${value}Hint`) : undefined,
      })),
      value: filters[facet],
      onChange: (value) => onChange(facet, value),
    }
  })

  return {
    statusOptions,
    status: filters.status === '' ? 'all' : filters.status,
    onStatusChange: (value) => onChange('status', value === 'all' ? '' : value),
    facets,
  }
}

/** Anzeigename eines Facettenwerts. */
function useFacetLabel(agents: Agent[]) {
  const { t } = useTranslation('learning')
  return (facet: EntryFacet, value: string): string => {
    switch (facet) {
      case 'agent':
        return agents.find((agent) => agent.id === value)?.name ?? value
      case 'kind':
        return value === 'user_fact' ? t('kind.user_fact_agent') : t(`kind.${value}`)
      case 'status':
        return t(`entries.status.${value}`)
      case 'health':
        return t(`health.${value}`)
      case 'origin':
        return t(`origin.${value}`)
      case 'source':
        return t(`channel.${value}`)
    }
  }
}
