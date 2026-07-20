import { ChevronRight, Inbox, ThumbsUp, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { FeedbackOverviewItem } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EntityIcon } from '@/components/data'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useFeedbackOverview } from '@/hooks/useFeedback'
import { cn } from '@/lib/utils'

import { FeedbackInbox } from '../components/FeedbackInbox'
import { ReportProblemDialog } from '../components/ReportProblemDialog'
import { entityMeta } from '../lib/entityMeta'

type SortMode = 'care' | 'usage' | 'activity'

const MAX_COLLAPSED = 8

function lastActivityValue(item: FeedbackOverviewItem): number {
  return item.last_activity_at !== null ? new Date(item.last_activity_at).getTime() : 0
}

export function FeedbackOverviewPage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { overview, loading, error, reload } = useFeedbackOverview()
  const [reloadNonce, setReloadNonce] = useState(0)
  const [sort, setSort] = useState<SortMode>('care')
  const [careOnly, setCareOnly] = useState(false)
  const [showAll, setShowAll] = useState(false)

  const items: FeedbackOverviewItem[] = overview?.items ?? []

  const sorted = useMemo(() => {
    let list = items.slice()
    if (careOnly) list = list.filter((i) => i.negative_count > 0)
    list.sort((a, b) => {
      if (sort === 'care') {
        return b.negative_count - a.negative_count || b.usage_count - a.usage_count
      }
      if (sort === 'usage') return b.usage_count - a.usage_count
      return lastActivityValue(b) - lastActivityValue(a)
    })
    return list
  }, [items, sort, careOnly])

  const visible = showAll ? sorted : sorted.slice(0, MAX_COLLAPSED)

  // Nach „Problem melden" beide Sichten auffrischen (Uebersicht + Posteingang).
  const onReported = () => {
    reload()
    setReloadNonce((n) => n + 1)
  }

  const sortModes: { key: SortMode; label: string }[] = [
    { key: 'care', label: t('overview.sortCare') },
    { key: 'usage', label: t('overview.sortUsage') },
    { key: 'activity', label: t('overview.sortActivity') },
  ]

  return (
    <Container>
      <PageHeader
        title={t('overview.title')}
        description={t('overview.description')}
        actions={<ReportProblemDialog onReported={onReported} />}
      />

      {/* Posteingang (Einzel-Feedbacks) und Kuration (Aggregat pro Element)
          liegen in Tabs — pro Ansicht nur eine Liste, deutlich uebersichtlicher. */}
      <div className="mt-6">
        <Tabs defaultValue="inbox">
          <TabsList>
            <TabsTrigger value="inbox">
              <Inbox className="size-4" aria-hidden="true" />
              {t('overview.tabs.inbox')}
            </TabsTrigger>
            <TabsTrigger value="curation">
              <TriangleAlert className="size-4" aria-hidden="true" />
              {t('overview.tabs.curation')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="inbox" className="mt-6">
            <FeedbackInbox reloadNonce={reloadNonce} />
          </TabsContent>

          <TabsContent value="curation" className="mt-6">
            <section className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">{t('overview.curationDescription')}</p>

              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  {t('overview.sort')}
                </span>
                <span className="inline-flex gap-0.5 rounded-lg bg-muted p-1">
                  {sortModes.map((mode) => (
                    <Button
                      key={mode.key}
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-pressed={sort === mode.key}
                      onClick={() => setSort(mode.key)}
                      className={cn(
                        'h-8 rounded-md px-3 text-xs font-medium',
                        sort === mode.key
                          ? 'bg-card text-foreground shadow-card'
                          : 'text-muted-foreground hover:bg-transparent hover:text-foreground',
                      )}
                    >
                      {mode.label}
                    </Button>
                  ))}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-pressed={careOnly}
                  onClick={() => {
                    setCareOnly((v) => !v)
                    setShowAll(false)
                  }}
                  className={cn(
                    'ml-auto',
                    careOnly &&
                      'border-destructive/40 bg-destructive/10 text-destructive hover:text-destructive',
                  )}
                >
                  <TriangleAlert />
                  {t('overview.careOnly')}
                </Button>
              </div>

              <Card>
                <CardContent className="p-0">
                  <DataView
                    loading={loading && overview === null}
                    error={error}
                    empty={!loading && sorted.length === 0}
                    emptyTitle={careOnly ? t('overview.careEmpty') : t('overview.empty')}
                  >
                    {sorted.length > 0 ? (
                      <>
                        <ul className="flex flex-col divide-y">
                          {visible.map((item) => {
                            const meta = entityMeta(item.entity_type)
                            const signalTotal = item.helpful_count + item.negative_count
                            const helpfulPct =
                              signalTotal > 0 ? (item.helpful_count / signalTotal) * 100 : 0
                            const negativePct = signalTotal > 0 ? 100 - helpfulPct : 0
                            return (
                              <li key={`${item.entity_type}-${item.entity_id}`} className="relative">
                                <div
                                  className={cn(
                                    'flex items-center gap-4 border-l-2 py-3 pr-4 pl-3 transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/40',
                                    item.negative_count >= 3
                                      ? 'border-l-destructive'
                                      : item.negative_count > 0
                                        ? 'border-l-brand'
                                        : 'border-l-transparent',
                                  )}
                                >
                                  <span className="flex w-52 min-w-0 flex-none items-center gap-2.5">
                                    <EntityIcon icon={meta.icon} tone={meta.tone} size="sm" />
                                    <span className="min-w-0">
                                      <Link
                                        to={wsPath(`/feedback/${item.entity_type}/${item.entity_id}`)}
                                        state={{ name: item.name }}
                                        className="block truncate rounded-sm font-medium text-foreground after:absolute after:inset-0 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                                      >
                                        {item.name}
                                      </Link>
                                      <span className="block text-xs text-muted-foreground">
                                        {t(`overview.type.${item.entity_type}`)} ·{' '}
                                        {t('tiles.usageUnit', { count: item.usage_count })}
                                      </span>
                                    </span>
                                  </span>
                                  {/* min-w-[7.5rem]: funktionale Mindestbreite, damit der
                                      Signal-Balken auch bei schmalen Viewports lesbar bleibt —
                                      die Spacing-Skala kennt diesen Wert nicht (§4.1). */}
                                  <span className="flex min-w-[7.5rem] flex-1 flex-col gap-1.5">
                                    <span className="flex h-1.5 overflow-hidden rounded-full bg-muted">
                                      <span className="bg-brand" style={{ width: `${helpfulPct}%` }} />
                                      <span
                                        className="bg-destructive"
                                        style={{ width: `${negativePct}%` }}
                                      />
                                    </span>
                                    <span className="flex gap-3 text-xs text-muted-foreground">
                                      <span className="inline-flex items-center gap-1">
                                        <ThumbsUp className="size-4" aria-hidden="true" />
                                        {t('overview.helpfulShort', { count: item.helpful_count })}
                                      </span>
                                      <span
                                        className={cn(
                                          'inline-flex items-center gap-1',
                                          item.negative_count > 0
                                            ? 'text-destructive'
                                            : 'text-muted-foreground',
                                        )}
                                      >
                                        <TriangleAlert className="size-4" aria-hidden="true" />
                                        {t('overview.negativeShort', { count: item.negative_count })}
                                      </span>
                                    </span>
                                  </span>
                                  <span className="w-24 flex-none text-right text-xs text-muted-foreground">
                                    {item.last_activity_at !== null
                                      ? new Date(item.last_activity_at).toLocaleDateString()
                                      : '—'}
                                  </span>
                                  <ChevronRight
                                    className="size-4 flex-none text-muted-foreground/60"
                                    aria-hidden="true"
                                  />
                                </div>
                              </li>
                            )
                          })}
                        </ul>
                        {sorted.length > MAX_COLLAPSED ? (
                          <Button
                            type="button"
                            variant="link"
                            onClick={() => setShowAll((v) => !v)}
                            className="w-full rounded-none border-t text-xs font-medium"
                          >
                            {showAll
                              ? t('overview.showLess')
                              : t('overview.showAll', { count: sorted.length })}
                          </Button>
                        ) : null}
                      </>
                    ) : null}
                  </DataView>
                </CardContent>
              </Card>
            </section>
          </TabsContent>
        </Tabs>
      </div>
    </Container>
  )
}
