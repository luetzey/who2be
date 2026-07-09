import { FileText, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Resource } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAgents } from '@/hooks/useAgents'
import {
  useAgentFilterParam,
  useListFilters,
  type ListFilterAccessors,
} from '@/hooks/useListFilters'
import { useResources } from '@/hooks/useResources'

export function ResourcesPage() {
  const { t } = useTranslation(['resources', 'data'])
  // Serverseitige Agent-Facette (WP-B): Param VOR dem Daten-Hook lesen,
  // damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const { resources, loading, error } = useResources(agentFilter || undefined)
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

        {resources.length > 0 || filters.agent !== '' ? (
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
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}

        <DataList
          items={filters.filtered}
          loading={loading}
          error={error}
          getKey={(resource) => resource.id}
          empty={
            // Bei aktiver Agent-Facette kommt die Liste serverseitig gefiltert
            // an — dann ist "leer" ein Filter-Ergebnis, kein leerer Workspace.
            resources.length === 0 && filters.agent === '' ? (
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
          }
          renderItem={(resource) => (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={wsPath(`/resources/${resource.id}`)}
                  className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                >
                  {resource.name}
                </Link>
                <StatusBadge
                  status={resource.current_status}
                  pendingDraft={resource.has_pending_draft}
                />
                {(resource.content.tags ?? []).length > 0 ? (
                  <div className="flex flex-wrap gap-1" aria-label={t('resources:list.tagFilter')}>
                    {(resource.content.tags ?? []).map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
              <span className="text-xs text-muted-foreground">v{resource.current_version}</span>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
