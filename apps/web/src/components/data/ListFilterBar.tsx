import { AlertCircle, Search, SlidersHorizontal, X } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'
import {
  type FacetOption,
  type FacetSpec,
  LIST_STATUSES,
  type StatusChipOption,
  type StatusCounts,
  type StatusFilterValue,
  visibleStatusChips,
} from '@/lib/listFilter'

import { ListFilterSheet } from './ListFilterSheet'

export interface AgentFilterOption {
  id: string
  name: string
}

export interface LocaleFilterOption {
  value: string
  label: string
}

export interface GroupByOption {
  value: string
  label: string
}

export type SortOption = GroupByOption

// Status-Chips: entweder der Versionsstatus der vier Inhaltslisten
// (`counts`/`status`, Standardweg) oder generische Chips (`statusOptions`,
// E1) — oder gar keine Chip-Zeile.
type StatusProps =
  | {
      counts: StatusCounts
      status: StatusFilterValue
      onStatusChange: (value: StatusFilterValue) => void
      statusOptions?: undefined
    }
  | {
      statusOptions: StatusChipOption[]
      status: string
      onStatusChange: (value: string) => void
      counts?: undefined
    }
  | { counts?: undefined; statusOptions?: undefined; status?: undefined; onStatusChange?: undefined }

type ListFilterBarProps = StatusProps & {
  // Suche optional (E2): ohne `onQueryChange` keine Suche.
  query?: string
  onQueryChange?: (value: string) => void
  searchPlaceholder?: string
  // Status ≠ Standard, Suche oder eine Facette gesetzt — die Seite kennt den
  // Standardwert, die Leiste nicht.
  active: boolean
  onReset: () => void
  // Eingebaute Facetten; Reihenfolge: Agent → Typ → generische → Tag → Sprache.
  availableTags?: string[]
  tag?: string
  onTagChange?: (value: string) => void
  availableTypes?: string[]
  type?: string
  onTypeChange?: (value: string) => void
  // Uebersetzte Typ-Labels (z. B. Playbook-Typen) — Fallback: Rohwert.
  typeLabel?: (value: string) => string
  // Serverseitige Agent-Facette (WP-B): Auswahl loest einen Refetch aus.
  agents?: AgentFilterOption[]
  agent?: string
  onAgentChange?: (value: string) => void
  // Serverseitige Sprach-Facette (ADR-0045 „Ein Element, eine Sprache").
  locales?: LocaleFilterOption[]
  locale?: string
  onLocaleChange?: (value: string) => void
  // Generische Facetten (E3), fertig uebersetzt von der Seite.
  facets?: FacetSpec[]
  // Anzeige (kein Filter, kein Chip, bleibt beim Zuruecksetzen): erst
  // Sortierung (E5), dann Gruppieren (WP-D3). Wert '' = Standard.
  sortOptions?: SortOption[]
  sort?: string
  onSortChange?: (value: string) => void
  groupOptions?: GroupByOption[]
  group?: string
  onGroupChange?: (value: string) => void
  // E7: Zahlen nicht ladbar (Hinweiszeile) und Trefferzahl fuer den Sheet-Fuss.
  countsUnavailable?: boolean
  resultCount?: number | null
  // E8: ohne Card, fuer Leisten, die schon in einer Karte stehen.
  bare?: boolean
  idPrefix: string
}

// Eine Facette in einheitlicher Form — Select, Chip und Zaehler im Knopf.
interface FacetModel {
  key: string
  label: string
  allLabel: string
  options: FacetOption[]
  value: string
  onChange: (value: string) => void
  showSelect: boolean
  chipText: string
  chipRemove: string
}

function StatusChip({
  option,
  selected,
  onClick,
}: {
  option: StatusChipOption
  selected: boolean
  onClick: () => void
}) {
  const accent = option.accent === true
  return (
    <Button
      type="button"
      size="sm"
      variant={selected ? (accent ? 'brand' : 'default') : 'outline'}
      aria-pressed={selected}
      onClick={onClick}
      // E9: unter `md` 40 px Hit-Target (wie AgentsPage), ab `md` 32 px
      // Chip-Dichte; `h-8` gewinnt gegen `size="sm"` in tailwind-merge.
      className="h-8 min-h-10 gap-1.5 rounded-full md:min-h-0"
    >
      {accent ? <AlertCircle className="size-3.5" aria-hidden="true" /> : null}
      {option.token ? (
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: `var(--status-${option.token})` }}
          aria-hidden="true"
        />
      ) : null}
      <span>{option.label}</span>
      {option.count !== null ? (
        <>
          {/* Leerzeichen fuer den Namen „Offen 3“ (§5); im Flex-Container
              unsichtbar, den Abstand macht `gap`. */}{' '}
          <span className={cn('tabular-nums', selected ? 'opacity-90' : 'text-muted-foreground')}>
            {option.count}
          </span>
        </>
      ) : null}
    </Button>
  )
}

function SelectField({
  id,
  label,
  value,
  onChange,
  hint,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  hint?: string
  children: ReactNode
}) {
  const hintId = `${id}-hint`
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={hint ? hintId : undefined}
      >
        {children}
      </Select>
      {hint ? (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

export function ListFilterBar(props: ListFilterBarProps) {
  const {
    query = '',
    onQueryChange,
    searchPlaceholder,
    active,
    onReset,
    availableTags = [],
    tag = '',
    onTagChange,
    availableTypes = [],
    type = '',
    onTypeChange,
    typeLabel,
    agents = [],
    agent = '',
    onAgentChange,
    locales = [],
    locale = '',
    onLocaleChange,
    facets = [],
    sortOptions = [],
    sort = '',
    onSortChange,
    groupOptions = [],
    group = '',
    onGroupChange,
    countsUnavailable = false,
    resultCount = null,
    bare = false,
    idPrefix,
  } = props
  const { t, i18n } = useTranslation(['data', 'common'])
  const mobile = useIsMobile()
  const format = (value: number) => new Intl.NumberFormat(i18n.language).format(value)

  // --- Status-Chips (E1) ---------------------------------------------------
  let chipOptions: StatusChipOption[] | null = null
  if (props.statusOptions) {
    chipOptions = props.statusOptions
  } else if (props.counts) {
    const counts = props.counts
    chipOptions = [
      { value: 'all', label: t('data:filter.all'), count: counts.all, keepWhenZero: true },
      {
        value: 'attention',
        label: t('data:filter.attention'),
        count: counts.attention,
        accent: true,
      },
      ...LIST_STATUSES.map((s) => ({
        value: s,
        label: t(`common:status.${s}`),
        count: counts[s],
        token: s,
      })),
    ]
  }
  const status = props.status ?? ''
  const onStatusChange = props.onStatusChange as ((value: string) => void) | undefined

  // --- Facetten in fester Reihenfolge (E3) ---------------------------------
  const chip = (label: string, value: string) => ({
    chipText: t('data:filter.chip', { label, value }),
    chipRemove: t('data:filter.chipRemove', { label, value }),
  })
  const models: FacetModel[] = []
  if (onAgentChange) {
    // Chip-Label: Agent-Name, solange die Liste ihn kennt — sonst die rohe ID
    // aus der URL (geteilter Link auf einen inzwischen geloeschten Agent).
    const name = agents.find((entry) => entry.id === agent)?.name ?? agent
    models.push({
      key: 'agent',
      label: t('data:filter.agentLabel'),
      allLabel: t('data:filter.allAgents'),
      options: agents.map((entry) => ({ value: entry.id, label: entry.name })),
      value: agent,
      onChange: onAgentChange,
      showSelect: agents.length > 0,
      chipText: t('data:filter.agentChip', { name }),
      chipRemove: t('data:filter.agentChipRemove', { name }),
    })
  }
  if (onTypeChange) {
    const label = t('data:filter.typeLabel')
    models.push({
      key: 'type',
      label,
      allLabel: t('data:filter.allTypes'),
      options: availableTypes.map((entry) => ({
        value: entry,
        label: typeLabel ? typeLabel(entry) : entry,
      })),
      value: type,
      onChange: onTypeChange,
      showSelect: availableTypes.length > 0,
      ...chip(label, typeLabel && type ? typeLabel(type) : type),
    })
  }
  for (const facet of facets) {
    const selected = facet.options.find((option) => option.value === facet.value)
    models.push({
      ...facet,
      showSelect: facet.options.length > 0,
      ...chip(facet.label, selected?.label ?? facet.value),
    })
  }
  if (onTagChange) {
    const label = t('data:filter.tagLabel')
    models.push({
      key: 'tag',
      label,
      allLabel: t('data:filter.allTags'),
      options: availableTags.map((entry) => ({ value: entry, label: entry })),
      value: tag,
      onChange: onTagChange,
      showSelect: availableTags.length > 0,
      ...chip(label, tag),
    })
  }
  if (onLocaleChange) {
    const name = locales.find((entry) => entry.value === locale)?.label ?? locale
    models.push({
      key: 'locale',
      label: t('data:filter.localeLabel'),
      allLabel: t('data:filter.allLocales'),
      options: locales,
      value: locale,
      onChange: onLocaleChange,
      showSelect: locales.length > 0,
      chipText: t('data:filter.localeChip', { name }),
      chipRemove: t('data:filter.localeChipRemove', { name }),
    })
  }
  const visibleFacets = models.filter((model) => model.showSelect)
  const activeFacets = models.filter((model) => model.value !== '')
  const showSort = Boolean(onSortChange) && sortOptions.length > 0
  const showGroup = Boolean(onGroupChange) && groupOptions.length > 0
  const hasDisplay = showSort || showGroup

  // Mobil (E6, §2.2): ab zwei Facetten oder mit Anzeige-Option liegen die
  // Selects unter `md` im Sheet. Sonst steht das eine Select direkt in der
  // Karte — ein Sheet fuer ein einziges Select ist ein Klick zu viel.
  const useSheet = visibleFacets.length > 1 || hasDisplay
  const sheetActive = useSheet && mobile
  const [sheetOpen, setSheetOpen] = useState(false)
  const filterButtonRef = useRef<HTMLButtonElement>(null)

  // Fokus nach dem Entfernen eines Chips (§2.1 Punkt 7): naechster Chip,
  // sonst „Filter zuruecksetzen“, sonst die Suche. Die Seite aktualisiert
  // asynchron (URL) — deshalb erst fokussieren, wenn der Chip weg ist.
  const chipListRef = useRef<HTMLUListElement>(null)
  const resetRef = useRef<HTMLButtonElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const pendingFocus = useRef<{ key: string; index: number } | null>(null)
  const activeKeys = activeFacets.map((model) => model.key).join('|')
  useEffect(() => {
    const pending = pendingFocus.current
    if (!pending || activeKeys.split('|').includes(pending.key)) return
    pendingFocus.current = null
    const chips = chipListRef.current?.querySelectorAll('button') ?? []
    const target = chips[pending.index] ?? resetRef.current ?? searchRef.current
    target?.focus()
  }, [activeKeys])

  const renderSelect = (model: FacetModel, prefix: string) => {
    const hint = model.options.find((option) => option.value === model.value)?.hint
    return (
      <SelectField
        key={model.key}
        id={`${prefix}-${model.key}`}
        label={model.label}
        value={model.value}
        onChange={model.onChange}
        hint={hint}
      >
        <option value="">{model.allLabel}</option>
        {model.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.count !== undefined
              ? t('data:filter.optionCount', { label: option.label, formatted: format(option.count) })
              : option.label}
          </option>
        ))}
      </SelectField>
    )
  }
  const renderDisplay = (prefix: string) => (
    <>
      {showSort && onSortChange ? (
        <SelectField
          id={`${prefix}-sort`}
          label={t('data:filter.sortLabel')}
          value={sort}
          onChange={onSortChange}
        >
          {sortOptions.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </SelectField>
      ) : null}
      {showGroup && onGroupChange ? (
        <SelectField
          id={`${prefix}-group`}
          label={t('data:filter.groupLabel')}
          value={group}
          onChange={onGroupChange}
        >
          {groupOptions.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.label}
            </option>
          ))}
        </SelectField>
      ) : null}
    </>
  )

  // „Filter“ / „Filter (n)“ — n zaehlt nur gesetzte Facetten, nie Anzeige.
  const filterButton = useSheet ? (
    <Button
      ref={filterButtonRef}
      type="button"
      variant="outline"
      className="min-h-10 shrink-0 gap-2 md:hidden"
      aria-haspopup="dialog"
      aria-expanded={sheetOpen}
      data-testid="list-filter-facets-toggle"
      onClick={() => setSheetOpen(true)}
    >
      <SlidersHorizontal aria-hidden="true" />
      {activeFacets.length > 0
        ? t('data:filter.moreFiltersCount', { count: activeFacets.length })
        : t('data:filter.moreFilters')}
    </Button>
  ) : null

  const body = (
    <>
      {chipOptions && onStatusChange ? (
        <div className="flex flex-col gap-2">
          <div
            className="flex flex-wrap items-center gap-2"
            role="group"
            aria-label={t('data:filter.statusGroup')}
          >
            {visibleStatusChips(chipOptions, status).map((option) => (
              <StatusChip
                key={option.value}
                option={option}
                selected={status === option.value}
                onClick={() => onStatusChange(option.value)}
              />
            ))}
          </div>
          {countsUnavailable ? (
            <p className="text-xs text-muted-foreground">{t('data:filter.countsUnavailable')}</p>
          ) : null}
        </div>
      ) : null}

      {onQueryChange || visibleFacets.length > 0 || hasDisplay ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {onQueryChange ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor={`${idPrefix}-search`}>{t('data:filter.searchLabel')}</Label>
              <div className="flex gap-2">
                <div className="relative min-w-0 flex-1">
                  <Search
                    className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden="true"
                  />
                  {/* pl-9 ist bewusst off-scale (funktionaler Icon-Inset):
                      left-3 (12px) + size-4 (16px) + 8px Luft = 36px, damit der
                      Eingabetext nicht unter dem Such-Icon liegt. */}
                  <Input
                    ref={searchRef}
                    id={`${idPrefix}-search`}
                    value={query}
                    onChange={(event) => onQueryChange(event.target.value)}
                    placeholder={searchPlaceholder ?? t('data:filter.searchPlaceholder')}
                    className="pl-9"
                  />
                </div>
                {filterButton}
              </div>
            </div>
          ) : filterButton ? (
            <div className="flex md:hidden">{filterButton}</div>
          ) : null}

          {/* `contents`: die Facetten bleiben Kinder des Rasters. Mit Sheet
              unter `md` `hidden` (nicht im A11y-Tree, das Sheet traegt sie);
              jsdom ohne `matchMedia` sieht weiter das Raster. Ist das Sheet
              wirklich aktiv, entfaellt die Kopie ganz — sonst traegt die
              Seite jedes Label doppelt (Playwright-`getByLabel` strikt). */}
          {sheetActive ? null : (
            <div
              className={cn(useSheet ? 'hidden md:contents' : 'contents')}
              data-testid="list-filter-facets"
            >
              {visibleFacets.map((model) => renderSelect(model, idPrefix))}
              {renderDisplay(idPrefix)}
            </div>
          )}
        </div>
      ) : null}

      {activeFacets.length > 0 || active ? (
        <div className="flex flex-wrap items-center gap-2">
          {activeFacets.length > 0 ? (
            <ul
              ref={chipListRef}
              className="flex flex-wrap items-center gap-2"
              aria-label={t('data:filter.activeFilters')}
            >
              {activeFacets.map((model, index) => (
                <li key={model.key} className="max-w-full min-w-0">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="h-7 min-h-10 max-w-full gap-1 rounded-full px-3 text-xs whitespace-normal md:min-h-0"
                    aria-label={model.chipRemove}
                    onClick={() => {
                      pendingFocus.current = { key: model.key, index }
                      model.onChange('')
                    }}
                  >
                    <span className="min-w-0 break-words">{model.chipText}</span>
                    <X className="size-4" aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}
          {active ? (
            <Button
              ref={resetRef}
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 min-h-10 gap-1 px-2 text-xs md:min-h-0"
              onClick={onReset}
            >
              <X className="size-4" aria-hidden="true" />
              {t('data:filter.reset')}
            </Button>
          ) : null}
        </div>
      ) : null}

      {sheetActive ? (
        <ListFilterSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          facets={visibleFacets.map((model) => renderSelect(model, `${idPrefix}-sheet`))}
          display={hasDisplay ? renderDisplay(`${idPrefix}-sheet`) : null}
          onReset={onReset}
          resultCount={resultCount}
          returnFocusRef={filterButtonRef}
        />
      ) : null}
    </>
  )

  if (bare) return <div className="flex flex-col gap-4">{body}</div>
  return (
    <Card>
      <CardContent className="flex flex-col gap-4 pt-6">{body}</CardContent>
    </Card>
  )
}
