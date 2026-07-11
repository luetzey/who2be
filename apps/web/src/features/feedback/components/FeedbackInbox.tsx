import { Archive, Bot, CircleCheckBig, Clock, Inbox, List, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type {
  FeedbackEntityType,
  FeedbackItem,
  FeedbackResolution,
  FeedbackSignal,
  FeedbackTarget,
} from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityIcon } from '@/components/data'
import { DeleteFeedbackButton } from '@/components/feedback/DeleteFeedbackButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useFeedbackItems } from '@/hooks/useFeedback'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import { DETAIL_SEGMENT, entityMeta } from '../lib/entityMeta'
import { ResolutionSegments } from './ResolutionSegments'

const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']
const NEGATIVE: readonly string[] = ['outdated', 'incorrect', 'unclear']
// Typ-Filter inkl. 'system' (zielloses Plattform-/MCP-Feedback).
const TYPES: readonly FeedbackEntityType[] = ['persona', 'playbook', 'resource', 'system']

// Status-Filter: 'open' = noch nicht triagiert (resolution null).
type StatusFilter = 'open' | FeedbackResolution | 'all'

function matchesStatus(item: FeedbackItem, status: StatusFilter): boolean {
  if (status === 'all') return true
  if (status === 'open') return item.resolution === null
  return item.resolution === status
}

interface FeedbackInboxProps {
  /** Wird hochgezaehlt, wenn extern (Problem melden) ein Reload noetig ist. */
  reloadNonce?: number
}

/**
 * Zentraler Feedback-Posteingang (ADR-0038): KPI-Kachelleiste (als Status-Filter)
 * + Signal-/Typ-Filter + abarbeitbare Liste aller Einzel-Feedbacks mit
 * Inline-Triage. Editor-gated; die Page rendert das nur fuer editor+.
 */
export function FeedbackInbox({ reloadNonce }: FeedbackInboxProps) {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { data, loading, error, setResolution, deleteFeedback, reload } = useFeedbackItems()
  const [status, setStatus] = useState<StatusFilter>('open')
  const [signal, setSignal] = useState<FeedbackSignal | 'all'>('all')
  const [type, setType] = useState<FeedbackEntityType | 'all'>('all')

  // Externer Reload-Trigger (z. B. nach „Problem melden" im PageHeader) — der
  // Erst-Render laedt bereits ueber den Hook, daher hier ueberspringen.
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    reload()
  }, [reloadNonce, reload])

  const counts = data?.counts
  const items = (data?.items ?? []).filter(
    (i) =>
      matchesStatus(i, status) &&
      (signal === 'all' || i.signal === signal) &&
      (type === 'all' || i.entity_type === type),
  )

  const onResolution = async (id: string, value: FeedbackResolution) => {
    try {
      await setResolution(id, value)
    } catch {
      notify.error(t('resolution.error'))
    }
  }

  const total =
    (counts?.open ?? 0) +
    (counts?.in_progress ?? 0) +
    (counts?.addressed ?? 0) +
    (counts?.dismissed ?? 0)

  // KPI-Kacheln setzen den Status-Filter (active = border-brand bg-accent).
  const tiles: {
    key: StatusFilter
    label: string
    value: number
    icon: typeof Inbox
    tone: string
  }[] = [
    { key: 'open', label: t('inbox.kpi.open'), value: counts?.open ?? 0, icon: Inbox, tone: 'bg-brand/10 text-brand' },
    {
      key: 'in_progress',
      label: t('inbox.kpi.inProgress'),
      value: counts?.in_progress ?? 0,
      icon: Clock,
      tone: 'bg-pill-date text-pill-date-fg',
    },
    {
      key: 'addressed',
      label: t('inbox.kpi.addressed'),
      value: counts?.addressed ?? 0,
      icon: CircleCheckBig,
      tone: 'bg-pill-resource text-pill-resource-fg',
    },
  ]
  const chips: { key: StatusFilter; label: string; value: number; icon: typeof Archive }[] = [
    { key: 'dismissed', label: t('inbox.status.dismissed'), value: counts?.dismissed ?? 0, icon: Archive },
    { key: 'all', label: t('inbox.status.all'), value: total, icon: List },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* KPI-Kacheln + Verworfen/Alle-Chips — klickbar als Status-Filter. */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[repeat(3,1fr)_10rem]">
        {tiles.map((tile) => {
          const Icon = tile.icon
          return (
            <Button
              key={tile.key}
              type="button"
              variant="ghost"
              onClick={() => setStatus(tile.key)}
              className={cn(
                'flex h-auto items-center justify-start gap-3.5 rounded-xl border bg-card p-4 text-left shadow-card hover:shadow-popover',
                status === tile.key && 'border-brand bg-accent',
              )}
            >
              <span
                className={cn(
                  'inline-flex size-10 flex-none items-center justify-center rounded-lg',
                  tile.tone,
                )}
              >
                <Icon aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-2xl font-semibold tracking-tight tabular-nums">
                  {tile.value}
                </span>
                <span className="block text-xs font-normal text-muted-foreground">{tile.label}</span>
              </span>
            </Button>
          )
        })}
        <div className="flex flex-col gap-3">
          {chips.map((chip) => {
            const Icon = chip.icon
            return (
              <Button
                key={chip.key}
                type="button"
                variant="ghost"
                onClick={() => setStatus(chip.key)}
                className={cn(
                  'flex flex-1 items-center justify-between gap-2 rounded-lg border bg-card px-3 text-xs font-medium shadow-card hover:shadow-popover',
                  status === chip.key && 'border-brand bg-accent',
                )}
              >
                <span className="inline-flex items-center gap-2">
                  <Icon className="text-muted-foreground" aria-hidden="true" />
                  {chip.label}
                </span>
                <span className="tabular-nums text-muted-foreground">{chip.value}</span>
              </Button>
            )
          })}
        </div>
      </div>

      {/* Signal-/Typ-Filter (Status kommt jetzt aus den Kacheln). */}
      <div className="flex flex-wrap items-end gap-3">
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="text-muted-foreground">{t('inbox.filter.signal')}</span>
          <Select
            value={signal}
            onChange={(e) => setSignal(e.target.value as FeedbackSignal | 'all')}
            className="h-9 w-40"
          >
            <option value="all">{t('inbox.filter.allSignals')}</option>
            {SIGNALS.map((s) => (
              <option key={s} value={s}>
                {t(`signal.${s}`)}
              </option>
            ))}
          </Select>
        </Label>
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="text-muted-foreground">{t('inbox.filter.type')}</span>
          <Select
            value={type}
            onChange={(e) => setType(e.target.value as FeedbackEntityType | 'all')}
            className="h-9 w-40"
          >
            <option value="all">{t('inbox.filter.allTypes')}</option>
            {TYPES.map((ty) => (
              <option key={ty} value={ty}>
                {t(`overview.type.${ty}`)}
              </option>
            ))}
          </Select>
        </Label>
      </div>

      {/* Liste */}
      <Card>
        <CardContent className="pt-6">
          <DataView
            loading={loading && data === null}
            error={error}
            empty={!loading && items.length === 0}
            emptyTitle={t('inbox.empty')}
          >
            {items.length > 0 ? (
              <ul className="flex flex-col divide-y">
                {items.map((item) => {
                  const meta = entityMeta(item.entity_type)
                  const isSystem = item.entity_type === 'system'
                  // System-Feedback hat kein Element → kein Detail-Link; das
                  // signal-Feld traegt dann die Kategorie statt eines Signals.
                  const detailPath = isSystem
                    ? null
                    : wsPath(
                        `/${DETAIL_SEGMENT[item.entity_type as FeedbackTarget]}/${item.entity_id}`,
                      )
                  const signalLabel = isSystem
                    ? t(`systemCategory.${item.signal}`)
                    : t(`signal.${item.signal}`)
                  const SourceIcon = item.agent_id !== null ? Bot : User
                  return (
                    <li key={item.id} className="flex flex-col gap-2.5 py-4 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                        <Badge
                          variant={
                            NEGATIVE.includes(item.signal) || isSystem ? 'destructive' : 'secondary'
                          }
                        >
                          <span className="mr-1 inline-block size-1.5 rounded-full bg-current" aria-hidden="true" />
                          {signalLabel}
                        </Badge>
                        <span className="inline-flex min-w-0 items-center gap-2">
                          <EntityIcon icon={meta.icon} tone={meta.tone} size="sm" />
                          {detailPath !== null ? (
                            <Link
                              to={detailPath}
                              className="truncate font-medium text-foreground hover:underline"
                            >
                              {item.name}
                            </Link>
                          ) : (
                            <span className="truncate font-medium">{item.name}</span>
                          )}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {t(`overview.type.${item.entity_type}`)}
                        </span>
                        <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                          <SourceIcon className="size-3.5" aria-hidden="true" />
                          {item.agent_id !== null ? t('panel.agent') : t('panel.human')} ·{' '}
                          {new Date(item.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {item.note !== null && item.note !== '' ? (
                        <p className="border-l-2 border-border pl-3 text-sm text-foreground/90">
                          {item.note}
                        </p>
                      ) : null}
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                          {t('resolution.label')}
                        </span>
                        <ResolutionSegments
                          name={item.name}
                          value={item.resolution}
                          onChange={(r) => void onResolution(item.id, r)}
                        />
                        {detailPath !== null ? (
                          <Link to={detailPath} className="text-xs font-medium text-brand hover:underline">
                            {t('inbox.openElement')}
                          </Link>
                        ) : null}
                        <div className="ml-auto">
                          <DeleteFeedbackButton
                            entityName={item.name}
                            onConfirm={() => deleteFeedback(item.id)}
                          />
                        </div>
                      </div>
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </DataView>
        </CardContent>
      </Card>
    </div>
  )
}
