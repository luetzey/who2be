import { LayoutDashboard } from 'lucide-react'

import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { ActivityRow } from '../components/ActivityRow'
import { KpiCard } from '../components/KpiCard'
import { StatusBar } from '../components/StatusBar'
import { useDashboard } from '../hooks/useDashboard'

export function DashboardPage() {
  const { data, loading, error, notFound } = useDashboard()

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title="Dashboard"
          description="Aktueller Zustand des Workspaces — KPIs, Aktivitaeten und Status-Verteilung."
        />

        {notFound ? (
          <EmptyState
            icon={LayoutDashboard}
            title="Dashboard noch nicht verfuegbar."
            description="Der Dashboard-Endpoint wird mit Phase 2.1b-A/B ausgerollt. Sobald das Backend gemergt ist, erscheinen hier KPIs, Aktivitaeten und die Status-Verteilung."
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
                  />
                  <KpiCard
                    label="Aktive Playbooks"
                    value={data.kpis.active_playbooks}
                  />
                  <KpiCard
                    label="In Review"
                    value={data.kpis.pending_reviews}
                    description="Versionen, die auf Promote warten."
                  />
                </section>

                <Card>
                  <CardHeader>
                    <CardTitle>Letzte Aktivitaeten</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DataList
                      items={data.activity}
                      getKey={(activity) => `${activity.ts}-${activity.entity_id}`}
                      renderItem={(activity) => <ActivityRow activity={activity} />}
                      empty={
                        <EmptyState
                          title="Noch keine Aktivitaeten."
                          description="Sobald jemand Versionen anlegt oder Status aendert, erscheinen sie hier."
                        />
                      }
                    />
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Status-Verteilung</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Stack gap="md">
                      <StatusBar
                        label="Personae"
                        distribution={data.status_distribution.persona}
                      />
                      <StatusBar
                        label="Playbooks"
                        distribution={data.status_distribution.playbook}
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
