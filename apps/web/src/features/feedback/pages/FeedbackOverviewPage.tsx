import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { FeedbackOverviewItem, FeedbackTarget } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFeedbackOverview, useFeedbackUnused } from '@/hooks/useFeedback'

// entity_type → Listen-Pfad-Segment der Detailseite.
const DETAIL_SEGMENT: Record<FeedbackTarget, string> = {
  persona: 'personas',
  playbook: 'playbooks',
  resource: 'resources',
}

export function FeedbackOverviewPage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const { overview, loading, error } = useFeedbackOverview()
  const unusedState = useFeedbackUnused()
  const items: FeedbackOverviewItem[] = overview?.items ?? []
  const unusedItems = unusedState.unused?.items ?? []

  return (
    <Container>
      <PageHeader title={t('overview.title')} description={t('overview.description')} />
      <Card>
        <CardContent className="pt-6">
          <DataView
            loading={loading && overview === null}
            error={error}
            empty={!loading && items.length === 0}
            emptyTitle={t('overview.empty')}
          >
            {items.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('overview.col.name')}</TableHead>
                    <TableHead>{t('overview.col.type')}</TableHead>
                    <TableHead className="text-right">{t('overview.col.usage')}</TableHead>
                    <TableHead className="text-right">{t('overview.col.helpful')}</TableHead>
                    <TableHead className="text-right">{t('overview.col.negative')}</TableHead>
                    <TableHead>{t('overview.col.lastActivity')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={`${item.entity_type}-${item.entity_id}`}>
                      <TableCell>
                        <Link
                          to={wsPath(`/${DETAIL_SEGMENT[item.entity_type]}/${item.entity_id}`)}
                          className="font-medium text-brand hover:underline"
                        >
                          {item.name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {t(`overview.type.${item.entity_type}`)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{item.usage_count}</TableCell>
                      <TableCell className="text-right tabular-nums">{item.helpful_count}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {item.negative_count > 0 ? (
                          <Badge variant="destructive">{item.negative_count}</Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {item.last_activity_at !== null
                          ? new Date(item.last_activity_at).toLocaleString()
                          : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </DataView>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>{t('unused.title')}</CardTitle>
          <p className="text-sm text-muted-foreground">{t('unused.description')}</p>
        </CardHeader>
        <CardContent>
          <DataView
            loading={unusedState.loading && unusedState.unused === null}
            error={unusedState.error}
            empty={!unusedState.loading && unusedItems.length === 0}
            emptyTitle={t('unused.empty')}
          >
            {unusedItems.length > 0 ? (
              <ul className="flex flex-col gap-2">
                {unusedItems.map((item) => (
                  <li
                    key={`${item.entity_type}-${item.entity_id}`}
                    className="flex items-center justify-between gap-2 text-sm"
                  >
                    <Link
                      to={wsPath(`/${DETAIL_SEGMENT[item.entity_type]}/${item.entity_id}`)}
                      className="font-medium text-brand hover:underline"
                    >
                      {item.name}
                    </Link>
                    <span className="text-xs text-muted-foreground">
                      {t(`overview.type.${item.entity_type}`)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </DataView>
        </CardContent>
      </Card>
    </Container>
  )
}
