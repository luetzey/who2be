import { FileText, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { EmptyState } from '@/components/data/EmptyState'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { useSystemPrompts } from '../hooks/useSystemPrompts'

export function SystemPromptsPage() {
  const { t } = useTranslation('systemPrompts')
  const { templates, loading, error } = useSystemPrompts()
  const wsPath = useWorkspacePath()
  return (
    <Container>
      <Stack gap="lg">
        <PageHeader
          title={t('page.list.title')}
          description={t('page.list.description')}
          actions={
            <Button asChild variant="brand">
              <Link to={wsPath('/system-prompts/new')}>
                <Plus className="h-4 w-4" />
                {t('page.list.newTemplate')}
              </Link>
            </Button>
          }
        />
        <DataList
          items={templates}
          loading={loading}
          error={error}
          getKey={(template) => template.id}
          empty={
            <EmptyState
              icon={FileText}
              title={t('page.list.empty.title')}
              description={t('page.list.empty.description')}
              action={
                <Button asChild variant="brand">
                  <Link to={wsPath('/system-prompts/new')}>
                    <Plus className="h-4 w-4" />
                    {t('page.list.newTemplate')}
                  </Link>
                </Button>
              }
            />
          }
          renderItem={(template) => (
            <div className="flex items-center justify-between gap-3">
              <Link
                to={wsPath(`/system-prompts/${template.id}`)}
                className="rounded-sm font-medium text-foreground ring-offset-background hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                {template.name}
              </Link>
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
