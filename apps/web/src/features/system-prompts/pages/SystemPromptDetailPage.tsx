import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { VersionHistory } from '@/components/version'
import { notify } from '@/lib/feedback'

import { SystemPromptEditorForm } from '../components/SystemPromptEditorForm'
import { SystemPromptStatusActionBar } from '../components/SystemPromptStatusActionBar'
import { useSystemPrompt } from '../hooks/useSystemPrompt'
import { useSystemPromptForm } from '../hooks/useSystemPromptForm'

export function SystemPromptDetailPage() {
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
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

              <VersionHistory
                versions={versions}
                canEdit={role === 'admin' || role === 'editor'}
                onRestore={async (version) => {
                  await api.restoreSystemPromptTemplateVersion(template.id, version)
                  notify.success(`v${version} als Entwurf wiederhergestellt.`)
                  reload()
                }}
                loadDiff={(version) =>
                  api.diffSystemPromptTemplateVersion(template.id, version)
                }
                loadProvenance={(version) =>
                  api.provenanceSystemPromptTemplateVersion(template.id, version)
                }
              />
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
