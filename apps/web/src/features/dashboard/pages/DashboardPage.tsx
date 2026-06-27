import { BookOpen, ClipboardCheck, LayoutDashboard, Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { FeedbackTiles } from '@/components/feedback/FeedbackTiles'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { ActivityRow } from '../components/ActivityRow'
import { KpiCard } from '../components/KpiCard'
import { PaginationControls } from '../components/PaginationControls'
import { StatusDonut } from '../components/StatusDonut'
import { useDashboard } from '../hooks/useDashboard'

export function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const role = useCurrentWorkspaceRole()
  const { data, loading, error, notFound, preparing, page, setPage } = useDashboard()

  const pagination = data?.activity_pagination
  const totalPages = pagination?.total_pages ?? 1

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.title')}
          description={t('page.description')}
        />

        {preparing ? (
          <EmptyState
            icon={LayoutDashboard}
            title={t('preparing.title')}
            description={t('preparing.description')}
          />
        ) : notFound ? (
          <EmptyState
            icon={LayoutDashboard}
            title={t('notFound.title')}
            description={t('notFound.description')}
          />
        ) : (
          <DataView loading={loading && data === null} error={error}>
            {data !== null ? (
              <Stack gap="lg">
                <section
                  className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                  aria-label={t('kpis.ariaLabel')}
                >
                  <KpiCard
                    label={t('kpis.activePersonas')}
                    value={data.kpis.active_personas}
                    icon={Users}
                  />
                  <KpiCard
                    label={t('kpis.activePlaybooks')}
                    value={data.kpis.active_playbooks}
                    icon={BookOpen}
                  />
                  <KpiCard
                    label={t('common:status.review')}
                    value={data.kpis.pending_reviews}
                    icon={ClipboardCheck}
                    description={t('kpis.pendingReviewsDescription')}
                  />
                </section>

                {role !== 'viewer' ? <FeedbackTiles /> : null}

                <Card>
                  <CardHeader>
                    <CardTitle>{t('statusDistribution.title')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                      <StatusDonut
                        label={t('statusDistribution.personas')}
                        distribution={data.status_distribution.persona}
                      />
                      <StatusDonut
                        label={t('statusDistribution.playbooks')}
                        distribution={data.status_distribution.playbook}
                      />
                      {data.status_distribution.resource ? (
                        <StatusDonut
                          label={t('statusDistribution.resources')}
                          distribution={data.status_distribution.resource}
                        />
                      ) : null}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>{t('activity.title')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Stack gap="md">
                      <DataList
                        items={data.activity}
                        getKey={(activity) => `${activity.ts}-${activity.entity_id}`}
                        renderItem={(activity) => <ActivityRow activity={activity} />}
                        empty={
                          <EmptyState
                            title={t('activity.empty.title')}
                            description={t('activity.empty.description')}
                          />
                        }
                      />
                      <PaginationControls
                        page={page}
                        totalPages={totalPages}
                        onPageChange={setPage}
                        busy={loading}
                      />
                    </Stack>
                  </CardContent>
                </Card>
              </Stack>
            ) : null}
          </DataView>
        )}
      </Stack>
    </Container>
  )
}
