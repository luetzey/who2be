import {
  ArrowRight,
  Bell,
  BookOpen,
  Bot,
  Brain,
  CircleCheck,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Plus,
  ScrollText,
  UserPlus,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import { ActivityRow } from '../components/ActivityRow'
import { KpiCard } from '../components/KpiCard'
import { PaginationControls } from '../components/PaginationControls'
import { StatusBar } from '../components/StatusBar'
import { statusLabel } from '../lib/statusLabel'
import { useDashboard } from '../hooks/useDashboard'

const EYEBROW = 'text-xs font-semibold uppercase tracking-wide text-muted-foreground'
const LEGEND_STATUSES = ['draft', 'review', 'active', 'inactive'] as const

export function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const role = useCurrentWorkspaceRole()
  const wsPath = useWorkspacePath()
  const { data, loading, error, notFound, preparing, page, setPage } = useDashboard()

  const pagination = data?.activity_pagination
  const totalPages = pagination?.total_pages ?? 1
  const pendingReviews = data?.kpis.pending_reviews ?? 0
  const pendingMemories = data?.kpis.pending_memories ?? 0
  const pendingSystemPrompts = data?.kpis.pending_system_prompts ?? 0
  const allClear = pendingReviews === 0 && pendingMemories === 0 && pendingSystemPrompts === 0
  const activeResources =
    data?.kpis.active_resources ?? data?.status_distribution.resource?.active ?? 0

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader title={t('page.title')} description={t('page.description')} />

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
                {/* Aufmerksamkeits-Band */}
                <section className="flex flex-col gap-3" aria-label="Braucht jetzt deine Aufmerksamkeit">
                  <span className={cn('flex items-center gap-2', EYEBROW)}>
                    <Bell className="size-3.5" aria-hidden="true" />
                    Braucht jetzt deine Aufmerksamkeit
                  </span>
                  {pendingReviews > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={ClipboardCheck}
                      title={`${pendingReviews} ${t('kpis.pendingReviewsDescription')}`}
                      description="Prüfe die offenen Entwürfe in Personae und Playbooks."
                    />
                  ) : null}
                  {pendingMemories > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={Brain}
                      title={
                        pendingMemories === 1
                          ? '1 neuer Gedächtniseintrag wartet auf Freigabe'
                          : `${pendingMemories} neue Gedächtniseinträge warten auf Freigabe`
                      }
                      description="Gib die Gedächtnis-Vorschläge deiner Agenten frei oder lehne sie ab."
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/agents')}>
                            Agenten öffnen
                            <ArrowRight />
                          </Link>
                        </Button>
                      }
                    />
                  ) : null}
                  {pendingSystemPrompts > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={ScrollText}
                      title={
                        pendingSystemPrompts === 1
                          ? '1 System-Prompt liegt zur Review'
                          : `${pendingSystemPrompts} System-Prompts liegen zur Review`
                      }
                      description="Prüfe die eingereichten System-Prompt-Versionen."
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/system-prompts?status=review')}>
                            Zur Review
                            <ArrowRight />
                          </Link>
                        </Button>
                      }
                    />
                  ) : null}
                  {allClear ? (
                    <AttentionBanner
                      variant="brand"
                      icon={CircleCheck}
                      title="Alles erledigt"
                      description="Nichts wartet gerade auf dich — leg direkt los."
                    />
                  ) : null}
                </section>

                {/* Schnellstart */}
                {role !== 'viewer' ? (
                  <section className="flex flex-col gap-3" aria-label="Schnellstart">
                    <span className={EYEBROW}>Schnellstart</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button asChild variant="brand">
                        <Link to={wsPath('/playbooks/new')}>
                          <Plus />
                          Neues Playbook
                        </Link>
                      </Button>
                      <Button asChild variant="outline">
                        <Link to={wsPath('/personas/new')}>
                          <UserPlus />
                          Neue Persona
                        </Link>
                      </Button>
                      <Button asChild variant="outline">
                        <Link to={wsPath('/agents')}>
                          <Bot />
                          Neuer Agent
                        </Link>
                      </Button>
                      <Button asChild variant="ghost" className="ml-auto">
                        <Link to={wsPath('/feedback')}>
                          Feedback ansehen
                          <ArrowRight />
                        </Link>
                      </Button>
                    </div>
                  </section>
                ) : null}

                {/* KPI-Strip */}
                <section
                  className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                  aria-label={t('kpis.ariaLabel')}
                >
                  <KpiCard
                    label={t('kpis.activePersonas')}
                    value={data.kpis.active_personas}
                    icon={Users}
                    tone="persona"
                  />
                  <KpiCard
                    label={t('kpis.activePlaybooks')}
                    value={data.kpis.active_playbooks}
                    icon={BookOpen}
                    tone="playbook"
                  />
                  <KpiCard
                    label={t('statusDistribution.resources')}
                    value={activeResources}
                    icon={FileText}
                    tone="resource"
                  />
                </section>

                {/* Status-Verteilung */}
                <Card>
                  <CardHeader className="flex-row flex-wrap items-center justify-between gap-3 space-y-0">
                    <CardTitle>{t('statusDistribution.title')}</CardTitle>
                    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      {LEGEND_STATUSES.map((status) => (
                        <li key={status} className="flex items-center gap-1.5">
                          <span
                            className="inline-block size-2 rounded-full"
                            style={{ backgroundColor: `var(--status-${status})` }}
                            aria-hidden="true"
                          />
                          {statusLabel(status)}
                        </li>
                      ))}
                    </ul>
                  </CardHeader>
                  <CardContent>
                    <Stack gap="md">
                      <StatusBar
                        label={t('statusDistribution.personas')}
                        distribution={data.status_distribution.persona}
                        hrefFor={(status) => wsPath(`/personas?status=${status}`)}
                      />
                      <StatusBar
                        label={t('statusDistribution.playbooks')}
                        distribution={data.status_distribution.playbook}
                        hrefFor={(status) => wsPath(`/playbooks?status=${status}`)}
                      />
                      {data.status_distribution.resource ? (
                        <StatusBar
                          label={t('statusDistribution.resources')}
                          distribution={data.status_distribution.resource}
                          hrefFor={(status) => wsPath(`/resources?status=${status}`)}
                        />
                      ) : null}
                    </Stack>
                  </CardContent>
                </Card>

                {/* Letzte Aktivitaeten */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t('activity.title')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Stack gap="md">
                      {data.activity.length === 0 ? (
                        <EmptyState
                          title={t('activity.empty.title')}
                          description={t('activity.empty.description')}
                        />
                      ) : (
                        <ul className="-mx-2 flex flex-col">
                          {data.activity.map((activity) => (
                            <li
                              key={`${activity.ts}-${activity.entity_id}`}
                              className="rounded-md px-2 py-2 transition-[background-color] duration-[var(--duration-fast)] ease-standard hover:bg-muted/50"
                            >
                              <ActivityRow activity={activity} />
                            </li>
                          ))}
                        </ul>
                      )}
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
