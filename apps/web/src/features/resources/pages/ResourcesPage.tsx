import { FileText, GitBranch, Layers, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Resource } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { EntityCard } from '@/components/data/EntityCard'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { LoadingState } from '@/components/data/LoadingState'
import { MetaPill } from '@/components/data/MetaPill'
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

  // Leerer Workspace vs. leeres Filter-Ergebnis: bei aktiver Agent-Facette
  // kommt die Liste serverseitig gefiltert an — dann ist "leer" ein
  // Filter-Ergebnis, kein leerer Workspace.
  const isEmptyWorkspace = resources.length === 0 && filters.agent === ''

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
                      <>
                        <MetaPill icon={GitBranch} iconTone="playbook">
                          {(resource.playbook_link_count ?? 0) > 0
                            ? t('resources:card.linkedIn', {
                                count: resource.playbook_link_count ?? 0,
                              })
                            : t('resources:card.notLinked')}
                        </MetaPill>
                        {(resource.sub_resource_count ?? 0) > 0 ? (
                          <MetaPill icon={Layers} iconTone="resource">
                            {t('resources:card.subResourceCount', {
                              count: resource.sub_resource_count ?? 0,
                            })}
                          </MetaPill>
                        ) : null}
                      </>
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
