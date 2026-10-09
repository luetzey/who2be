import { Bot, Search, User } from 'lucide-react'
import { useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import type {
  FeedbackEntityType,
  FeedbackItem,
  FeedbackResolution,
  FeedbackSignal,
} from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { MetaPill } from '@/components/data/MetaPill'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useFeedbackItems } from '@/hooks/useFeedback'
import type { FacetSpec, StatusChipOption } from '@/lib/listFilter'

import { entityMeta } from '../lib/entityMeta'

const SIGNALS: readonly FeedbackSignal[] = ['helpful', 'outdated', 'incorrect', 'unclear']
const NEGATIVE: readonly string[] = ['outdated', 'incorrect', 'unclear']
// Typ-Filter inkl. 'system' (zielloses Plattform-/MCP-Feedback).
const TYPES: readonly FeedbackEntityType[] = ['persona', 'playbook', 'resource', 'system']

// Status-Filter: 'open' = noch nicht triagiert (resolution null). Reihenfolge
// = Chip-Reihenfolge (Lebenszyklus); Standard ist „Offen“.
type StatusFilter = 'open' | FeedbackResolution | 'all'
const STATUS_VALUES: readonly StatusFilter[] = [
  'all',
  'open',
  'in_progress',
  'addressed',
  'dismissed',
]
const DEFAULT_STATUS: StatusFilter = 'open'
// URL-Parameter dieser Liste; `tab` gehoert der Seite und bleibt stehen.
const FILTER_KEYS = ['status', 'signal', 'type', 'q'] as const

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

function isStatusFilter(value: string | null): value is StatusFilter {
  return value !== null && (STATUS_VALUES as readonly string[]).includes(value)
}

function isSignal(value: string | null): value is FeedbackSignal {
  return value !== null && (SIGNALS as readonly string[]).includes(value)
}

function isType(value: string | null): value is FeedbackEntityType {
  return value !== null && (TYPES as readonly string[]).includes(value)
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
 *
 * Filter nach Filter-Standard (G1) ueber die gemeinsame `ListFilterBar`:
 * Status-Chips, Suche nach Elementname, Facetten Signal und Typ. Die API
 * liefert den (gekappten) Posteingang ohne Paginierung auf einmal, deshalb
 * filtert die Seite clientseitig. Die Chip-Zahlen rechnet sie ueber die nach
 * Suche und Facetten eingegrenzte Menge — die Zahl zeigt, was ein Klick ergaebe.
 */
export function FeedbackInbox({ reloadNonce }: FeedbackInboxProps) {
  const { t } = useTranslation(['feedback', 'data'])
  const wsPath = useWorkspacePath()
  const { data, loading, error, reload } = useFeedbackItems()

  // Filter-Standard §2.1 Punkt 9: jeder Filterwert steht in der URL (neben
  // `tab`), per `replace` geschrieben; der Standard „Offen“ fehlt darin.
  const [params, setParams] = useSearchParams()
  const rawStatus = params.get('status')
  const status: StatusFilter = isStatusFilter(rawStatus) ? rawStatus : DEFAULT_STATUS
  const rawSignal = params.get('signal')
  const signal: FeedbackSignal | '' = isSignal(rawSignal) ? rawSignal : ''
  const rawType = params.get('type')
  const type: FeedbackEntityType | '' = isType(rawType) ? rawType : ''
  const query = params.get('q') ?? ''

  const setParam = useCallback(
    (key: string, value: string) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          if (value === '' || (key === 'status' && value === DEFAULT_STATUS)) next.delete(key)
          else next.set(key, value)
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )
  const reset = useCallback(() => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const key of FILTER_KEYS) next.delete(key)
        return next
      },
      { replace: true },
    )
  }, [setParams])

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

  const all = data?.items ?? []
  const needle = query.trim().toLocaleLowerCase()
  // Basismenge fuer die Chip-Zahlen: Suche und Facetten, aber nicht Status.
  const base = all.filter(
    (i) =>
      (signal === '' || i.signal === signal) &&
      (type === '' || i.entity_type === type) &&
      (needle === '' || i.name.toLocaleLowerCase().includes(needle)),
  )
  const items = base.filter((i) => matchesStatus(i, status))

  const active = status !== DEFAULT_STATUS || signal !== '' || type !== '' || query !== ''

  // Generische Status-Chips (E1). 0er-Chips entfallen, ausser „Alle“ und der
  // Standard „Offen“; den gewaehlten Chip haelt die Leiste selbst.
  const statusOptions: StatusChipOption[] = STATUS_VALUES.map((value) => ({
    value,
    label: value === 'all' ? t('data:filter.all') : t(`feedback:inbox.status.${value}`),
    count: base.filter((i) => matchesStatus(i, value)).length,
    token: value === 'all' ? undefined : RESOLUTION_TOKEN[value],
    keepWhenZero: value === 'all' || value === DEFAULT_STATUS,
  }))

  // Reihenfolge §2.1 Punkt 3: fachliche Facetten der Liste (kein Agent, kein
  // Tag, keine Sprache — der Posteingang kennt sie nicht).
  const facets: FacetSpec[] = [
    {
      key: 'signal',
      label: t('feedback:inbox.filter.signal'),
      allLabel: t('feedback:inbox.filter.allSignals'),
      options: SIGNALS.map((value) => ({ value, label: t(`feedback:signal.${value}`) })),
      value: signal,
      onChange: (value) => setParam('signal', value),
    },
    {
      key: 'type',
      label: t('feedback:inbox.filter.type'),
      allLabel: t('feedback:inbox.filter.allTypes'),
      options: TYPES.map((value) => ({ value, label: t(`feedback:overview.type.${value}`) })),
      value: type,
      onChange: (value) => setParam('type', value),
    },
  ]

  // Keine Daten ueberhaupt: eigener Leerzustand, die Leiste entfaellt
  // (Filter-Standard §2.3). Waehrend des Ladens und bei Fehlern bleibt sie.
  const nothingAtAll = data !== null && all.length === 0 && !active

  let empty = null
  if (data !== null && items.length === 0) {
    if (nothingAtAll) {
      empty = <EmptyState title={t('feedback:overview.empty')} />
    } else if (active) {
      empty = (
        <EmptyState
          icon={Search}
          title={t('data:filter.emptyFilteredTitle')}
          description={t('data:filter.emptyFilteredDescription')}
          action={
            <Button type="button" variant="outline" onClick={reset}>
              {t('data:filter.reset')}
            </Button>
          }
        />
      )
    } else {
      // Standard „Offen“ ohne Treffer: „Alles erledigt“, kein Zuruecksetzen.
      empty = (
        <EmptyState
          title={t('feedback:inbox.emptyOpenTitle')}
          description={t('feedback:inbox.emptyOpenDescription')}
        />
      )
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {nothingAtAll ? null : (
        <ListFilterBar
          idPrefix="feedback-inbox"
          statusOptions={statusOptions}
          status={status}
          onStatusChange={(value) => setParam('status', value)}
          query={query}
          onQueryChange={(value) => setParam('q', value)}
          searchPlaceholder={t('feedback:inbox.filter.searchPlaceholder')}
          facets={facets}
          active={active}
          onReset={reset}
          resultCount={data === null ? null : items.length}
        />
      )}

      {/* Liste: pro Feedback eine kompakte Karte → Detailansicht. */}
      <DataView loading={loading && data === null} error={error}>
        {empty ?? (
          <div className="flex flex-col gap-3">
            {items.map((item) => {
              const meta = entityMeta(item.entity_type)
              const isSystem = item.entity_type === 'system'
              const signalLabel = isSystem
                ? t(`feedback:systemCategory.${item.signal}`)
                : t(`feedback:signal.${item.signal}`)
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
                        {item.agent_id !== null ? t('feedback:panel.agent') : t('feedback:panel.human')} ·{' '}
                        {new Date(item.created_at).toLocaleDateString()}
                      </MetaPill>
                      <MetaPill>{t(`feedback:overview.type.${item.entity_type}`)}</MetaPill>
                    </>
                  }
                />
              )
            })}
          </div>
        )}
      </DataView>
    </div>
  )
}
