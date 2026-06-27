import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { FeedbackOverviewItem, FeedbackTarget } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useFeedbackOverview } from '@/hooks/useFeedback'

const DETAIL_SEGMENT: Record<FeedbackTarget, string> = {
  persona: 'personas',
  playbook: 'playbooks',
  resource: 'resources',
}
const TILE_LIMIT = 3

interface TileProps {
  title: string
  items: FeedbackOverviewItem[]
  metric: (item: FeedbackOverviewItem) => string
  emptyLabel: string
}

function Tile({ title, items, metric, emptyLabel }: TileProps) {
  const wsPath = useWorkspacePath()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {items.map((item) => (
              <li
                key={`${item.entity_type}-${item.entity_id}`}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <Link
                  to={wsPath(`/${DETAIL_SEGMENT[item.entity_type]}/${item.entity_id}`)}
                  className="truncate font-medium text-brand hover:underline"
                >
                  {item.name}
                </Link>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {metric(item)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Zwei Kurations-Kacheln fuers Dashboard: meistgenutzte Elemente und die am
 * haeufigsten bemaengelten (negative Signale). Speist sich aus der
 * workspace-weiten Feedback-Uebersicht; editor-gated (Mount nur fuer editor+).
 */
export function FeedbackTiles() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { overview } = useFeedbackOverview()
  const items = overview?.items ?? []

  // Backend liefert nach last_activity sortiert — fuer die Kacheln re-sortieren.
  const mostUsed = [...items]
    .filter((i) => i.usage_count > 0)
    .sort((a, b) => b.usage_count - a.usage_count)
    .slice(0, TILE_LIMIT)
  const mostFlagged = [...items]
    .filter((i) => i.negative_count > 0)
    .sort((a, b) => b.negative_count - a.negative_count)
    .slice(0, TILE_LIMIT)

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <CardTitle className="text-base">{t('overview.title')}</CardTitle>
        <Link to={wsPath('/feedback')} className="text-sm text-brand hover:underline">
          {t('tiles.viewAll')}
        </Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Tile
          title={t('tiles.mostUsed')}
          items={mostUsed}
          metric={(item) => t('tiles.usageUnit', { count: item.usage_count })}
          emptyLabel={t('tiles.empty')}
        />
        <Tile
          title={t('tiles.mostFlagged')}
          items={mostFlagged}
          metric={(item) => t('tiles.negativeUnit', { count: item.negative_count })}
          emptyLabel={t('tiles.empty')}
        />
      </div>
    </section>
  )
}
