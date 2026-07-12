import { Bot, User } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type {
  FeedbackEntityType,
  FeedbackItem,
  FeedbackResolution,
  FeedbackSignal,
} from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityCard } from '@/components/data/EntityCard'
import { MetaPill } from '@/components/data/MetaPill'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { useFeedbackItems } from '@/hooks/useFeedback'
import { cn } from '@/lib/utils'

import { entityMeta } from '../lib/entityMeta'

const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']
const NEGATIVE: readonly string[] = ['outdated', 'incorrect', 'unclear']
// Typ-Filter inkl. 'system' (zielloses Plattform-/MCP-Feedback).
const TYPES: readonly FeedbackEntityType[] = ['persona', 'playbook', 'resource', 'system']

// Status-Filter: 'open' = noch nicht triagiert (resolution null).
type StatusFilter = 'open' | FeedbackResolution | 'all'

// Resolution → Status-Token (gleiche Farbsprache wie StatusBadge/§2.4).
const RESOLUTION_TOKEN: Record<'open' | FeedbackResolution, string> = {
  open: 'draft',
  in_progress: 'review',
  addressed: 'active',
  dismissed: 'inactive',
}

function matchesStatus(item: FeedbackItem, status: StatusFilter): boolean {
  if (status === 'all') return true
  if (status === 'open') return item.resolution === null
  return item.resolution === status
}

// Kompaktes Status-Pill (Punkt + Label) fuer den aktuellen Triage-Stand eines
// Feedbacks. Bewusst nur Anzeige — die Triage passiert in der Detailansicht.
function ResolutionBadge({ resolution }: { resolution: FeedbackResolution | null }) {
  const { t } = useTranslation('feedback')
  const key = resolution ?? 'open'
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground">
      <span
        className="inline-block size-2 rounded-full"
        style={{ backgroundColor: `var(--status-${RESOLUTION_TOKEN[key]})` }}
        aria-hidden="true"
      />
      {t(`inbox.status.${key}`)}
    </span>
  )
}

// Segmentierter Status-Chip — gleiche Optik wie ListFilterBar/AgentsPage.
function StatusChip({
  label,
  count,
  token,
  selected,
  onClick,
}: {
  label: string
  count: number
  token?: string
  selected: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={selected ? 'default' : 'outline'}
      aria-pressed={selected}
      onClick={onClick}
      className="h-8 gap-1.5 rounded-full"
    >
      {token ? (
        <span
          className="inline-block size-2 rounded-full"
          style={{ backgroundColor: `var(--status-${token})` }}
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

interface FeedbackInboxProps {
  /** Wird hochgezaehlt, wenn extern (Problem melden) ein Reload noetig ist. */
  reloadNonce?: number
}

/**
 * Zentraler Feedback-Posteingang (ADR-0038): kompakte, scannbare Liste aller
 * Einzel-Feedbacks — pro Zeile nur Grundinfos (Signal, Element, Quelle, Datum,
 * Status). Der eigentliche Feedback-Inhalt + Triage/Loeschen liegen in der
 * Einzel-Feedback-Detailseite (`/feedback/item/:id`), die die Karte oeffnet.
 * Editor-gated; die Page rendert das nur fuer editor+.
 */
export function FeedbackInbox({ reloadNonce }: FeedbackInboxProps) {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { data, loading, error, reload } = useFeedbackItems()
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

  const total =
    (counts?.open ?? 0) +
    (counts?.in_progress ?? 0) +
    (counts?.addressed ?? 0) +
    (counts?.dismissed ?? 0)

  const statusChips: { key: StatusFilter; label: string; count: number; token?: string }[] = [
    { key: 'all', label: t('inbox.status.all'), count: total },
    { key: 'open', label: t('inbox.status.open'), count: counts?.open ?? 0, token: 'draft' },
    {
      key: 'in_progress',
      label: t('inbox.status.in_progress'),
      count: counts?.in_progress ?? 0,
      token: 'review',
    },
    {
      key: 'addressed',
      label: t('inbox.status.addressed'),
      count: counts?.addressed ?? 0,
      token: 'active',
    },
    {
      key: 'dismissed',
      label: t('inbox.status.dismissed'),
      count: counts?.dismissed ?? 0,
      token: 'inactive',
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      {/* Filter-Karte: Status-Chips + Signal-/Typ-Selects (wie die anderen Uebersichten). */}
      <Card>
        <CardContent className="flex flex-col gap-4 pt-6">
          <div
            className="flex flex-wrap items-center gap-2"
            role="group"
            aria-label={t('inbox.filter.statusGroup')}
          >
            {statusChips.map((chip) => (
              <StatusChip
                key={chip.key}
                label={chip.label}
                count={chip.count}
                token={chip.token}
                selected={status === chip.key}
                onClick={() => setStatus(chip.key)}
              />
            ))}
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Label className="flex flex-col items-start gap-1 text-sm font-normal">
              <span className="text-muted-foreground">{t('inbox.filter.signal')}</span>
              <Select
                value={signal}
                onChange={(e) => setSignal(e.target.value as FeedbackSignal | 'all')}
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
        </CardContent>
      </Card>

      {/* Liste: pro Feedback eine kompakte Karte → Detailansicht. */}
      <DataView
        loading={loading && data === null}
        error={error}
        empty={!loading && items.length === 0}
        emptyTitle={t('inbox.empty')}
      >
        {items.length > 0 ? (
          <div className="flex flex-col gap-3">
            {items.map((item) => {
              const meta = entityMeta(item.entity_type)
              const isSystem = item.entity_type === 'system'
              const signalLabel = isSystem
                ? t(`systemCategory.${item.signal}`)
                : t(`signal.${item.signal}`)
              const SourceIcon = item.agent_id !== null ? Bot : User
              return (
                <EntityCard
                  key={item.id}
                  icon={meta.icon}
                  iconTone={meta.tone}
                  title={item.name}
                  href={wsPath(`/feedback/item/${item.id}`)}
                  badges={
                    <Badge variant={NEGATIVE.includes(item.signal) || isSystem ? 'destructive' : 'secondary'}>
                      <span
                        className="mr-1 inline-block size-1.5 rounded-full bg-current"
                        aria-hidden="true"
                      />
                      {signalLabel}
                    </Badge>
                  }
                  status={<ResolutionBadge resolution={item.resolution} />}
                  meta={
                    <>
                      <MetaPill icon={SourceIcon}>
                        {item.agent_id !== null ? t('panel.agent') : t('panel.human')} ·{' '}
                        {new Date(item.created_at).toLocaleDateString()}
                      </MetaPill>
                      <MetaPill>{t(`overview.type.${item.entity_type}`)}</MetaPill>
                    </>
                  }
                />
              )
            })}
          </div>
        ) : null}
      </DataView>
    </div>
  )
}
