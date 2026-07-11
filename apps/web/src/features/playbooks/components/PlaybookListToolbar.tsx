import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { AgentFilterOption, GroupByOption } from '@/components/data/ListFilterBar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  LIST_STATUSES,
  type StatusCounts,
  type StatusFilterValue,
} from '@/lib/listFilter'

// Design-Handoff „Playbooks-Redesign" §Filterleiste: ersetzt die
// ListFilterBar-Card auf der Playbooks-Uebersicht durch eine Zeile aus
// Segmented-Status-Control, Suche (Name oder Trigger) und einem
// „Filter"-Popover fuer die erweiterten Facetten (Tag/Typ/Agent/Gruppieren).
// Bewusst feature-lokal — Promotion nach components/data erst, wenn eine
// zweite Liste das Muster uebernimmt.

interface PlaybookListToolbarProps {
  counts: StatusCounts
  status: StatusFilterValue
  onStatusChange: (value: StatusFilterValue) => void
  query: string
  onQueryChange: (value: string) => void
  active: boolean
  onReset: () => void
  availableTags: string[]
  tag: string
  onTagChange: (value: string) => void
  availableTypes: string[]
  type: string
  onTypeChange: (value: string) => void
  typeLabel?: (value: string) => string
  agents: AgentFilterOption[]
  agent: string
  onAgentChange: (value: string) => void
  groupOptions: GroupByOption[]
  group: string
  onGroupChange: (value: string) => void
}

function Segment({
  label,
  count,
  selected,
  accent,
  onClick,
}: {
  label: string
  count?: number
  selected: boolean
  accent?: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        'h-8 gap-1.5 rounded-md px-3 text-sm font-medium',
        selected
          ? 'bg-background text-foreground shadow-card hover:bg-background'
          : 'text-muted-foreground',
      )}
    >
      <span>{label}</span>
      {count !== undefined ? (
        <span
          className={cn(
            'tabular-nums',
            accent ? 'font-semibold text-brand' : 'text-muted-foreground',
          )}
        >
          {count}
        </span>
      ) : null}
    </Button>
  )
}

export function PlaybookListToolbar({
  counts,
  status,
  onStatusChange,
  query,
  onQueryChange,
  active,
  onReset,
  availableTags,
  tag,
  onTagChange,
  availableTypes,
  type,
  onTypeChange,
  typeLabel,
  agents,
  agent,
  onAgentChange,
  groupOptions,
  group,
  onGroupChange,
}: PlaybookListToolbarProps) {
  const { t } = useTranslation(['data', 'common', 'playbooks'])
  const agentName = agents.find((entry) => entry.id === agent)?.name ?? agent
  const showAttention = counts.attention > 0 || status === 'attention'
  // Facetten-Zaehler auf dem Filter-Button — macht im zugeklappten Zustand
  // sichtbar, dass Popover-Filter aktiv sind.
  const facetCount = [tag, type, agent].filter((value) => value !== '').length

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div
          className="inline-flex items-center gap-1 rounded-lg bg-muted p-1"
          role="group"
          aria-label={t('data:filter.statusGroup')}
        >
          <Segment
            label={t('data:filter.all')}
            selected={status === 'all'}
            onClick={() => onStatusChange('all')}
          />
          {showAttention ? (
            <Segment
              label={t('data:filter.attention')}
              count={counts.attention}
              selected={status === 'attention'}
              accent
              onClick={() => onStatusChange('attention')}
            />
          ) : null}
          {LIST_STATUSES.filter((s) => counts[s] > 0 || status === s).map((s) => (
            <Segment
              key={s}
              label={t(`common:status.${s}`)}
              count={counts[s]}
              selected={status === s}
              onClick={() => onStatusChange(s)}
            />
          ))}
        </div>

        <div className="relative min-w-48 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          {/* pl-9 ist bewusst off-scale (funktionaler Icon-Inset, wie in der
              ListFilterBar): left-3 (12px) + size-4 (16px) + 8px Luft. */}
          <Input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={t('playbooks:list.searchPlaceholder')}
            aria-label={t('data:filter.searchLabel')}
            className={cn('pr-9 pl-9', query !== '' && 'border-brand')}
          />
          {query !== '' ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => onQueryChange('')}
              aria-label={t('data:filter.clearSearch')}
              className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
            >
              <X className="size-4" aria-hidden="true" />
            </Button>
          ) : null}
        </div>

        <Popover>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" className="gap-2">
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              {t('data:filter.moreFilters')}
              {facetCount > 0 ? (
                <span className="text-muted-foreground tabular-nums">{facetCount}</span>
              ) : null}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="flex w-72 flex-col gap-4">
            {availableTags.length > 0 ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbooks-facet-tag">{t('data:filter.tagLabel')}</Label>
                <Select
                  id="playbooks-facet-tag"
                  value={tag}
                  onChange={(event) => onTagChange(event.target.value)}
                >
                  <option value="">{t('data:filter.allTags')}</option>
                  {availableTags.map((entry) => (
                    <option key={entry} value={entry}>
                      {entry}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            {availableTypes.length > 0 ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbooks-facet-type">{t('data:filter.typeLabel')}</Label>
                <Select
                  id="playbooks-facet-type"
                  value={type}
                  onChange={(event) => onTypeChange(event.target.value)}
                >
                  <option value="">{t('data:filter.allTypes')}</option>
                  {availableTypes.map((entry) => (
                    <option key={entry} value={entry}>
                      {typeLabel ? typeLabel(entry) : entry}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            {agents.length > 0 ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbooks-facet-agent">{t('data:filter.agentLabel')}</Label>
                <Select
                  id="playbooks-facet-agent"
                  value={agent}
                  onChange={(event) => onAgentChange(event.target.value)}
                >
                  <option value="">{t('data:filter.allAgents')}</option>
                  {agents.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.name}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            {groupOptions.length > 0 ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="playbooks-facet-group">{t('data:filter.groupLabel')}</Label>
                <Select
                  id="playbooks-facet-group"
                  value={group}
                  onChange={(event) => onGroupChange(event.target.value)}
                >
                  {groupOptions.map((entry) => (
                    <option key={entry.value} value={entry.value}>
                      {entry.label}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            {active ? (
              <div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 gap-1 px-2 text-xs"
                  onClick={onReset}
                >
                  <X className="size-3" aria-hidden="true" />
                  {t('data:filter.reset')}
                </Button>
              </div>
            ) : null}
          </PopoverContent>
        </Popover>
      </div>

      {agent !== '' ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="h-7 gap-1 rounded-full px-3 text-xs"
            onClick={() => onAgentChange('')}
            aria-label={t('data:filter.agentChipRemove', { name: agentName })}
          >
            {t('data:filter.agentChip', { name: agentName })}
            <X className="size-3" aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </div>
  )
}
