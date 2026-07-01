import { AlertCircle, Search, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  LIST_STATUSES,
  type StatusCounts,
  type StatusFilterValue,
} from '@/lib/listFilter'

interface ListFilterBarProps {
  counts: StatusCounts
  status: StatusFilterValue
  onStatusChange: (value: StatusFilterValue) => void
  query: string
  onQueryChange: (value: string) => void
  active: boolean
  onReset: () => void
  // Kombinierbare Facetten (optional je Liste).
  availableTags?: string[]
  tag?: string
  onTagChange?: (value: string) => void
  availableTypes?: string[]
  type?: string
  onTypeChange?: (value: string) => void
  // Uebersetzte Typ-Labels (z. B. Playbook-Typen) — Fallback: Rohwert.
  typeLabel?: (value: string) => string
  idPrefix: string
}

function StatusChip({
  value,
  label,
  count,
  selected,
  accent,
  onClick,
}: {
  value: StatusFilterValue
  label: string
  count: number
  selected: boolean
  accent: boolean
  onClick: () => void
}) {
  const isStatus = value !== 'all' && value !== 'attention'
  return (
    <Button
      type="button"
      size="sm"
      variant={selected ? (accent ? 'brand' : 'default') : 'outline'}
      aria-pressed={selected}
      onClick={onClick}
      className="h-8 gap-1.5 rounded-full"
    >
      {accent ? <AlertCircle className="size-3.5" aria-hidden="true" /> : null}
      {isStatus ? (
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: `var(--status-${value})` }}
          aria-hidden="true"
        />
      ) : null}
      <span>{label}</span>
      <span className={cn('tabular-nums', selected ? 'opacity-90' : 'text-muted-foreground')}>
        {count}
      </span>
    </Button>
  )
}

export function ListFilterBar({
  counts,
  status,
  onStatusChange,
  query,
  onQueryChange,
  active,
  onReset,
  availableTags = [],
  tag = '',
  onTagChange,
  availableTypes = [],
  type = '',
  onTypeChange,
  typeLabel,
  idPrefix,
}: ListFilterBarProps) {
  const { t } = useTranslation(['data', 'common'])

  // Status-Chips: `all` immer, `attention` sobald es welche gibt (oder aktiv),
  // ein Status-Chip nur bei Vorkommen (oder wenn aktuell gewaehlt). Vermeidet
  // Null-Zaehler-Rauschen, haelt aber die aktive Auswahl sichtbar.
  const showAttention = counts.attention > 0 || status === 'attention'

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 pt-6">
        <div
          className="flex flex-wrap items-center gap-2"
          role="group"
          aria-label={t('data:filter.statusGroup')}
        >
          <StatusChip
            value="all"
            label={t('data:filter.all')}
            count={counts.all}
            selected={status === 'all'}
            accent={false}
            onClick={() => onStatusChange('all')}
          />
          {showAttention ? (
            <StatusChip
              value="attention"
              label={t('data:filter.attention')}
              count={counts.attention}
              selected={status === 'attention'}
              accent
              onClick={() => onStatusChange('attention')}
            />
          ) : null}
          {LIST_STATUSES.filter((s) => counts[s] > 0 || status === s).map((s) => (
            <StatusChip
              key={s}
              value={s}
              label={t(`common:status.${s}`)}
              count={counts[s]}
              selected={status === s}
              accent={false}
              onClick={() => onStatusChange(s)}
            />
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="flex flex-col gap-2">
            <Label htmlFor={`${idPrefix}-search`}>{t('data:filter.searchLabel')}</Label>
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id={`${idPrefix}-search`}
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder={t('data:filter.searchPlaceholder')}
                className="pl-9"
              />
            </div>
          </div>

          {onTagChange && availableTags.length > 0 ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor={`${idPrefix}-tag`}>{t('data:filter.tagLabel')}</Label>
              <Select
                id={`${idPrefix}-tag`}
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

          {onTypeChange && availableTypes.length > 0 ? (
            <div className="flex flex-col gap-2">
              <Label htmlFor={`${idPrefix}-type`}>{t('data:filter.typeLabel')}</Label>
              <Select
                id={`${idPrefix}-type`}
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
        </div>

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
      </CardContent>
    </Card>
  )
}
