import { Plus, Users } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Persona } from '@/api/types'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { ListFilterBar } from '@/components/data/ListFilterBar'
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
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { usePersonas } from '@/hooks/usePersonas'

export function PersonasPage() {
  const { t } = useTranslation(['personas', 'data'])
  // Serverseitige Agent-Facette (WP-B): Param VOR dem Daten-Hook lesen,
  // damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const { personas, loading, error } = usePersonas(agentFilter || undefined)
  const { agents } = useAgents()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<Persona>>(
    () => ({
      name: (persona) => persona.name,
      status: (persona) => persona.current_status,
      hasPendingDraft: (persona) => persona.has_pending_draft,
      tags: (persona) => persona.content?.tags ?? [],
    }),
    [],
  )
  const filters = useListFilters(personas, accessors)

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('personas:list.title')}
          description={t('personas:list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/personas/new')}>
                <Plus className="h-4 w-4" />
                {t('personas:list.newPersona')}
              </Link>
            </Button>
          }
        />
        {personas.length > 0 || filters.agent !== '' ? (
          <ListFilterBar
            idPrefix="personas"
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
        <DataView loading={loading} error={error}>
          {filters.filtered.length === 0 ? (
            // Bei aktiver Agent-Facette kommt die Liste serverseitig gefiltert
            // an — dann ist "leer" ein Filter-Ergebnis, kein leerer Workspace.
            personas.length === 0 && filters.agent === '' ? (
              <EmptyState
                icon={Users}
                title={t('personas:list.empty.title')}
                description={t('personas:list.empty.description')}
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath('/personas/new')}>
                      <Plus className="h-4 w-4" />
                      {t('personas:list.newPersona')}
                    </Link>
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={Users}
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
            <div className="flex flex-col gap-3">
              {filters.filtered.map((persona) => {
                const tags = persona.content?.tags ?? []
                return (
                  <EntityCard
                    key={persona.id}
                    icon={Users}
                    iconTone="persona"
                    title={persona.name}
                    href={wsPath(`/personas/${persona.id}`)}
                    badges={<Badge variant="secondary">v{persona.current_version}</Badge>}
                    status={
                      <StatusBadge
                        status={persona.current_status}
                        pendingDraft={persona.has_pending_draft}
                      />
                    }
                    description={persona.content.description}
                    meta={
                      tags.length > 0
                        ? tags.map((tag) => (
                            <MetaPill key={tag} tone="persona">
                              {tag}
                            </MetaPill>
                          ))
                        : undefined
                    }
                  />
                )
              })}
            </div>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
