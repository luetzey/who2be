import { SlidersHorizontal, X } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Agent, MemoryCounts } from '@/api/types'
import { Button } from '@/components/ui/button'
import { InfoTooltip } from '@/components/ui/info-tooltip'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useIsMobile } from '@/hooks/useMediaQuery'
import type { FacetSpec, StatusChipOption } from '@/lib/listFilter'
import { cn } from '@/lib/utils'

import {
  ENTRY_FACETS,
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
// Tab „Eintraege“: `useMemoryFilterBar` → Props der ListFilterBar
// (Filter-Standard §3.1, M1). Die Radiogruppen samt `FilterSheetButton` und
// `ActiveFilterChips` dienen nur noch der Gedaechtnis-Karte am Agenten (bis M2).

// Status-Chips in Lebenszyklus-Reihenfolge, Punkt-Token wie `StatusLine`.
const STATUS_TOKENS: Record<string, string> = {
  active: 'active',
  pending: 'review',
  expired: 'draft',
  rejected: 'draft',
}

// Facetten der Leiste (ohne Status — der steht in den Chips), feste Reihenfolge.
const BAR_FACETS = ['agent', 'kind', 'health', 'origin', 'source'] as const

/**
 * Adapter Tab „Eintraege“ → ListFilterBar (Filter-Standard §3.1): Status als
 * Chips, die uebrigen Facetten als Selects mit Serverzahl „(n)“, Agenten
 * alphabetisch, Hinweis zum gewaehlten Zustand unter dem Select.
 */
export function useMemoryFilterBar({
  filters,
  counts,
  countsError,
  agents,
  onChange,
}: Omit<FacetsProps, 'hideAgent'>): {
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

  const facets = BAR_FACETS.map((facet): FacetSpec => {
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

interface FacetsProps {
  filters: EntryFilters
  counts: MemoryCounts | null
  countsError: boolean
  agents: Agent[]
  // Agent fest vorgegeben (Agent-Seite, C5b-2): keine Agent-Facette.
  hideAgent?: boolean
  onChange: (facet: EntryFacet, value: string) => void
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

/** Werte einer Facette in Anzeigereihenfolge. */
function valuesOf(facet: EntryFacet, filters: EntryFilters, counts: MemoryCounts | null): string[] {
  if (facet !== 'agent') return [...ENTRY_FACET_VALUES[facet]]
  // Agenten: nach Anzahl absteigend. Der Server meldet nur vorhandene Werte;
  // ein gesetzter Agent ohne Eintraege bleibt trotzdem waehlbar sichtbar.
  const groups = counts?.groups?.agent ?? {}
  const ids = Object.keys(groups).sort((a, b) => groups[b] - groups[a])
  if (filters.agent !== '' && !ids.includes(filters.agent)) ids.push(filters.agent)
  return ids
}

function FacetGroup({
  facet,
  filters,
  counts,
  countsError,
  agents,
  onChange,
  idPrefix,
}: Omit<FacetsProps, 'hideAgent'> & { facet: EntryFacet; idPrefix: string }) {
  const { t, i18n } = useTranslation('learning')
  const label = useFacetLabel(agents)
  const format = new Intl.NumberFormat(i18n.language)
  const legendId = `${idPrefix}-${facet}-legend`
  const values = valuesOf(facet, filters, counts)
  const groupCounts = counts?.groups?.[facet] ?? null

  const item = (value: string, text: string, count: number | null, hint?: string) => {
    const id = `${idPrefix}-${facet}-${value || 'all'}`
    const hintId = hint !== undefined ? `${id}-hint` : undefined
    const zero = count === 0
    return (
      <div key={value || 'all'} className="flex min-h-8 items-center gap-2">
        <RadioGroupItem id={id} value={value} aria-describedby={hintId} />
        <Label
          htmlFor={id}
          className={cn(
            'flex min-h-8 min-w-0 flex-1 cursor-pointer items-center justify-between gap-2 font-normal',
            zero && 'text-muted-foreground',
          )}
        >
          <span className="min-w-0 break-words">{text}</span>
          {count !== null ? (
            <>
              <span aria-hidden="true" className="shrink-0 text-muted-foreground tabular-nums">
                {format.format(count)}
              </span>
              <span className="sr-only">
                , {t('entries.resultCount', { count, formatted: format.format(count) })}
              </span>
            </>
          ) : null}
        </Label>
        {hint !== undefined ? (
          <>
            <span id={hintId} className="sr-only">
              {hint}
            </span>
            <InfoTooltip>{hint}</InfoTooltip>
          </>
        ) : null}
      </div>
    )
  }

  return (
    <fieldset className="flex min-w-0 flex-col gap-1" aria-labelledby={legendId}>
      <legend
        id={legendId}
        className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {t(`entries.facet.${facet}`)}
      </legend>
      <RadioGroup
        value={filters[facet]}
        onValueChange={(value) => onChange(facet, value)}
        aria-labelledby={legendId}
        className="gap-0"
      >
        {item('', t('entries.facet.all'), null)}
        {values.map((value) =>
          item(
            value,
            label(facet, value),
            countsError || counts === null ? null : (groupCounts?.[value] ?? 0),
            facet === 'health' ? t(`health.${value}Hint`) : undefined,
          ),
        )}
      </RadioGroup>
    </fieldset>
  )
}

function FacetGroups(props: FacetsProps & { idPrefix: string }) {
  const { t } = useTranslation('learning')
  const facets = ENTRY_FACETS.filter((facet) => !(props.hideAgent && facet === 'agent'))
  return (
    <div className="flex flex-col gap-5">
      {props.countsError ? (
        <p className="text-xs text-muted-foreground" data-testid="counts-unavailable">
          {t('entries.countsUnavailable')}
        </p>
      ) : null}
      {facets.map((facet) => (
        <FacetGroup key={facet} facet={facet} {...props} />
      ))}
    </div>
  )
}

/** Zahl der gesetzten Facetten (ohne Suche und Sortierung). */
function activeFacetCount(filters: EntryFilters, hideAgent = false): number {
  return ENTRY_FACETS.filter((facet) => !(hideAgent && facet === 'agent') && filters[facet] !== '')
    .length
}

/**
 * „Filter (n)“ unter `lg`: oeffnet die Facetten als Sheet — unter `md` von
 * unten in voller Hoehe, sonst von rechts (Spec §6.1, §14). Filter wirken
 * sofort; „n Eintraege zeigen“ schliesst nur. `alwaysVisible`: auch ab `lg`
 * (Agent-Seite, §6.6 — dort gibt es keine Facettenspalte).
 */
export function FilterSheetButton({
  total,
  onReset,
  alwaysVisible = false,
  ...props
}: FacetsProps & { total: number | null; onReset: () => void; alwaysVisible?: boolean }) {
  const { t, i18n } = useTranslation('learning')
  const [open, setOpen] = useState(false)
  const mobile = useIsMobile()
  const descriptionId = useId()
  const active = activeFacetCount(props.filters, props.hideAgent)
  return (
    <>
      <Button
        type="button"
        variant="outline"
        className={cn('min-h-11 md:min-h-9', !alwaysVisible && 'lg:hidden')}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        <SlidersHorizontal aria-hidden="true" />
        {t('entries.filterButton', { count: active })}
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side={mobile ? 'bottom' : 'right'}
          aria-describedby={descriptionId}
          className={cn(
            'gap-0 overflow-y-auto overscroll-contain p-0',
            mobile ? 'h-[100svh] rounded-none' : 'w-full sm:max-w-sm',
          )}
        >
          <SheetHeader className="sticky top-0 z-10 border-b bg-background p-4 pr-12 text-left">
            <SheetTitle>{t('entries.filterTitle')}</SheetTitle>
            <SheetDescription id={descriptionId}>{t('entries.filterDescription')}</SheetDescription>
          </SheetHeader>
          <div className="flex-1 p-4">
            <FacetGroups {...props} idPrefix="facet-sheet" />
          </div>
          <div className="sticky bottom-0 flex flex-wrap gap-2 border-t bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <Button type="button" variant="outline" className="min-h-11 flex-1" onClick={onReset}>
              {t('entries.resetFilters')}
            </Button>
            <Button type="button" className="min-h-11 flex-1" onClick={() => setOpen(false)}>
              {total !== null
                ? t('entries.showResults', {
                    count: total,
                    formatted: new Intl.NumberFormat(i18n.language).format(total),
                  })
                : t('entries.showResultsPlain')}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}

/** Gesetzte Filter als entfernbare Chips ueber der Liste (Spec §6.1, §14). */
export function ActiveFilterChips({
  filters,
  agents,
  hideAgent,
  onChange,
}: Pick<FacetsProps, 'filters' | 'agents' | 'hideAgent' | 'onChange'>) {
  const { t } = useTranslation('learning')
  const label = useFacetLabel(agents)
  const active = ENTRY_FACETS.filter(
    (facet) => !(hideAgent && facet === 'agent') && filters[facet] !== '',
  )
  if (active.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-2" aria-label={t('entries.activeFilters')}>
      {active.map((facet) => {
        const text = label(facet, filters[facet])
        const full = `${t(`entries.facet.${facet}`)}: ${text}`
        return (
          <li key={facet} className="max-w-full min-w-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-auto min-h-11 max-w-full gap-1 rounded-full py-1 whitespace-normal md:min-h-8"
              aria-label={t('entries.removeFilter', { label: full })}
              onClick={() => onChange(facet, '')}
            >
              <span className="min-w-0 break-words">{full}</span>
              <X aria-hidden="true" />
            </Button>
          </li>
        )
      })}
    </ul>
  )
}
