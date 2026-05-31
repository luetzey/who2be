import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import type { VersionStatus } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { SystemPromptEditorForm } from '../components/SystemPromptEditorForm'
import { SystemPromptStatusActionBar } from '../components/SystemPromptStatusActionBar'
import { useSystemPrompt } from '../hooks/useSystemPrompt'
import { useSystemPromptForm } from '../hooks/useSystemPromptForm'

function statusBadge(status: VersionStatus | undefined) {
  if (status === 'active') return <Badge variant="default">Aktiv</Badge>
  if (status === 'review') return <Badge variant="secondary">In Review</Badge>
  if (status === 'draft') return <Badge variant="outline">Entwurf</Badge>
  return <Badge variant="outline">Inaktiv</Badge>
}

export function SystemPromptDetailPage() {
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const { template, versions, loading, error, reload } = useSystemPrompt(id)
  const { form, onSubmit, saveError } = useSystemPromptForm(template, reload)

  if (id === undefined) {
    return <Navigate to={wsPath('/system-prompts')} replace />
  }

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/system-prompts')}>
            <ArrowLeft className="h-4 w-4" />
            System-Prompts
          </Link>
        </Button>
        <DataView loading={loading && template === null} error={error}>
          {template !== null ? (
            <Stack gap="lg">
              <Stack gap="md">
                <PageHeader
                  title={template.name}
                  description={`Slug: ${template.slug} · Aktuelle Version: v${template.current_version}`}
                />
                {template.current_status !== undefined ? (
                  <SystemPromptStatusActionBar
                    templateId={template.id}
                    version={template.current_version}
                    status={template.current_status}
                    onTransitioned={reload}
                  />
                ) : null}
              </Stack>

              <SystemPromptEditorForm
                form={form}
                onSubmit={onSubmit}
                saveError={saveError}
              />

              <Card>
                <CardHeader>
                  <CardTitle>Versionen</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataList
                    items={versions}
                    getKey={(version) => String(version.version)}
                    renderItem={(version) => (
                      <span className="flex items-center justify-between gap-3">
                        <span>
                          v{version.version} —{' '}
                          {new Date(version.created_at).toLocaleString()}
                        </span>
                        {statusBadge(version.status)}
                      </span>
                    )}
                  />
                </CardContent>
              </Card>
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
