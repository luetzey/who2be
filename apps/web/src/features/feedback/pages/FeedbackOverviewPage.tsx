import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { FeedbackOverviewItem, FeedbackTarget } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFeedbackOverview } from '@/hooks/useFeedback'

import { FeedbackInbox } from '../components/FeedbackInbox'

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
  const items: FeedbackOverviewItem[] = overview?.items ?? []

  return (
    <Container>
      <PageHeader title={t('overview.title')} description={t('overview.description')} />

      <FeedbackInbox />

      <h2 className="mt-10 mb-4 text-lg font-semibold tracking-tight">
        {t('overview.sectionTitle')}
      </h2>
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
    </Container>
  )
}
