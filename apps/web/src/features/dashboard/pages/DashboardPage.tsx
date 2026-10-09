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
  MessageSquareWarning,
  Plus,
  Repeat,
  ScrollText,
  UserPlus,
  Users,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Api } from '@/api/client'
import { useApi } from '@/api/useApi'
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
import { statusLabel } from '@/components/version'
import { useApprovalCount } from '@/hooks/useApprovalCount'
import { cn } from '@/lib/utils'

import { ActivityRow } from '../components/ActivityRow'
import { KpiCard } from '../components/KpiCard'
import { PaginationControls } from '../components/PaginationControls'
import { StatusBar } from '../components/StatusBar'
import { useDashboard } from '../hooks/useDashboard'
import { useReviewTargets } from '../hooks/useReviewTargets'

const EYEBROW = 'text-xs font-semibold uppercase tracking-wide text-muted-foreground'
const LEGEND_STATUSES = ['draft', 'review', 'active', 'inactive'] as const

/**
 * Eine Zahl fuer das Aufmerksamkeits-Band, die nur fuer editor+ geladen wird
 * (Lernschleife D6h). `enabled=false` (viewer, Rolle unbekannt) loest keinen
 * Aufruf aus. `null`, solange die Zahl laedt, nicht ladbar ist oder nicht
 * angefragt wird — dann zeigt das Band keinen Eintrag. Jede Zahl hat ihren
 * eigenen Effekt: scheitert ein Aufruf, bleibt der andere Eintrag stehen.
 */
function useEditorCount(enabled: boolean, load: (api: Api) => Promise<number>): number | null {
  const api = useApi()
  // Ergebnis samt Anfrage-Schluessel, wie `useApprovalCount`: eine Zahl aus
  // einem anderen Workspace gilt nicht.
  const [result, setResult] = useState<{ api: Api; total: number | null } | null>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    load(api)
      .then((total) => {
        if (!cancelled) setResult({ api, total })
      })
      .catch(() => {
        if (!cancelled) setResult({ api, total: null })
      })
    return () => {
      cancelled = true
    }
    // `load` ist eine modulweite Funktion und damit stabil.
  }, [api, enabled, load])

  if (!enabled || result === null || result.api !== api) return null
  return result.total
}

// Muster haben keinen Neu-Status (ADR 3.7): gezaehlt wird die ganze Liste.
const loadPatternCount = (api: Api) =>
  api.listPatterns().then((list) => list.patterns.length)

// Offene Faelle = `open` + `reopened` aus dem Zaehler-Endpunkt (Q1); die
// Fall-Liste wird zum Zaehlen nie geladen.
const loadOpenCaseCount = (api: Api) =>
  api.countCases().then((counts) => (counts.open ?? 0) + (counts.reopened ?? 0))

export function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const role = useCurrentWorkspaceRole()
  const wsPath = useWorkspacePath()
  const { data, loading, error, notFound, preparing, page, setPage } = useDashboard()

  const pagination = data?.activity_pagination
  const totalPages = pagination?.total_pages ?? 1
  const pendingReviews = data?.kpis.pending_reviews ?? 0
  // Dieselbe Quelle wie der Tab „Zur Freigabe“ (C5a-2), rollengerecht ohne
  // Lernvorschlaege und fremdes Nutzergedaechtnis; das Dashboard selbst
  // liefert keine Gedaechtnis-Zahl (ADR-0053 3.1.1). `null` (laedt/Fehler)
  // zeigt keinen Banner und kein „Alles erledigt“.
  const pendingMemories = useApprovalCount()
  const pendingSystemPrompts = data?.kpis.pending_system_prompts ?? 0
  // Lernschleife D6h: Muster und offene Faelle nur fuer editor+ (wie die
  // Hub-Tabs). viewer und eine noch unbekannte Rolle fragen nichts an.
  const canTriage = role !== null && role !== 'viewer'
  const patternCount = useEditorCount(canTriage, loadPatternCount)
  const openCaseCount = useEditorCount(canTriage, loadOpenCaseCount)
  // Fuer editor+ behauptet „Alles erledigt“ erst etwas, wenn beide Zahlen
  // belegt 0 sind; fuer viewer zaehlen die Eintraege nicht.
  const triageClear = !canTriage || (patternCount === 0 && openCaseCount === 0)
  const allClear =
    pendingReviews === 0 && pendingMemories === 0 && pendingSystemPrompts === 0 && triageClear
  const reviewTargets = useReviewTargets(pendingReviews, data?.status_distribution)
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
                <section className="flex flex-col gap-3" aria-label={t('attention.ariaLabel')}>
                  <span className={cn('flex items-center gap-2', EYEBROW)}>
                    <Bell className="size-3.5" aria-hidden="true" />
                    {t('attention.eyebrow')}
                  </span>
                  {pendingReviews > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={ClipboardCheck}
                      title={t('attention.reviews.title', { count: pendingReviews })}
                      description={t('attention.reviews.description')}
                      actions={
                        reviewTargets.targets !== null
                          ? reviewTargets.targets.map((target) => {
                              const label = t('attention.reviews.openVersion', {
                                name: target.name,
                                version: target.version,
                              })
                              return (
                                <Button
                                  key={`${target.type}-${target.id}`}
                                  asChild
                                  variant="outline"
                                  size="sm"
                                  className="max-w-full"
                                >
                                  {/* `title`: auf 390 px wird der Name gekuerzt. */}
                                  <Link to={wsPath(target.path)} title={label}>
                                    <span className="min-w-0 truncate">{label}</span>
                                    <ArrowRight />
                                  </Link>
                                </Button>
                              )
                            })
                          : reviewTargets.lists.map((list) => (
                              <Button key={list.type} asChild variant="outline" size="sm">
                                <Link to={wsPath(list.path)}>
                                  {t(`attention.reviews.openList.${list.type}`, {
                                    count: list.count,
                                  })}
                                  <ArrowRight />
                                </Link>
                              </Button>
                            ))
                      }
                    />
                  ) : null}
                  {pendingMemories !== null && pendingMemories > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={Brain}
                      title={t('attention.memories.title', { count: pendingMemories })}
                      description={t('attention.memories.description')}
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/memory?tab=approval')}>
                            {t('attention.memories.action')}
                            <ArrowRight />
                          </Link>
                        </Button>
                      }
                    />
                  ) : null}
                  {patternCount !== null && patternCount > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={Repeat}
                      title={t('attention.patterns.title', { count: patternCount })}
                      description={t('attention.patterns.description')}
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/feedback?tab=patterns')}>
                            {t('attention.patterns.action')}
                            <ArrowRight />
                          </Link>
                        </Button>
                      }
                    />
                  ) : null}
                  {openCaseCount !== null && openCaseCount > 0 ? (
                    <AttentionBanner
                      variant="brand"
                      icon={MessageSquareWarning}
                      title={t('attention.cases.title', { count: openCaseCount })}
                      description={t('attention.cases.description')}
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/feedback?tab=cases')}>
                            {t('attention.cases.action')}
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
                      title={t('attention.systemPrompts.title', { count: pendingSystemPrompts })}
                      description={t('attention.systemPrompts.description')}
                      actions={
                        <Button asChild variant="outline" size="sm">
                          <Link to={wsPath('/system-prompts?status=review')}>
                            {t('attention.systemPrompts.action')}
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
                      title={t('attention.allClear.title')}
                      description={t('attention.allClear.description')}
                    />
                  ) : null}
                </section>

                {/* Schnellstart */}
                {role !== 'viewer' ? (
                  <section className="flex flex-col gap-3" aria-label={t('quickStart.ariaLabel')}>
                    <span className={EYEBROW}>{t('quickStart.eyebrow')}</span>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button asChild variant="brand">
                        <Link to={wsPath('/playbooks/new')}>
                          <Plus />
                          {t('quickStart.newPlaybook')}
                        </Link>
                      </Button>
                      <Button asChild variant="outline">
                        <Link to={wsPath('/personas/new')}>
                          <UserPlus />
                          {t('quickStart.newPersona')}
                        </Link>
                      </Button>
                      <Button asChild variant="outline">
                        <Link to={wsPath('/agents')}>
                          <Bot />
                          {t('quickStart.newAgent')}
                        </Link>
                      </Button>
                      <Button asChild variant="ghost" className="ml-auto">
                        <Link to={wsPath('/feedback')}>
                          {t('quickStart.viewFeedback')}
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
                        <li key={status} className="flex min-w-0 items-center gap-1.5">
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
