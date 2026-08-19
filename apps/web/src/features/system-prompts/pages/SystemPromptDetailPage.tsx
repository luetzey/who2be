import { Clock, GitBranch, ScrollText, SquarePen } from 'lucide-react'
import { Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { LocaleBadge } from '@/components/data/LocaleBadge'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { StatusBadge } from '@/components/data/StatusBadge'
import { Container } from '@/components/layout/Container'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { VersionHistory } from '@/components/version'
import { EntityDuplicateButton } from '@/components/entity'
import { notify } from '@/lib/feedback'

import { SystemPromptEditorForm } from '../components/SystemPromptEditorForm'
import { SystemPromptStatusActionBar } from '../components/SystemPromptStatusActionBar'
import { useSystemPrompt } from '../hooks/useSystemPrompt'
import { useSystemPromptForm } from '../hooks/useSystemPromptForm'

export function SystemPromptDetailPage() {
  const { t } = useTranslation('systemPrompts')
  const { id } = useParams<{ id: string }>()
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const { template, versions, loading, error, reload } = useSystemPrompt(id)
  const { form, onSubmit, saveError } = useSystemPromptForm(template, reload)
  // Vom System verwaltet (Builder-Template): Editor read-only, keine Status-
  // Aktionen (Backend sperrt mit 403 managed_aggregate).
  const locked = template?.is_managed === true

  if (id === undefined) {
    return <Navigate to={wsPath('/system-prompts')} replace />
  }

  return (
    <Container>
      <DataView loading={loading && template === null} error={error}>
        {template !== null ? (
          <div className="flex flex-col gap-6">
            <DetailHeader
              icon={ScrollText}
              iconTone="tools"
              title={template.name}
              backHref={wsPath('/system-prompts')}
              backLabel={t('nav.backToList')}
              badges={
                <>
                  <Badge variant="outline" className="font-mono">
                    {template.slug}
                  </Badge>
                  <StatusBadge
                    status={template.current_status}
                    pendingDraft={template.has_pending_draft}
                  />
                  <Badge variant="secondary">v{template.current_version}</Badge>
                  <LocaleBadge locale={template.locale} />
                </>
              }
              description={template.content.description}
              actions={
                <EntityDuplicateButton
                  texts={{
                    success: t('duplicate.success'),
                    error: t('duplicate.error'),
                    viewerReadOnly: t('duplicate.viewerReadOnly'),
                  }}
                  label={t('duplicate.label')}
                  onDuplicate={() => api.duplicateSystemPrompt(template.id)}
                  detailPath={(newId) => wsPath(`/system-prompts/${newId}`)}
                  testId="duplicate-system-prompt"
                />
              }
            />

            {/* Managed-Lock, Review-Banner oder schlichte Status-Aktionsleiste —
                dieselbe Transition-Logik wie zuvor, nur neu eingekleidet. */}
            {locked ? (
              <ManagedNotice />
            ) : template.current_status === 'review' ? (
              <AttentionBanner
                variant="brand"
                icon={Clock}
                title={`Version ${template.current_version} liegt zur Review`}
                description="Prüfe die Änderungen und aktiviere die Version oder schicke sie zurück in den Entwurf."
                actions={
                  <SystemPromptStatusActionBar
                    templateId={template.id}
                    version={template.current_version}
                    status={template.current_status}
                    onTransitioned={reload}
                  />
                }
              />
            ) : template.current_status !== undefined ? (
              <SystemPromptStatusActionBar
                templateId={template.id}
                version={template.current_version}
                status={template.current_status}
                onTransitioned={reload}
              />
            ) : null}

            <Tabs defaultValue="edit">
              <TabsList aria-label="Detail-Ansicht">
                <TabsTrigger value="edit">
                  <SquarePen aria-hidden="true" />
                  Bearbeiten
                </TabsTrigger>
                <TabsTrigger value="versions">
                  <GitBranch aria-hidden="true" />
                  Versionen
                </TabsTrigger>
              </TabsList>

              <TabsContent value="edit">
                <SystemPromptEditorForm
                  form={form}
                  onSubmit={onSubmit}
                  saveError={saveError}
                  locked={locked}
                />
              </TabsContent>

              <TabsContent value="versions">
                <VersionHistory
                  versions={versions}
                  canEdit={role === 'admin' || role === 'editor'}
                  onRestore={async (version) => {
                    await api.restoreSystemPromptTemplateVersion(template.id, version)
                    notify.success(`v${version} als Entwurf wiederhergestellt.`)
                    reload()
                  }}
                  loadDiff={(version) => api.diffSystemPromptTemplateVersion(template.id, version)}
                  loadProvenance={(version) =>
                    api.provenanceSystemPromptTemplateVersion(template.id, version)
                  }
                />
              </TabsContent>
            </Tabs>
          </div>
        ) : null}
      </DataView>
    </Container>
  )
}
