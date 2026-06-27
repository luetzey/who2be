import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type {
  FeedbackItem,
  FeedbackResolution,
  FeedbackSignal,
  FeedbackTarget,
} from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useFeedbackItems } from '@/hooks/useFeedback'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

const DETAIL_SEGMENT: Record<FeedbackTarget, string> = {
  persona: 'personas',
  playbook: 'playbooks',
  resource: 'resources',
}
const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']
const NEGATIVE: readonly FeedbackSignal[] = ['outdated', 'incorrect', 'unclear']
const RESOLUTIONS: readonly FeedbackResolution[] = ['addressed', 'in_progress', 'dismissed']
const TYPES: readonly FeedbackTarget[] = ['persona', 'playbook', 'resource']

// Status-Filter: 'open' = noch nicht triagiert (resolution null).
type StatusFilter = 'open' | FeedbackResolution | 'all'
const STATUS_FILTERS: readonly StatusFilter[] = [
  'open',
  'in_progress',
  'addressed',
  'dismissed',
  'all',
]

function matchesStatus(item: FeedbackItem, status: StatusFilter): boolean {
  if (status === 'all') return true
  if (status === 'open') return item.resolution === null
  return item.resolution === status
}

interface FeedbackInboxProps {
  /** Anzahl ungenutzter Elemente — fuer die KPI-Leiste (aus der Stale-Sicht). */
  unusedCount?: number
}

/**
 * Zentraler Feedback-Posteingang (ADR-0038): KPI-Leiste + Filter + abarbeitbare
 * Liste aller Einzel-Feedbacks mit Inline-Triage. Editor-gated; die Page rendert
 * das nur fuer editor+.
 */
export function FeedbackInbox({ unusedCount }: FeedbackInboxProps) {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { data, loading, error, setResolution } = useFeedbackItems()
  const [status, setStatus] = useState<StatusFilter>('open')
  const [signal, setSignal] = useState<FeedbackSignal | 'all'>('all')
  const [type, setType] = useState<FeedbackTarget | 'all'>('all')

  const counts = data?.counts
  const items = (data?.items ?? []).filter(
    (i) =>
      matchesStatus(i, status) &&
      (signal === 'all' || i.signal === signal) &&
      (type === 'all' || i.entity_type === type),
  )

  const onResolution = async (id: string, value: string) => {
    if (value === '') return
    try {
      await setResolution(id, value as FeedbackResolution)
    } catch {
      notify.error(t('resolution.error'))
    }
  }

  // KPI-Karten: die ersten drei setzen den Status-Filter; Ungenutzt ist rein
  // informativ (gehoert in den Ueberblick).
  const kpis: { key: string; label: string; value: number; filter?: StatusFilter }[] = [
    { key: 'open', label: t('inbox.kpi.open'), value: counts?.open ?? 0, filter: 'open' },
    {
      key: 'in_progress',
      label: t('inbox.kpi.inProgress'),
      value: counts?.in_progress ?? 0,
      filter: 'in_progress',
    },
    {
      key: 'addressed',
      label: t('inbox.kpi.addressed'),
      value: counts?.addressed ?? 0,
      filter: 'addressed',
    },
    { key: 'unused', label: t('inbox.kpi.unused'), value: unusedCount ?? 0 },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* KPI-Leiste */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => {
          const filter = kpi.filter
          const content = (
            <>
              <span className="text-2xl font-semibold tabular-nums">{kpi.value}</span>
              <span className="text-sm text-muted-foreground">{kpi.label}</span>
            </>
          )
          return filter !== undefined ? (
            <Button
              key={kpi.key}
              type="button"
              variant="ghost"
              onClick={() => setStatus(filter)}
              className={cn(
                'flex h-auto flex-col items-start gap-1 rounded-lg border p-4 whitespace-normal',
                status === filter && 'border-brand bg-accent',
              )}
            >
              {content}
            </Button>
          ) : (
            <div
              key={kpi.key}
              className="flex flex-col gap-1 rounded-lg border p-4 text-left"
            >
              {content}
            </div>
          )
        })}
      </div>

      {/* Filterleiste */}
      <div className="flex flex-wrap items-end gap-3">
        <Label className="flex flex-col items-start gap-1 text-sm font-normal">
          <span className="text-muted-foreground">{t('inbox.filter.status')}</span>
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value as StatusFilter)}
            className="h-9 w-44"
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s} value={s}>
                {t(`inbox.status.${s}`)}
              </option>
            ))}
          </Select>
        </Label>
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
            onChange={(e) => setType(e.target.value as FeedbackTarget | 'all')}
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
                {items.map((item) => (
                  <li key={item.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={NEGATIVE.includes(item.signal) ? 'destructive' : 'secondary'}
                      >
                        {t(`signal.${item.signal}`)}
                      </Badge>
                      <Link
                        to={wsPath(`/${DETAIL_SEGMENT[item.entity_type]}/${item.entity_id}`)}
                        className="font-medium text-brand hover:underline"
                      >
                        {item.name}
                      </Link>
                      <span className="text-xs text-muted-foreground">
                        {t(`overview.type.${item.entity_type}`)}
                      </span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {item.agent_id !== null ? t('panel.agent') : t('panel.human')} ·{' '}
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {item.note !== null && item.note !== '' ? (
                      <p className="text-sm text-muted-foreground">{item.note}</p>
                    ) : null}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-muted-foreground">{t('resolution.label')}</span>
                      <Select
                        aria-label={`${t('resolution.label')} — ${item.name}`}
                        value={item.resolution ?? ''}
                        onChange={(e) => void onResolution(item.id, e.target.value)}
                        className="h-8 w-40 text-xs"
                      >
                        <option value="">{t('resolution.placeholder')}</option>
                        {RESOLUTIONS.map((r) => (
                          <option key={r} value={r}>
                            {t(`resolution.${r}`)}
                          </option>
                        ))}
                      </Select>
                      <Link
                        to={wsPath(`/${DETAIL_SEGMENT[item.entity_type]}/${item.entity_id}`)}
                        className="text-xs text-brand hover:underline"
                      >
                        {t('inbox.openElement')}
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}
          </DataView>
        </CardContent>
      </Card>
    </div>
  )
}
