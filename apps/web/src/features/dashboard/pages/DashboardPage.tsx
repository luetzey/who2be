import { BookOpen, ClipboardCheck, LayoutDashboard, Users } from 'lucide-react'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { ActivityRow } from '../components/ActivityRow'
import { KpiCard } from '../components/KpiCard'
import { PaginationControls } from '../components/PaginationControls'
import { StatusDonut } from '../components/StatusDonut'
import { useDashboard } from '../hooks/useDashboard'

export function DashboardPage() {
  const { data, loading, error, notFound, page, setPage } = useDashboard()

  const pagination = data?.activity_pagination
  const totalPages = pagination?.total_pages ?? 1

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Dashboard"
          description="Aktueller Zustand des Workspaces — KPIs, Status-Verteilung und Aktivitäten."
        />

        {notFound ? (
          <EmptyState
            icon={LayoutDashboard}
            title="Dashboard noch nicht verfügbar."
            description="Der Dashboard-Endpoint wird mit Phase 2.1b-A/B ausgerollt. Sobald das Backend gemergt ist, erscheinen hier KPIs, Aktivitäten und die Status-Verteilung."
          />
        ) : (
          <DataView loading={loading && data === null} error={error}>
            {data !== null ? (
              <Stack gap="lg">
                <section
                  className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                  aria-label="Kennzahlen"
                >
                  <KpiCard
                    label="Aktive Personae"
                    value={data.kpis.active_personas}
                    icon={Users}
                  />
                  <KpiCard
                    label="Aktive Playbooks"
                    value={data.kpis.active_playbooks}
                    icon={BookOpen}
                  />
                  <KpiCard
                    label="In Review"
                    value={data.kpis.pending_reviews}
                    icon={ClipboardCheck}
                    description="Versionen, die auf Promote warten."
                  />
                </section>

                <Card>
                  <CardHeader>
                    <CardTitle>Status-Verteilung</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                      <StatusDonut
                        label="Personae"
                        distribution={data.status_distribution.persona}
                      />
                      <StatusDonut
                        label="Playbooks"
                        distribution={data.status_distribution.playbook}
                      />
                      {data.status_distribution.resource ? (
                        <StatusDonut
                          label="Resources"
                          distribution={data.status_distribution.resource}
                        />
                      ) : null}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Letzte Aktivitäten</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Stack gap="md">
                      <DataList
                        items={data.activity}
                        getKey={(activity) => `${activity.ts}-${activity.entity_id}`}
                        renderItem={(activity) => <ActivityRow activity={activity} />}
                        empty={
                          <EmptyState
                            title="Noch keine Aktivitäten."
                            description="Sobald jemand Versionen anlegt oder Status ändert, erscheinen sie hier."
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
