import { FileText, GitBranch, Layers, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Resource, SubResourceSummary } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { CONTENT_LOCALE_OPTIONS } from '@/components/forms/content-languages'
import { EntityCard } from '@/components/data/EntityCard'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { LoadingState } from '@/components/data/LoadingState'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { MetaPill } from '@/components/data/MetaPill'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAgents } from '@/hooks/useAgents'
import {
  useAgentFilterParam,
  useListFilters,
  useLocaleFilterParam,
  type ListFilterAccessors,
} from '@/hooks/useListFilters'
import { useResources } from '@/hooks/useResources'

/**
 * Aufklappbare Kind-Liste der Resource-Karte. Spiegelt das Sub-Playbook-Muster
 * (PersonaPlaybooksCard): nummerierte, verlinkte Zeilen mit Status/Version aus
 * der vom List-Endpoint mitgelieferten Summary.
 */
function SubResourceList({
  items,
  wsPath,
  label,
}: {
  items: SubResourceSummary[]
  wsPath: (path: string) => string
  label: string
}) {
  return (
    <ol className="flex flex-col gap-1.5" aria-label={label}>
      {items.map((child, index) => (
        <li key={child.id}>
          <Link
            to={wsPath(`/resources/${child.id}`)}
            className="flex items-center gap-3 rounded-lg border border-pill-catalog-fg/20 bg-card px-3 py-2 text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-pill-catalog text-xs font-bold text-pill-catalog-fg">
              {index + 1}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{child.name}</span>
            {child.status !== undefined ? <StatusBadge status={child.status} /> : null}
            {child.version !== undefined ? (
              <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                v{child.version}
              </span>
            ) : null}
          </Link>
        </li>
      ))}
    </ol>
  )
}

export function ResourcesPage() {
  const { t } = useTranslation(['resources', 'data'])
  // Serverseitige Agent-/Sprach-Facette (WP-B, ADR-0045): Params VOR dem
  // Daten-Hook lesen, damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const localeFilter = useLocaleFilterParam()
  const { resources, loading, error } = useResources(
    agentFilter || undefined,
    localeFilter || undefined,
  )
  const { agents } = useAgents()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<Resource>>(
    () => ({
      name: (resource) => resource.name,
      status: (resource) => resource.current_status,
      hasPendingDraft: (resource) => resource.has_pending_draft,
      tags: (resource) => resource.content.tags ?? [],
    }),
    [],
  )
  const filters = useListFilters(resources, accessors)

  // Leerer Workspace vs. leeres Filter-Ergebnis: bei aktiver Agent-/Sprach-
  // Facette kommt die Liste serverseitig gefiltert an — dann ist "leer" ein
  // Filter-Ergebnis, kein leerer Workspace.
  const isEmptyWorkspace =
    resources.length === 0 && filters.agent === '' && filters.locale === ''

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('resources:list.title')}
          description={t('resources:list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/resources/new')}>
                <Plus className="h-4 w-4" />
                {t('resources:list.newResource')}
              </Link>
            </Button>
          }
        />

        {resources.length > 0 || filters.agent !== '' || filters.locale !== '' ? (
          <ListFilterBar
            idPrefix="resources"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            availableTags={filters.availableTags}
            tag={filters.tag}
            onTagChange={filters.setTag}
            agents={agents}
            agent={filters.agent}
            onAgentChange={filters.setAgent}
            locales={CONTENT_LOCALE_OPTIONS}
            locale={filters.locale}
            onLocaleChange={filters.setLocale}
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}

        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorAlert message={error} />
        ) : filters.filtered.length === 0 ? (
          isEmptyWorkspace ? (
            <EmptyState
              icon={FileText}
              title={t('resources:list.emptyTitle')}
              description={t('resources:list.emptyDescription')}
              action={
                <Button asChild variant="brand">
                  <Link to={wsPath('/resources/new')}>
                    <Plus className="h-4 w-4" />
                    {t('resources:list.newResource')}
                  </Link>
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={FileText}
              title={t('data:filter.emptyFilteredTitle')}
              description={t('data:filter.emptyFilteredDescription')}
              action={
                <Button type="button" variant="outline" onClick={filters.reset}>
                  {t('data:filter.reset')}
                </Button>
              }
            />
          )
        ) : (
          <ul className="flex flex-col gap-3">
            {filters.filtered.map((resource) => {
              const tags = resource.content.tags ?? []
              const subResources = resource.sub_resources ?? []
              const hasSubResources = subResources.length > 0
              return (
                <li key={resource.id}>
                  <EntityCard
                    icon={FileText}
                    iconTone="resource"
                    title={resource.name}
                    href={wsPath(`/resources/${resource.id}`)}
                    badges={
                      <>
                        <Badge variant="secondary" className="tabular-nums">
                          v{resource.current_version}
                        </Badge>
                        <LocaleBadge locale={resource.locale} />
                        {resource.slug ? (
                          <Badge variant="outline" className="font-mono text-xs">
                            {resource.slug}
                          </Badge>
                        ) : null}
                        {tags.map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </>
                    }
                    status={
                      <StatusBadge
                        status={resource.current_status}
                        pendingDraft={resource.has_pending_draft}
                      />
                    }
                    description={resource.content.description}
                    meta={
                      <MetaPill icon={GitBranch} iconTone="playbook">
                        {(resource.playbook_link_count ?? 0) > 0
                          ? t('resources:card.linkedIn', {
                              count: resource.playbook_link_count ?? 0,
                            })
                          : t('resources:card.notLinked')}
                      </MetaPill>
                    }
                    expandable={
                      hasSubResources ? (
                        <SubResourceList
                          items={subResources}
                          wsPath={wsPath}
                          label={t('resources:card.subResourcesListLabel')}
                        />
                      ) : undefined
                    }
                    expandIcon={Layers}
                    expandLabel={
                      hasSubResources
                        ? t('resources:card.subResourcesToggle', {
                            count: subResources.length,
                          })
                        : undefined
                    }
                    expandSummary={
                      hasSubResources
                        ? subResources.map((child) => child.name).join(' · ')
                        : undefined
                    }
                  />
                </li>
              )
            })}
          </ul>
        )}
      </Stack>
    </Container>
  )
}
