import { BookOpen, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { Playbook } from '@/api/types'
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
import { usePlaybooks } from '@/hooks/usePlaybooks'
import { useWorkspacePath } from '@/auth/useWorkspacePath'

export function PlaybooksPage() {
  const { t } = useTranslation(['playbooks', 'data', 'common'])
  // Serverseitige Agent-Facette (WP-B): Param VOR dem Daten-Hook lesen,
  // damit ein Facetten-Wechsel den Refetch ausloest.
  const agentFilter = useAgentFilterParam()
  const { playbooks, loading, error } = usePlaybooks(agentFilter || undefined)
  const { agents } = useAgents()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<Playbook>>(
    () => ({
      name: (playbook) => playbook.name,
      status: (playbook) => playbook.current_status,
      hasPendingDraft: (playbook) => playbook.has_pending_draft,
      tags: (playbook) => playbook.tags,
      type: (playbook) => playbook.type,
    }),
    [],
  )
  const filters = useListFilters(playbooks, accessors)

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('playbooks:list.title')}
          description={t('playbooks:list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/playbooks/new')}>
                <Plus className="h-4 w-4" />
                {t('playbooks:list.newButton')}
              </Link>
            </Button>
          }
        />
        {playbooks.length > 0 || filters.agent !== '' ? (
          <ListFilterBar
            idPrefix="playbooks"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            availableTags={filters.availableTags}
            tag={filters.tag}
            onTagChange={filters.setTag}
            availableTypes={filters.availableTypes}
            type={filters.type}
            onTypeChange={filters.setType}
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
          getKey={(playbook) => playbook.id}
          empty={
            // Bei aktiver Agent-Facette kommt die Liste serverseitig gefiltert
            // an — dann ist "leer" ein Filter-Ergebnis, kein leerer Workspace.
            playbooks.length === 0 && filters.agent === '' ? (
              <EmptyState
                icon={BookOpen}
                title={t('playbooks:list.empty.title')}
                description={t('playbooks:list.empty.description')}
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath('/playbooks/new')}>
                      <Plus className="h-4 w-4" />
                      {t('playbooks:list.newButton')}
                    </Link>
                  </Button>
                }
              />
            ) : (
              <EmptyState
                icon={BookOpen}
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
          renderItem={(playbook) => (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={wsPath(`/playbooks/${playbook.id}`)}
                  className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                >
                  {playbook.name}
                </Link>
                <StatusBadge
                  status={playbook.current_status}
                  pendingDraft={playbook.has_pending_draft}
                />
                <span className="text-xs text-muted-foreground">
                  {playbook.type} · v{playbook.current_version}
                </span>
              </div>
              {playbook.tags.length > 0 ? (
                <div className="flex flex-wrap gap-1" aria-label={t('common:fields.tags')}>
                  {playbook.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
