import { ArrowLeft } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { BranchStatus } from '@/components/data/BranchStatus'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { VersionHistory } from '@/components/version'
import { useResourceSubResources } from '@/hooks/useResourceSubResources'
import { useResourceUsages } from '@/hooks/useResourceUsages'
import { notify } from '@/lib/feedback'

import { ResourceEditorForm } from '../components/ResourceEditorForm'
import { ResourceUsedByList } from '../components/ResourceUsedByList'
import { StatusActionBar } from '../components/StatusActionBar'
import { SubResourcePicker } from '../components/SubResourcePicker'
import { useResource } from '../hooks/useResource'
import { useResourceForm } from '../hooks/useResourceForm'
import { statusLabel } from '../lib/status'

export function ResourceDetailPage() {
  const { t } = useTranslation('resources')
  const { id } = useParams<{ id: string }>()
  const { resource, versions, loading, error, reload } = useResource(id)
  const { form, autoSave } = useResourceForm(resource, reload)
  const usages = useResourceUsages(id)
  const subResources = useResourceSubResources(id)
  const wsPath = useWorkspacePath()
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const canEdit = role === 'admin' || role === 'editor'

  if (id === undefined) {
    return <Navigate to={wsPath('/resources')} replace />
  }

  const draftVersion = versions.find((v) => v.status === 'draft')
  const reviewVersion = versions.find((v) => v.status === 'review')
  const activeVersion = versions.find((v) => v.status === 'active')
  const inactiveCurrent =
    activeVersion === undefined
      ? versions.find(
          (v) =>
            v.version === resource?.current_version && v.status === 'inactive',
        )
      : undefined

  const promotableVersion = reviewVersion ?? draftVersion

  return (
    <Container>
      <Stack gap="md">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link to={wsPath('/resources')}>
            <ArrowLeft className="h-4 w-4" />
            {t('list.title')}
          </Link>
        </Button>

        <DataView loading={loading && resource === null} error={error}>
          {resource !== null ? (
            <Stack gap="lg">
              {(() => {
                const description =
                  activeVersion !== undefined
                    ? `${t('detail.activeVersion', { version: activeVersion.version })}${
                        draftVersion !== undefined
                          ? ` · ${t('detail.workingOnDraft', { version: draftVersion.version })}`
                          : reviewVersion !== undefined
                            ? ` · ${t('detail.inReview', { version: reviewVersion.version })}`
                            : ''
                      }`
                    : t('detail.currentVersion', {
                        version: resource.current_version,
                        status: statusLabel(resource.current_status ?? 'draft'),
                      })
                return (
                  <Stack gap="sm">
                    <PageHeader title={resource.name} description={description} />
                    <BranchStatus
                      activeVersion={activeVersion?.version}
                      draftVersion={draftVersion?.version}
                      reviewVersion={reviewVersion?.version}
                      inactiveVersion={inactiveCurrent?.version}
                      currentVersion={resource.current_version}
                      saveState={autoSave}
                      actions={[]}
                    />
                    {promotableVersion !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={promotableVersion.version}
                        status={promotableVersion.status ?? 'draft'}
                        onTransitioned={reload}
                      />
                    ) : null}
                    {inactiveCurrent !== undefined ? (
                      <StatusActionBar
                        resourceId={resource.id}
                        version={inactiveCurrent.version}
                        status="inactive"
                        onTransitioned={reload}
                      />
                    ) : null}
                  </Stack>
                )
              })()}

              <ResourceEditorForm
                form={form}
                formKey={`${resource.id}-${resource.current_version}`}
                initialBodyBlocks={resource.content.blocks ?? []}
              />

              <Card>
                <CardHeader>
                  <CardTitle>{t('detail.linkedIn')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataView
                    loading={usages.loading}
                    error={usages.error}
                    empty={!usages.loading && usages.usages.length === 0}
                    emptyTitle={t('detail.usagesEmptyTitle')}
                    emptyDescription={t('detail.usagesEmptyDescription')}
                  >
                    <DataList
                      items={usages.usages}
                      getKey={(usage) => usage.playbook_id}
                      renderItem={(usage) => (
                        <span className="flex items-center justify-between gap-3">
                          <Link
                            to={wsPath(`/playbooks/${usage.playbook_id}`)}
                            className="truncate"
                          >
                            {usage.playbook_name}
                          </Link>
                          <Badge variant="secondary">
                            {t('detail.block', { count: usage.block_count })}
                          </Badge>
                        </span>
                      )}
                    />
                  </DataView>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('detail.subResourcesTitle')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Stack gap="sm">
                    <DataView
                      loading={subResources.loading}
                      error={subResources.error}
                      empty={
                        !subResources.loading && subResources.children.length === 0
                      }
                      emptyTitle={t('detail.subResourcesEmptyTitle')}
                      emptyDescription={t('detail.subResourcesEmptyDescription')}
                    >
                      <DataList
                        items={subResources.children}
                        getKey={(sub) => `${sub.id}-${sub.block_id ?? 'doc'}`}
                        renderItem={(sub) => (
                          <span className="flex items-center justify-between gap-3">
                            <Link
                              to={wsPath(`/resources/${sub.id}`)}
                              className="truncate"
                            >
                              {sub.name}
                            </Link>
                            <Badge variant="secondary">
                              {sub.link_scope === 'block'
                                ? t('detail.scopeBlock', { blockId: sub.block_id ?? '' })
                                : sub.embedding_mode === 'inline'
                                  ? t('detail.scopeDocumentInline')
                                  : t('detail.scopeDocumentLazy')}
                            </Badge>
                          </span>
                        )}
                      />
                    </DataView>
                    {canEdit ? (
                      <SubResourcePicker
                        currentResourceId={resource.id}
                        existing={subResources.children}
                        saving={subResources.saving}
                        onSave={subResources.save}
                      />
                    ) : null}
                  </Stack>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('detail.usedByTitle')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataView loading={subResources.loading} error={subResources.error}>
                    <ResourceUsedByList parents={subResources.parents} />
                  </DataView>
                </CardContent>
              </Card>

              <VersionHistory
                versions={versions}
                canEdit={canEdit}
                onRestore={async (version) => {
                  await api.restoreResourceVersion(resource.id, version)
                  notify.success(t('detail.restoredAsDraft', { version }))
                  reload()
                }}
                loadDiff={(version) => api.diffResourceVersion(resource.id, version)}
                loadProvenance={(version) =>
                  api.provenanceResourceVersion(resource.id, version)
                }
              />
            </Stack>
          ) : null}
        </DataView>
      </Stack>
    </Container>
  )
}
