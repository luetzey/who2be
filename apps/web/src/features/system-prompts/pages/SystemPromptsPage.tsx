import { FileText, Plus } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { SystemPromptTemplate } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useListFilters, type ListFilterAccessors } from '@/hooks/useListFilters'

import { useSystemPrompts } from '../hooks/useSystemPrompts'

export function SystemPromptsPage() {
  const { t } = useTranslation(['systemPrompts', 'data'])
  const { templates, loading, error } = useSystemPrompts()
  const wsPath = useWorkspacePath()

  const accessors = useMemo<ListFilterAccessors<SystemPromptTemplate>>(
    () => ({
      name: (template) => template.name,
      status: (template) => template.current_status,
      hasPendingDraft: (template) => template.has_pending_draft,
    }),
    [],
  )
  const filters = useListFilters(templates, accessors)

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('systemPrompts:page.list.title')}
          description={t('systemPrompts:page.list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/system-prompts/new')}>
                <Plus className="h-4 w-4" />
                {t('systemPrompts:page.list.newTemplate')}
              </Link>
            </Button>
          }
        />
        {templates.length > 0 ? (
          <ListFilterBar
            idPrefix="system-prompts"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}
        <DataList
          items={filters.filtered}
          loading={loading}
          error={error}
          getKey={(template) => template.id}
          empty={
            templates.length === 0 ? (
              <EmptyState
                icon={FileText}
                title={t('systemPrompts:page.list.empty.title')}
                description={t('systemPrompts:page.list.empty.description')}
                action={
                  <Button asChild variant="brand">
                    <Link to={wsPath('/system-prompts/new')}>
                      <Plus className="h-4 w-4" />
                      {t('systemPrompts:page.list.newTemplate')}
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
          renderItem={(template) => (
            <div className="flex items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={wsPath(`/system-prompts/${template.id}`)}
                  className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
                >
                  {template.name}
                </Link>
                <StatusBadge
                  status={template.current_status}
                  pendingDraft={template.has_pending_draft}
                />
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline">{template.slug}</Badge>
                <Badge variant="secondary">v{template.current_version}</Badge>
              </div>
            </div>
          )}
        />
      </Stack>
    </Container>
  )
}
