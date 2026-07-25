import { Plus, ScrollText, Users } from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { SystemPromptTemplate } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { CONTENT_LOCALE_OPTIONS } from '@/components/forms/content-languages'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import { EntityCard } from '@/components/data/EntityCard'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { MetaPill } from '@/components/data/MetaPill'
import { ListFilterBar } from '@/components/data/ListFilterBar'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  useListFilters,
  useLocaleFilterParam,
  type ListFilterAccessors,
} from '@/hooks/useListFilters'

import { useSystemPrompts } from '../hooks/useSystemPrompts'

export function SystemPromptsPage() {
  const { t } = useTranslation(['systemPrompts', 'data'])
  // Serverseitige Sprach-Facette (ADR-0045): Param VOR dem Daten-Hook lesen,
  // damit ein Facetten-Wechsel den Refetch ausloest.
  const localeFilter = useLocaleFilterParam()
  const { templates, loading, error } = useSystemPrompts(localeFilter || undefined)
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

  const newTemplateCta = (
    <Button asChild variant="brand">
      <Link to={wsPath('/system-prompts/new')}>
        <Plus className="h-4 w-4" />
        {t('systemPrompts:page.list.newTemplate')}
      </Link>
    </Button>
  )

  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('systemPrompts:page.list.title')}
          titleAddon={
            templates.length > 0 ? (
              <span
                className="rounded-full bg-muted px-2 py-0.5 text-sm font-medium text-muted-foreground tabular-nums"
                aria-label={`${templates.length} Templates`}
              >
                {templates.length}
              </span>
            ) : undefined
          }
          description={t('systemPrompts:page.list.description')}
          actions={newTemplateCta}
        />
        {templates.length > 0 || filters.locale !== '' ? (
          <ListFilterBar
            idPrefix="system-prompts"
            counts={filters.counts}
            status={filters.status}
            onStatusChange={filters.setStatus}
            query={filters.query}
            onQueryChange={filters.setQuery}
            locales={CONTENT_LOCALE_OPTIONS}
            locale={filters.locale}
            onLocaleChange={filters.setLocale}
            active={filters.active}
            onReset={filters.reset}
          />
        ) : null}
        <DataView loading={loading && templates.length === 0} error={error}>
          {templates.length === 0 && filters.locale === '' ? (
            <EmptyState
              icon={ScrollText}
              title={t('systemPrompts:page.list.empty.title')}
              description={t('systemPrompts:page.list.empty.description')}
              action={newTemplateCta}
            />
          ) : filters.filtered.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title={t('data:filter.emptyFilteredTitle')}
              description={t('data:filter.emptyFilteredDescription')}
              action={
                <Button type="button" variant="outline" onClick={filters.reset}>
                  {t('data:filter.reset')}
                </Button>
              }
            />
          ) : (
            <div className="flex flex-col gap-3">
              {filters.filtered.map((template) => (
                <EntityCard
                  key={template.id}
                  icon={ScrollText}
                  iconTone="tools"
                  title={template.name}
                  href={wsPath(`/system-prompts/${template.id}`)}
                  badges={
                    <>
                      <Badge variant="outline" className="font-mono">
                        {template.slug}
                      </Badge>
                      <Badge variant="secondary">v{template.current_version}</Badge>
                      <LocaleBadge locale={template.locale} />
                    </>
                  }
                  status={
                    <StatusBadge
                      status={template.current_status}
                      pendingDraft={template.has_pending_draft}
                    />
                  }
                  description={template.content.description}
                  meta={
                    <MetaPill icon={Users} iconTone="persona">
                      {(template.agent_count ?? 0) > 0
                        ? t('systemPrompts:card.usedByAgents', { count: template.agent_count ?? 0 })
                        : t('systemPrompts:card.usedByNone')}
                    </MetaPill>
                  }
                />
              ))}
            </div>
          )}
        </DataView>
      </Stack>
    </Container>
  )
}
