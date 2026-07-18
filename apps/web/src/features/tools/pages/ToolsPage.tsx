import { Plug, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { ExternalTool } from '@/api/types'
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
import { useListFilters, type ListFilterAccessors } from '@/hooks/useListFilters'

import { useTools } from '../hooks/useTools'

export function ToolsPage() {
  const { t } = useTranslation(['tools', 'data'])
  const { tools, loading, error } = useTools()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<ExternalTool>>(
    () => ({
      name: (tool) => tool.name,
      status: (tool) => tool.current_status,
      hasPendingDraft: (tool) => tool.has_pending_draft,
      tags: (tool) => tool.content.tags ?? [],
      searchText: (tool) => [tool.alias, tool.content.display_name, tool.content.mcp_server_name],
    }),
    [],
  )
  const filters = useListFilters(tools, accessors)

  const newToolCta = (
    <Button asChild variant="brand">
      <Link to={wsPath('/tools/new')}>
        <Plus className="h-4 w-4" />
        {t('tools:list.newTool')}
      </Link>
    </Button>
  )

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('tools:list.title')}
          titleAddon={
            tools.length > 0 ? (
              <span
                className="rounded-full bg-muted px-2 py-0.5 text-sm font-medium text-muted-foreground tabular-nums"
                aria-label={`${tools.length}`}
              >
                {tools.length}
              </span>
            ) : undefined
          }
          description={t('tools:list.description')}
          actions={newToolCta}
        />

        {tools.length > 0 ? (
          <ListFilterBar
            idPrefix="tools"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            availableTags={filters.availableTags}
            tag={filters.tag}
            onTagChange={filters.setTag}
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}

        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorAlert message={error} />
        ) : tools.length === 0 ? (
          <EmptyState
            icon={Plug}
            title={t('tools:list.emptyTitle')}
            description={t('tools:list.emptyDescription')}
            action={newToolCta}
          />
        ) : filters.filtered.length === 0 ? (
          <EmptyState
            icon={Plug}
            title={t('data:filter.emptyFilteredTitle')}
            description={t('data:filter.emptyFilteredDescription')}
            action={
              <Button type="button" variant="outline" onClick={filters.reset}>
                {t('data:filter.reset')}
              </Button>
            }
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {filters.filtered.map((tool) => {
              const tags = tool.content.tags ?? []
              const toolNames = tool.content.tool_names ?? []
              return (
                <li key={tool.id}>
                  <EntityCard
                    icon={Plug}
                    iconTone="tools"
                    title={tool.name}
                    href={wsPath(`/tools/${tool.id}`)}
                    badges={
                      <>
                        <Badge variant="outline" className="font-mono text-xs">
                          {tool.alias}
                        </Badge>
                        <Badge variant="secondary" className="tabular-nums">
                          v{tool.current_version}
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
                        status={tool.current_status}
                        pendingDraft={tool.has_pending_draft}
                      />
                    }
                    description={tool.content.display_name || tool.content.mcp_server_name}
                    meta={
                      <MetaPill icon={Plug} iconTone="tools">
                        {toolNames.length > 0
                          ? t('tools:card.toolCount', { count: toolNames.length })
                          : t('tools:card.noToolNames')}
                      </MetaPill>
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
