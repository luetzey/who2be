import {
  Boxes,
  Clock,
  FileText,
  GitBranch,
  Pencil,
  RotateCcw,
  Share2,
} from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { AttentionBanner } from '@/components/data/AttentionBanner'
import { BranchStatus } from '@/components/data/BranchStatus'
import { DataList } from '@/components/data/DataList'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { ManagedNotice } from '@/components/data/ManagedNotice'
import { StatusBadge } from '@/components/data/StatusBadge'
import { UsedByList } from '@/components/data/UsedByList'
import { GiveFeedbackDialog } from '@/components/feedback/GiveFeedbackDialog'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { VersionHistory } from '@/components/version'
import { useResourceSubResources } from '@/hooks/useResourceSubResources'
import { useResourceUsages } from '@/hooks/useResourceUsages'
import { notify } from '@/lib/feedback'

import { DeleteResourceButton } from '../components/DeleteResourceButton'
import { DuplicateResourceButton } from '../components/DuplicateResourceButton'
import { ExportResourceButton } from '../components/ExportResourceButton'
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
  // Vom System verwaltet: Editor read-only, keine Status-/Lösch-/Sub-Resource-
  // Aktionen (Backend sperrt mit 403 managed_aggregate).
  const locked = resource?.is_managed === true
  const canEdit = (role === 'admin' || role === 'editor') && !locked

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

  // Titel-/Beschreibungstext im Header (unveraendert gegenueber der alten Page,
  // damit Status-Text stabil bleibt).
  const description =
    resource === null
      ? ''
      : activeVersion !== undefined
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

  // Attention-Banner-Texte je Status (Design „Detail-Redesign": Brand-Band statt
  // nackter Button-Zeile). Die Aktion selbst bleibt die bestehende StatusActionBar.
  const bannerText = (status: VersionStatus, version: number) => {
    if (status === 'review') {
      return {
        title: t('detail.bannerReviewTitle', { version }),
        desc: t('detail.bannerReviewDescription'),
      }
    }
    if (status === 'inactive') {
      return {
        title: t('detail.bannerInactiveTitle', { version }),
        desc: t('detail.bannerInactiveDescription'),
      }
    }
    return {
      title: t('detail.bannerDraftTitle', { version }),
      desc: t('detail.bannerDraftDescription'),
    }
  }

  const tags = resource?.content.tags ?? []

  return (
    <Container>
      <DataView loading={loading && resource === null} error={error}>
        {resource !== null ? (
          <Stack gap="lg">
            <Stack gap="sm">
              <DetailHeader
                backHref={wsPath('/resources')}
                backLabel={t('list.title')}
                icon={FileText}
                iconTone="resource"
                title={resource.name}
                badges={
                  <>
                    <StatusBadge
                      status={resource.current_status}
                      pendingDraft={resource.has_pending_draft}
                    />
                    {resource.slug ? (
                      <Badge variant="outline" className="font-mono text-xs">
                        {resource.slug}
                      </Badge>
                    ) : null}
                    {tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </>
                }
                description={description}
                actions={
                  <>
                    {role === 'admin' || role === 'editor' ? (
                      <GiveFeedbackDialog
                        entityType="resource"
                        entityId={resource.id}
                        entityName={resource.name}
                        version={resource.current_version}
                      />
                    ) : null}
                    <ExportResourceButton resource={resource} />
                    <DuplicateResourceButton resource={resource} />
                    {canEdit ? <DeleteResourceButton resource={resource} /> : null}
                  </>
                }
              />

              {locked ? <ManagedNotice /> : null}

              <BranchStatus
                activeVersion={activeVersion?.version}
                draftVersion={draftVersion?.version}
                reviewVersion={reviewVersion?.version}
                inactiveVersion={inactiveCurrent?.version}
                currentVersion={resource.current_version}
                saveState={autoSave}
                actions={[]}
              />

              {!locked && promotableVersion !== undefined
                ? (() => {
                    const status = promotableVersion.status ?? 'draft'
                    const text = bannerText(status, promotableVersion.version)
                    return (
                      <AttentionBanner
                        variant="brand"
                        icon={Clock}
                        title={text.title}
                        description={text.desc}
                        actions={
                          <StatusActionBar
                            resourceId={resource.id}
                            version={promotableVersion.version}
                            status={status}
                            onTransitioned={reload}
                          />
                        }
                      />
                    )
                  })()
                : null}

              {!locked && inactiveCurrent !== undefined
                ? (() => {
                    const text = bannerText('inactive', inactiveCurrent.version)
                    return (
                      <AttentionBanner
                        variant="brand"
                        icon={RotateCcw}
                        title={text.title}
                        description={text.desc}
                        actions={
                          <StatusActionBar
                            resourceId={resource.id}
                            version={inactiveCurrent.version}
                            status="inactive"
                            onTransitioned={reload}
                          />
                        }
                      />
                    )
                  })()
                : null}
            </Stack>

            <Tabs defaultValue="edit">
              <TabsList aria-label={t('detail.subResourcesTitle')}>
                <TabsTrigger value="edit">
                  <Pencil aria-hidden="true" />
                  {t('tabs.edit')}
                </TabsTrigger>
                <TabsTrigger value="sub">
                  <Boxes aria-hidden="true" />
                  {t('tabs.subResources')}
                </TabsTrigger>
                <TabsTrigger value="use">
                  <Share2 aria-hidden="true" />
                  {t('tabs.usage')}
                </TabsTrigger>
                <TabsTrigger value="versions">
                  <GitBranch aria-hidden="true" />
                  {t('tabs.versions')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="edit">
                <ResourceEditorForm
                  form={form}
                  formKey={`${resource.id}-${resource.current_version}`}
                  initialBodyBlocks={resource.content.blocks ?? []}
                  locked={locked}
                />
              </TabsContent>

              <TabsContent value="sub">
                <Card>
                  <CardHeader>
                    <CardTitle>{t('detail.subResourcesTitle')}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DataView
                      loading={subResources.loading}
                      error={subResources.error}
                    >
                      {canEdit ? (
                        <SubResourcePicker
                          currentResourceId={resource.id}
                          existing={subResources.children}
                          saving={subResources.saving}
                          onSave={subResources.save}
                        />
                      ) : (
                        <DataView
                          empty={subResources.children.length === 0}
                          emptyTitle={t('detail.subResourcesEmptyTitle')}
                          emptyDescription={t(
                            'detail.subResourcesEmptyDescription',
                          )}
                        >
                          <DataList
                            items={subResources.children}
                            getKey={(sub) =>
                              `${sub.id}-${sub.block_id ?? 'doc'}`
                            }
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
                                    ? t('detail.scopeBlock', {
                                        blockId: sub.block_id ?? '',
                                      })
                                    : sub.embedding_mode === 'inline'
                                      ? t('detail.scopeDocumentInline')
                                      : t('detail.scopeDocumentLazy')}
                                </Badge>
                              </span>
                            )}
                          />
                        </DataView>
                      )}
                    </DataView>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="use">
                <Stack gap="lg">
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
                        <UsedByList
                          aria-label={t('detail.linkedIn')}
                          items={usages.usages.map((usage) => ({
                            id: usage.playbook_id,
                            name: usage.playbook_name,
                            href: wsPath(`/playbooks/${usage.playbook_id}`),
                            icon: GitBranch,
                            iconTone: 'playbook',
                            meta: t('detail.block', { count: usage.block_count }),
                          }))}
                        />
                      </DataView>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>{t('detail.usedByTitle')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <DataView
                        loading={subResources.loading}
                        error={subResources.error}
                      >
                        <ResourceUsedByList parents={subResources.parents} />
                      </DataView>
                    </CardContent>
                  </Card>
                </Stack>
              </TabsContent>

              <TabsContent value="versions">
                <VersionHistory
                  versions={versions}
                  canEdit={canEdit}
                  onRestore={async (version) => {
                    await api.restoreResourceVersion(resource.id, version)
                    notify.success(t('detail.restoredAsDraft', { version }))
                    reload()
                  }}
                  loadDiff={(version) =>
                    api.diffResourceVersion(resource.id, version)
                  }
                  loadProvenance={(version) =>
                    api.provenanceResourceVersion(resource.id, version)
                  }
                />
              </TabsContent>
            </Tabs>
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}
